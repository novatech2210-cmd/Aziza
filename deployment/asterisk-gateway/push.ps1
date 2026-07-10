<#
.SYNOPSIS
    Push deploy/asterisk-gateway/*.conf to the office TAS-IX gateway,
    apply each file atomically, reload the relevant Asterisk subsystem,
    and tail the journal.

.DESCRIPTION
    Standard local-first IaC loop, mirrored from deploy/kamailio/push.ps1
    but extended to cover multiple config files.

        edit configs locally  ->  ./push.ps1  ->  live gateway

    Files pushed:
      pjsip.conf          -> /etc/asterisk/pjsip.conf            (pjsip reload)
      pjsip.secrets.conf  -> /etc/asterisk/pjsip.secrets.conf    (pjsip reload)
      extensions.conf     -> /etc/asterisk/extensions.conf       (dialplan reload)
      rtp.conf            -> /etc/asterisk/rtp.conf              (module reload res_rtp_asterisk.so)

    pjsip.secrets.conf is gitignored. If the local copy is missing, the
    push aborts with a clear message - the operator must populate it from
    pjsip.secrets.conf.example first.

    Asterisk has no offline config validator (unlike kamailio -c), so the
    safety pattern is:
      1. Copy local -> /etc/asterisk/<file>.new.<UTC-timestamp>  (staged)
      2. Backup live    -> /etc/asterisk/<file>.bak.<UTC-timestamp>
      3. Atomic move    -> mv staged -> live path
      4. Issue the file's reload command
      5. If the reload errors are non-empty, surface them (but do not
         auto-rollback - operator decides). Backup path is printed for
         one-line revert.

.PARAMETER DryRun
    Show per-file diff against live and exit. Nothing is uploaded.

.PARAMETER Pull
    Replace LOCAL copies with the current live files (overwrites).
    Use this if anyone edited /etc/asterisk/ on the gateway directly.

.PARAMETER Diff
    Synonym for -DryRun.

.PARAMETER RemoteHost
    SSH alias from ~/.ssh/config. Default: sida-gateway.
    See Docs/REFERENCE_Hosts_and_SSH_Aliases.md for the canonical host list.

.EXAMPLE
    .\push.ps1 -DryRun
    .\push.ps1
    .\push.ps1 -Pull
#>
param(
    [switch]$DryRun,
    [switch]$Pull,
    [switch]$Diff,
    [string]$RemoteHost = "sida-gateway"
)

# Continue on non-zero exit + stderr from native commands (scp / ssh).
# The script checks $LASTEXITCODE after each invocation explicitly.
$ErrorActionPreference = "Continue"

$Files = @(
    @{ Local = "pjsip.conf";         Remote = "/etc/asterisk/pjsip.conf";         Reload = "pjsip reload";                       Required = $true  }
    @{ Local = "pjsip.secrets.conf"; Remote = "/etc/asterisk/pjsip.secrets.conf"; Reload = "pjsip reload";                       Required = $true  }
    @{ Local = "extensions.conf";    Remote = "/etc/asterisk/extensions.conf";    Reload = "dialplan reload";                    Required = $true  }
    @{ Local = "rtp.conf";           Remote = "/etc/asterisk/rtp.conf";           Reload = "module reload res_rtp_asterisk.so";  Required = $true  }
)

function Step ($m) { Write-Host "[push] $m" -ForegroundColor Cyan }
function Note ($m) { Write-Host "       $m" -ForegroundColor DarkGray }
function Ok   ($m) { Write-Host "[ok]   $m" -ForegroundColor Green }
function Warn ($m) { Write-Host "[warn] $m" -ForegroundColor Yellow }
function Fail ($m) { Write-Host "[err]  $m" -ForegroundColor Red; exit 1 }

# -- Pre-flight: every required local file must exist --
foreach ($f in $Files) {
    $localPath = Join-Path $PSScriptRoot $f.Local
    if (-not (Test-Path $localPath) -and $f.Required) {
        if ($f.Local -eq "pjsip.secrets.conf") {
            Fail "Missing $localPath. Copy pjsip.secrets.conf.example -> pjsip.secrets.conf and fill in the real password before pushing."
        }
        Fail "Missing required local file: $localPath"
    }
}

# -- Pull mode --
if ($Pull) {
    foreach ($f in $Files) {
        $localPath = Join-Path $PSScriptRoot $f.Local
        Step "Pulling ${RemoteHost}:$($f.Remote) -> $localPath"
        scp "${RemoteHost}:$($f.Remote)" $localPath
        if ($LASTEXITCODE -ne 0) { Fail "scp pull failed for $($f.Local) (exit $LASTEXITCODE)." }
        $h = (Get-FileHash -Algorithm SHA256 $localPath).Hash.ToLower()
        Ok "$($f.Local) refreshed. SHA256: $h"
    }
    exit 0
}

# -- DryRun / Diff mode: per-file SHA + line diff --
if ($DryRun -or $Diff) {
    $changed = 0
    foreach ($f in $Files) {
        $localPath = Join-Path $PSScriptRoot $f.Local
        $tmp = New-TemporaryFile
        try {
            scp "${RemoteHost}:$($f.Remote)" $tmp.FullName *> $null
            $remoteOk = ($LASTEXITCODE -eq 0)
            if (-not $remoteOk) {
                Note "$($f.Local): live file does not exist on remote yet (would be created on push)"
                $changed++
                continue
            }
            $localHash  = (Get-FileHash -Algorithm SHA256 -LiteralPath $localPath).Hash.ToLower()
            $remoteHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp.FullName).Hash.ToLower()
            if ($localHash -eq $remoteHash) {
                Ok "$($f.Local): matches live (SHA256 $localHash)"
            } else {
                Warn "$($f.Local): differs"
                Note "Local  SHA256: $localHash"
                Note "Live   SHA256: $remoteHash"
                Step "Line diff (Windows fc.exe):"
                & cmd /c "fc.exe /N `"$localPath`" `"$($tmp.FullName)`""
                $changed++
            }
        } finally {
            Remove-Item $tmp.FullName -ErrorAction SilentlyContinue
        }
    }
    Note "Dry-run complete. Files that would be pushed: $changed"
    exit 0
}

# -- Real push: per-file stage -> backup -> atomic apply -> reload --
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$backupPaths = @{}

foreach ($f in $Files) {
    $localPath  = Join-Path $PSScriptRoot $f.Local
    $remotePath = $f.Remote
    $staged     = "$remotePath.new.$ts"
    $backup     = "$remotePath.bak.$ts"

    # Skip files that already match live (saves a reload)
    $tmp = New-TemporaryFile
    try {
        scp "${RemoteHost}:$remotePath" $tmp.FullName *> $null
        if ($LASTEXITCODE -eq 0) {
            $localHash  = (Get-FileHash -Algorithm SHA256 -LiteralPath $localPath).Hash.ToLower()
            $remoteHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp.FullName).Hash.ToLower()
            if ($localHash -eq $remoteHash) {
                Ok "$($f.Local): already up to date"
                $f.NeedsReload = $false
                continue
            }
        }
    } finally {
        Remove-Item $tmp.FullName -ErrorAction SilentlyContinue
    }
    $f.NeedsReload = $true

    Step "Staging $($f.Local) -> ${RemoteHost}:$staged"
    scp $localPath "${RemoteHost}:$staged"
    if ($LASTEXITCODE -ne 0) { Fail "scp upload failed for $($f.Local) (exit $LASTEXITCODE)." }

    Step "Backing up live -> $backup"
    ssh $RemoteHost "test -f $remotePath && cp $remotePath $backup || echo 'No live file to back up.'"
    $backupPaths[$f.Local] = $backup

    Step "Applying -> $remotePath"
    ssh $RemoteHost "mv $staged $remotePath"
    if ($LASTEXITCODE -ne 0) { Fail "Atomic apply failed for $($f.Local) (exit $LASTEXITCODE). Backup at $backup." }
    Ok "$($f.Local) applied"
}

# -- Reload only the subsystems whose files changed --
$reloads = @{}
foreach ($f in $Files) {
    if ($f.NeedsReload) {
        $reloads[$f.Reload] = $true
    }
}
if ($reloads.Count -eq 0) {
    Ok "Nothing changed - no reload needed."
} else {
    foreach ($r in $reloads.Keys) {
        Step "Reloading: asterisk -rx '$r'"
        ssh $RemoteHost "asterisk -rx '$r'"
        if ($LASTEXITCODE -ne 0) { Warn "Reload command exited non-zero: $r" }
    }
}

Start-Sleep -Seconds 1

# -- Health check --
$status = (ssh $RemoteHost "systemctl is-active asterisk").Trim()
if ($status -ne "active") {
    Note "systemd status: $status"
    ssh $RemoteHost "journalctl -u asterisk -n 40 --no-pager" | ForEach-Object { Note $_ }
    Fail "Asterisk not active after reload."
}
Ok "Asterisk is active."

# -- Show registrations + last journal slice --
Step "PJSIP registrations:"
ssh $RemoteHost "asterisk -rx 'pjsip show registrations'" | ForEach-Object { Write-Host "  $_" }

Step "Last 15 journal lines:"
ssh $RemoteHost "journalctl -u asterisk -n 15 --no-pager" | ForEach-Object { Write-Host "  $_" }

if ($backupPaths.Count -gt 0) {
    Note ""
    Note "Rollback (per file):"
    $dq = [char]34
    $sq = [char]39
    foreach ($k in $backupPaths.Keys) {
        $bp = $backupPaths[$k]
        $rollbackCmd = "ssh " + $RemoteHost + " " + $dq + "cp " + $bp + " /etc/asterisk/" + $k + "; asterisk -rx " + $sq + "core reload" + $sq + $dq
        Note ("  " + $rollbackCmd)
    }
}
