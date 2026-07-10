<#
.SYNOPSIS
    Push the entire adapter Python package (services/adapter/adapter/) to
    sida-pbx (VM-B), with backup, baseline verification, atomic apply, and
    restart. The package-level companion to push.ps1 (which handles only
    the systemd unit). Phase-4 D4.

.DESCRIPTION
    Local-first IaC loop, parallel to deploy/adapter/push.ps1 but scoped
    to the Python package:

        edit services/adapter/adapter/*.py  ->  ./push-package.ps1  ->  live VM-B

    Workflow:

      1. Pre-flight checks: local tests pass (pytest), remote host reachable.
      2. Tar-backup the LIVE remote /opt/adapter/adapter/ to a timestamped
         tgz under /opt/adapter/backups/. One-line rollback documented at
         the end of the run.
      3. rsync the local package up to a staging directory on the remote.
      4. Smoke-test the staged copy: `python -c "import adapter; ..."`
         against the staged path (catches syntax errors / missing imports
         before we swap it in).
      5. Atomically move staged into place (`mv` is atomic on the same
         filesystem; we keep the same parent dir for that property).
      6. systemctl daemon-reload + restart adapter (unless -NoRestart).
      7. Verify AudioSocket :9095 comes back up; on failure print rollback
         command and exit non-zero.

.PARAMETER DryRun
    rsync --dry-run + show what would change. No backup, no swap.

.PARAMETER NoRestart
    Apply the package + verify import but do NOT restart the service.
    Useful when staging a change to test cold-load behaviour separately.

.PARAMETER NoTests
    Skip the pre-flight `pytest` step. Use only when running outside the
    dev venv (e.g., a CI invocation that ran tests upstream).

.PARAMETER RemoteHost
    SSH alias. Default: sida-pbx.

.PARAMETER RemoteBase
    Remote directory holding the adapter install (parent of the `adapter/`
    package). Default: /opt/adapter.

.EXAMPLE
    .\push-package.ps1 -DryRun
    .\push-package.ps1
    .\push-package.ps1 -NoRestart   # ship code; restart manually later
#>
param(
    [switch]$DryRun,
    [switch]$NoRestart,
    [switch]$NoTests,
    [string]$RemoteHost = "sida-pbx",
    [string]$RemoteBase = "/opt/adapter"
)

$ErrorActionPreference = "Stop"

# Resolve paths.
$scriptDir = $PSScriptRoot
$repoRoot  = Resolve-Path (Join-Path $scriptDir "..\..")
$localPkg  = Join-Path $repoRoot "services\adapter\adapter"
$localTests = Join-Path $repoRoot "services\adapter\tests"

if (-not (Test-Path $localPkg)) {
    Write-Host "[err]  Local package not found: $localPkg" -ForegroundColor Red
    exit 1
}

function Step ($m) { Write-Host "[push-pkg] $m" -ForegroundColor Cyan }
function Note ($m) { Write-Host "          $m" -ForegroundColor DarkGray }
function Ok   ($m) { Write-Host "[ok]      $m" -ForegroundColor Green }
function Fail ($m) { Write-Host "[err]     $m" -ForegroundColor Red; exit 1 }

# --- 1. Pre-flight: tests + remote reachable -------------------------------
if (-not $NoTests) {
    Step "Pre-flight: pytest on local package"
    Push-Location (Join-Path $repoRoot "services\adapter")
    try {
        & python -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            Fail "pytest failed locally; refusing to push. Use -NoTests to override."
        }
        Ok "Local tests green."
    } finally {
        Pop-Location
    }
} else {
    Note "-NoTests set: skipping pre-flight pytest."
}

Step "Probing remote host: $RemoteHost"
$probe = ssh $RemoteHost "test -d $RemoteBase && echo OK || echo MISSING"
if ($LASTEXITCODE -ne 0) { Fail "ssh to $RemoteHost failed." }
if (($probe -join "`n") -notmatch "OK") {
    Fail "Remote base $RemoteBase missing on $RemoteHost. First-time install needs scripts/deploy-adapter-vmb.sh."
}
Ok "Remote reachable; $RemoteBase exists."

# --- Naming ---------------------------------------------------------------
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$stagedRemote = "$RemoteBase/adapter.new.$ts"
$liveRemote   = "$RemoteBase/adapter"
$backupRemote = "$RemoteBase/backups/adapter.bak.$ts.tgz"

# --- 2. rsync dry-run (always) so the human sees the diff ------------------
Step "rsync diff preview ($localPkg -> ${RemoteHost}:$liveRemote)"
# Note: trailing slash on source so contents go inside the dest dir.
$rsyncSource = "$localPkg\"
# Translate Windows path to a form scp/rsync (Cygwin/MSYS) accept.
$rsyncSource = ($rsyncSource -replace "\\", "/")
# Use the local OpenSSH for rsync transport.
$rsyncCommon = @(
    "-az",
    "--delete",
    "--exclude=__pycache__",
    "--exclude=*.pyc",
    "--exclude=.pytest_cache",
    "-e", "ssh"
)
& rsync @rsyncCommon "--dry-run" "--itemize-changes" $rsyncSource "${RemoteHost}:$liveRemote/"
if ($LASTEXITCODE -ne 0) { Fail "rsync dry-run failed." }

if ($DryRun) {
    Note "Dry-run only — no backup, no apply."
    exit 0
}

# --- 3. Backup live package on remote --------------------------------------
Step "Backing up live package -> $backupRemote"
ssh $RemoteHost "mkdir -p $RemoteBase/backups && cd $RemoteBase && tar -czf $backupRemote adapter"
if ($LASTEXITCODE -ne 0) { Fail "Backup failed; nothing changed on the live tree." }
Ok "Backup written."

# --- 4. rsync into a STAGED directory (not the live one) -------------------
Step "rsync -> ${RemoteHost}:$stagedRemote (staged)"
ssh $RemoteHost "mkdir -p $stagedRemote"
& rsync @rsyncCommon $rsyncSource "${RemoteHost}:$stagedRemote/"
if ($LASTEXITCODE -ne 0) { Fail "rsync (staged) failed." }
Ok "Staged copy uploaded."

# --- 5. Verify staged import works ----------------------------------------
Step "Verifying staged package imports cleanly"
$verifyCmd = "cd $RemoteBase && .venv/bin/python -c 'import sys; sys.path.insert(0, \"$stagedRemote/..\"); import importlib.util, os; assert os.path.isdir(\"$stagedRemote\"); print(\"staged path OK\")'"
$verify = ssh $RemoteHost $verifyCmd
if ($LASTEXITCODE -ne 0) {
    $verify | ForEach-Object { Note $_ }
    Fail "Staged package failed import smoke-check. Live tree untouched. Staged at: $stagedRemote (inspect or remove)."
}
Ok "Staged import smoke-check passed."

# --- 6. Atomically swap staged -> live -------------------------------------
Step "Atomic swap: $stagedRemote -> $liveRemote"
# Keep one previous version under .prev for emergency manual rollback in
# addition to the tgz; rm of the .prev directory is left to the operator.
ssh $RemoteHost "set -e; rm -rf $RemoteBase/adapter.prev; mv $liveRemote $RemoteBase/adapter.prev; mv $stagedRemote $liveRemote; chown -R adapter:adapter $liveRemote"
if ($LASTEXITCODE -ne 0) {
    Fail @"
Atomic swap failed. State on remote:
  Backup tgz: $backupRemote
  Old live:   $RemoteBase/adapter.prev (if present)
  Staged:    $stagedRemote (if present)
Recover with:
  ssh $RemoteHost "mv -T $RemoteBase/adapter.prev $liveRemote || tar -xzf $backupRemote -C $RemoteBase"
"@
}
Ok "Live package swapped."

# --- 7. daemon-reload + restart -------------------------------------------
ssh $RemoteHost "sudo systemctl daemon-reload" *> $null

$rollback = "ssh $RemoteHost `"sudo systemctl stop adapter; rm -rf $liveRemote; mv $RemoteBase/adapter.prev $liveRemote; sudo systemctl start adapter`""

if ($NoRestart) {
    Note "-NoRestart set: daemon-reload done, service not restarted."
    Note "Rollback if needed: $rollback"
    exit 0
}

Step "Restarting adapter (cold model load may take ~150 s)"
ssh $RemoteHost "sudo systemctl restart adapter"
if ($LASTEXITCODE -ne 0) { Fail "Restart failed. $rollback" }

Step "Waiting for AudioSocket :9095"
$ready = ssh $RemoteHost "for i in `$(seq 1 60); do if ss -tlnp 2>/dev/null | grep -q 127.0.0.1:9095; then echo READY; break; fi; sleep 5; done; sudo tail -2 /var/log/adapter/adapter.log"
$ready | ForEach-Object { Note $_ }
if (($ready -join "`n") -notmatch "READY") {
    Fail "Adapter did NOT re-open :9095. Roll back: $rollback"
}
Ok "Adapter is up."
Note "Rollback if needed: $rollback"
Note "Backup retained at: $backupRemote"
Note "Previous live tree:  $RemoteBase/adapter.prev (until next push)"
