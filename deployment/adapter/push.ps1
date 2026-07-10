<#
.SYNOPSIS
    Push deploy/adapter/adapter.service to sida-pbx (VM-B), validate it,
    back up the live unit, apply atomically, daemon-reload + restart the
    adapter, and verify the AudioSocket port comes back.

.DESCRIPTION
    Local-first IaC loop, mirrored from deploy/kamailio/push.ps1 -- but
    SCOPED TO THE SYSTEMD UNIT ONLY.

        edit deploy/adapter/adapter.service  ->  ./push.ps1  ->  live VM-B

    Why unit-only: this script was originally scoped to the systemd unit
    file alone because the adapter Python package had uncommitted in-flight
    changes that a blind *.py sync would have shipped to production.
    **Phase-4 D4 promoted package-level IaC into a SEPARATE script —
    deploy/adapter/push-package.ps1 — which syncs the Python package
    with the same backup + verify-baseline discipline.** This unit-only
    script remains the right tool when only the systemd unit changes
    (the unit changes rarely; the Python package changes often, so the
    two have different cadences and warrant separate entry points).
    The unit file remains the stable artifact and carries the two
    production-blocking fixes from 2026-05-15 (PrivateTmp=false, ExecReload).

    The live unit is backed up to
      /etc/systemd/system/adapter.service.bak.<UTC>
    before overwrite -- one-line rollback.

.PARAMETER DryRun
    Show the unit diff vs live and exit. Nothing is uploaded.

.PARAMETER Pull
    Overwrite the LOCAL adapter.service from the live VM-B.

.PARAMETER NoRestart
    Apply the unit + daemon-reload but do NOT restart the service
    (restart cold-loads the ~3.5 GB RU model, ~150 s). Use when the
    change does not need a restart to take effect.

.PARAMETER RemoteHost
    SSH alias. Default: sida-pbx.

.EXAMPLE
    .\push.ps1 -DryRun
    .\push.ps1
    .\push.ps1 -Pull
#>
param(
    [switch]$DryRun,
    [switch]$Pull,
    [switch]$NoRestart,
    [string]$RemoteHost = "sida-pbx",
    [string]$RemotePath = "/etc/systemd/system/adapter.service",
    [string]$LocalPath  = (Join-Path $PSScriptRoot "adapter.service")
)

$ErrorActionPreference = "Stop"

function Step ($m) { Write-Host "[push] $m" -ForegroundColor Cyan }
function Note ($m) { Write-Host "       $m" -ForegroundColor DarkGray }
function Ok   ($m) { Write-Host "[ok]   $m" -ForegroundColor Green }
function Fail ($m) { Write-Host "[err]  $m" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $LocalPath)) { Fail "Local file not found: $LocalPath" }

# --- Pull mode ------------------------------------------------------
if ($Pull) {
    Step "Pulling ${RemoteHost}:$RemotePath -> $LocalPath"
    scp "${RemoteHost}:$RemotePath" $LocalPath
    if ($LASTEXITCODE -ne 0) { Fail "scp failed (exit $LASTEXITCODE)." }
    Ok "Local refreshed from live."
    exit 0
}

# --- Hash compare vs live ------------------------------------------
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

    if ($DryRun) {
        Step "Line-level diff (fc.exe):"
        & cmd /c "fc.exe /N `"$LocalPath`" `"$($tmp.FullName)`""
        Note "Dry-run / diff-only. Not pushing."
        exit 0
    }
} finally {
    Remove-Item $tmp.FullName -ErrorAction SilentlyContinue
}

# --- Stage -> validate -> backup -> apply -> reload/restart --------
$ts     = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$staged = "/tmp/adapter.service.new.$ts"
$backup = "${RemotePath}.bak.$ts"

Step "Staging -> ${RemoteHost}:$staged"
scp $LocalPath "${RemoteHost}:$staged"
if ($LASTEXITCODE -ne 0) { Fail "scp upload failed (exit $LASTEXITCODE)." }

Step "Validating: systemd-analyze verify"
$validate = ssh $RemoteHost "sudo systemd-analyze verify $staged 2>&1; echo __EC__=`$?"
$ec = ($validate | Select-String "__EC__=" | Select-Object -Last 1) -replace "__EC__=", ""
if ($ec.ToString().Trim() -ne "0") {
    $validate | Where-Object { $_ -notmatch "^__EC__" } | ForEach-Object { Note $_ }
    ssh $RemoteHost "rm -f $staged" *> $null
    Fail "systemd-analyze verify failed. Staged file removed. Live unit NOT touched."
}
Ok "Validation passed."

Step "Backing up live -> $backup"
ssh $RemoteHost "sudo cp $RemotePath $backup"
if ($LASTEXITCODE -ne 0) { Fail "Backup failed (exit $LASTEXITCODE). Aborting." }

Step "Applying: mv $staged -> $RemotePath"
ssh $RemoteHost "sudo mv $staged $RemotePath && sudo chown root:root $RemotePath && sudo systemctl daemon-reload"
if ($LASTEXITCODE -ne 0) { Fail "Apply failed (exit $LASTEXITCODE). Backup at $backup." }
Ok "Unit applied + daemon-reload done."

if ($NoRestart) {
    Note "-NoRestart set: service NOT restarted. New unit takes effect on next restart."
    Note "Rollback: ssh $RemoteHost `"sudo cp $backup $RemotePath; sudo systemctl daemon-reload`""
    exit 0
}

Step "Restarting adapter (cold RU-model load may take ~150s)"
ssh $RemoteHost "sudo systemctl restart adapter"
if ($LASTEXITCODE -ne 0) { Fail "Restart failed (exit $LASTEXITCODE). Backup at $backup." }

Step "Waiting for AudioSocket :9095"
$ready = ssh $RemoteHost "for i in `$(seq 1 60); do if ss -tlnp 2>/dev/null | grep -q 127.0.0.1:9095; then echo READY; break; fi; sleep 5; done; sudo tail -2 /var/log/adapter/adapter.log"
$ready | ForEach-Object { Note $_ }
$rollback = "ssh $RemoteHost `"sudo cp $backup $RemotePath; sudo systemctl daemon-reload; sudo systemctl restart adapter`""
if (($ready -join "`n") -notmatch "READY") {
    Fail "Adapter did not re-open :9095. Roll back: $rollback"
}
Ok "Adapter is up."
Note "Rollback if needed: $rollback"
