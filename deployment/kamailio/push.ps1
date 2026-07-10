<#
.SYNOPSIS
    Push deploy/kamailio/kamailio.cfg to sida-kam, validate it remotely, apply
    atomically, reload kamailio, and tail the journal.

.DESCRIPTION
    Standard local-first IaC loop:

        edit kamailio.cfg locally  →  ./push.ps1  →  live VM-A

    The live config is never touched until the staged copy passes
    `kamailio -c`. The previous live file is backed up under
    /etc/kamailio/kamailio.cfg.bak.<UTC-timestamp> for one-line rollback.

.PARAMETER DryRun
    Show the diff against live and exit. Nothing is uploaded.

.PARAMETER Pull
    Replace the LOCAL kamailio.cfg with the current live file from VM-A.
    Use this if you suspect anyone edited /etc/kamailio/ on the VM directly.

.PARAMETER Diff
    Same as -DryRun. Synonym for clarity.

.PARAMETER RemoteHost
    SSH alias from ~/.ssh/config. Default: sida-kam.

.EXAMPLE
    .\push.ps1 -DryRun
    .\push.ps1
    .\push.ps1 -Pull
#>
param(
    [switch]$DryRun,
    [switch]$Pull,
    [switch]$Diff,
    [string]$RemoteHost = "sida-kam",
    [string]$RemotePath = "/etc/kamailio/kamailio.cfg",
    [string]$LocalPath  = (Join-Path $PSScriptRoot "kamailio.cfg")
)

$ErrorActionPreference = "Stop"

function Step ($m) { Write-Host "[push] $m" -ForegroundColor Cyan }
function Note ($m) { Write-Host "       $m" -ForegroundColor DarkGray }
function Ok   ($m) { Write-Host "[ok]   $m" -ForegroundColor Green }
function Fail ($m) { Write-Host "[err]  $m" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $LocalPath)) { Fail "Local file not found: $LocalPath" }

# ── Pull mode ────────────────────────────────────────────────────────
if ($Pull) {
    Step "Pulling ${RemoteHost}:$RemotePath -> $LocalPath"
    scp "${RemoteHost}:$RemotePath" $LocalPath
    if ($LASTEXITCODE -ne 0) { Fail "scp failed (exit $LASTEXITCODE)." }
    $h = (Get-FileHash -Algorithm SHA256 $LocalPath).Hash.ToLower()
    Ok "Local refreshed. SHA256: $h"
    exit 0
}

# ── Hash check vs live ───────────────────────────────────────────────
Step "Comparing local vs live ${RemoteHost}:$RemotePath"
$tmp = New-TemporaryFile
try {
    scp "${RemoteHost}:$RemotePath" $tmp.FullName *> $null
    if ($LASTEXITCODE -ne 0) { Fail "scp pull for diff failed (exit $LASTEXITCODE)." }
    $localHash  = (Get-FileHash -Algorithm SHA256 -LiteralPath $LocalPath).Hash.ToLower()
    $remoteHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp.FullName).Hash.ToLower()

    if ($localHash -eq $remoteHash) {
        Ok "Local matches live (SHA256 $localHash). Nothing to push."
        exit 0
    }

    Note "Local  SHA256: $localHash"
    Note "Live   SHA256: $remoteHash"

    if ($DryRun -or $Diff) {
        Step "Line-level diff (Windows fc.exe):"
        # fc is Windows' built-in file-compare; quiet exit code 0 = identical, 1 = differs
        & cmd /c "fc.exe /N `"$($LocalPath)`" `"$($tmp.FullName)`""
        Note "Dry-run / diff-only. Not pushing."
        exit 0
    }
} finally {
    Remove-Item $tmp.FullName -ErrorAction SilentlyContinue
}

# ── Push: stage → validate → backup → atomic apply → reload ──────────
$ts        = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$staged    = "/etc/kamailio/kamailio.cfg.new.$ts"
$backup    = "/etc/kamailio/kamailio.cfg.bak.$ts"

Step "Staging -> ${RemoteHost}:$staged"
scp $LocalPath "${RemoteHost}:$staged"
if ($LASTEXITCODE -ne 0) { Fail "scp upload failed (exit $LASTEXITCODE)." }

Step "Validating: kamailio -c -f $staged"
$validateOut = ssh $RemoteHost "kamailio -c -f $staged 2>&1; echo __EC__=`$?"
$ec = ($validateOut | Select-String "__EC__=" | Select-Object -Last 1) -replace "__EC__=", ""
if ($ec.ToString().Trim() -ne "0") {
    $validateOut | Where-Object { $_ -notmatch "^__EC__" } | ForEach-Object { Note $_ }
    ssh $RemoteHost "rm -f $staged" *> $null
    Fail "Validation failed. Staged file removed. Live config NOT touched."
}
Ok "Validation passed."

Step "Backing up live -> $backup"
ssh $RemoteHost "cp $RemotePath $backup"
if ($LASTEXITCODE -ne 0) { Fail "Backup failed (exit $LASTEXITCODE). Aborting." }

Step "Applying: mv $staged -> $RemotePath"
ssh $RemoteHost "mv $staged $RemotePath"
if ($LASTEXITCODE -ne 0) { Fail "Atomic apply failed (exit $LASTEXITCODE). Backup at $backup." }

Step "Restarting kamailio (no graceful reload available; the systemd unit has no ExecReload)"
ssh $RemoteHost "systemctl restart kamailio"
if ($LASTEXITCODE -ne 0) { Fail "Restart failed (exit $LASTEXITCODE). Backup at $backup." }
Start-Sleep -Seconds 2

$status = (ssh $RemoteHost "systemctl is-active kamailio").Trim()
if ($status -ne "active") {
    Note "systemd status: $status"
    ssh $RemoteHost "journalctl -u kamailio -n 40 --no-pager" | ForEach-Object { Note $_ }
    Fail "kamailio not active after reload. Backup at $backup. Roll back with: ssh $RemoteHost `"cp $backup $RemotePath && systemctl reload kamailio`""
}
Ok "kamailio is active."

Step "Last 15 log lines:"
ssh $RemoteHost "journalctl -u kamailio -n 15 --no-pager" | ForEach-Object { Write-Host "  $_" }
Note "Rollback available: ssh $RemoteHost `"cp $backup $RemotePath && systemctl reload kamailio`""
