<#
.SYNOPSIS
    rsync the two source trees (Kyo's aziza-web + our dialogue-engine + the
    deploy/ subtree) to a hourly-rented GPU VPS's /workspace/_src/.

.DESCRIPTION
    Run on your laptop BEFORE starting work on the VPS. The VPS then runs
    deploy/vps/deploy-all.sh which reads from /workspace/_src/ and rsyncs
    into the live trees at /workspace/{aziza-web,telephony-llm}/.

    Three trees pushed:

      Local                                  →  VPS
      external/aziza-web/                    →  /workspace/_src/aziza-web/
      services/dialogue-engine/              →  /workspace/_src/dialogue-engine/
      deploy/                                →  /workspace/_src/deploy/

.PARAMETER RemoteHost
    SSH alias or user@host:port for the VPS. Required.

.PARAMETER DryRun
    Show what would change; don't transfer.

.EXAMPLE
    .\push-sources.ps1 -RemoteHost root@vast-instance:22
    .\push-sources.ps1 -RemoteHost <ssh-alias> -DryRun
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$RemoteHost,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$repoRoot  = Resolve-Path (Join-Path $scriptDir "..\..")

function Step ($m) { Write-Host "[push] $m" -ForegroundColor Cyan }
function Ok   ($m) { Write-Host "[ok]   $m" -ForegroundColor Green }
function Fail ($m) { Write-Host "[err]  $m" -ForegroundColor Red; exit 1 }

# Verify local source trees exist.
$aziza  = Join-Path $repoRoot "external\aziza-web"
$dialog = Join-Path $repoRoot "services\dialogue-engine"
$deploy = Join-Path $repoRoot "deploy"

if (-not (Test-Path "$aziza\backend"))  { Fail "missing $aziza\backend — extract Kyo's repo into external/aziza-web/ first" }
if (-not (Test-Path "$dialog\dialogue_engine")) { Fail "missing $dialog\dialogue_engine — should be in repo" }
if (-not (Test-Path "$deploy\vps"))     { Fail "missing $deploy\vps — should be in repo" }

# rsync sources (Windows-friendly paths via cygwin/MSYS rsync; on Windows 10+ ssh is fine)
$rsyncArgs = @(
    "-az",
    "--delete",
    "--exclude=__pycache__",
    "--exclude=*.pyc",
    "--exclude=.pytest_cache",
    "--exclude=.venv",
    "--exclude=node_modules",
    "--exclude=.git",
    "-e", "ssh"
)
if ($DryRun) { $rsyncArgs += "--dry-run", "--itemize-changes" }

# Normalize paths for rsync (forward slashes, trailing slash on source for contents-only).
function _rs($win) { return ($win -replace "\\", "/") + "/" }

Step "rsync external/aziza-web/ -> ${RemoteHost}:/workspace/_src/aziza-web/"
& rsync @rsyncArgs (_rs $aziza) "${RemoteHost}:/workspace/_src/aziza-web/"
if ($LASTEXITCODE -ne 0) { Fail "aziza-web push failed (exit $LASTEXITCODE)" }
Ok "aziza-web pushed"

Step "rsync services/dialogue-engine/ -> ${RemoteHost}:/workspace/_src/dialogue-engine/"
& rsync @rsyncArgs (_rs $dialog) "${RemoteHost}:/workspace/_src/dialogue-engine/"
if ($LASTEXITCODE -ne 0) { Fail "dialogue-engine push failed (exit $LASTEXITCODE)" }
Ok "dialogue-engine pushed"

Step "rsync deploy/ -> ${RemoteHost}:/workspace/_src/deploy/"
& rsync @rsyncArgs (_rs $deploy) "${RemoteHost}:/workspace/_src/deploy/"
if ($LASTEXITCODE -ne 0) { Fail "deploy push failed (exit $LASTEXITCODE)" }
Ok "deploy/ pushed"

if ($DryRun) {
    Write-Host ""
    Write-Host "Dry-run only. No files transferred." -ForegroundColor DarkGray
    exit 0
}

Write-Host ""
Write-Host "Sources pushed. Now on the VPS:" -ForegroundColor Cyan
Write-Host "  ssh $RemoteHost" -ForegroundColor DarkGray
Write-Host "  cd /workspace/_src/deploy/vps" -ForegroundColor DarkGray
Write-Host "  sudo ./deploy-all.sh" -ForegroundColor DarkGray
