param(
    [switch]$Install,
    [string]$LiveBaseUrl = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".env\Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"

if (-not (Test-Path $Python)) {
    python -m venv (Join-Path $Root ".env")
}

if ($Install) {
    & $Python -m pip install -r $Requirements
}

& $Python -m pytest `
    -p no:cacheprovider `
    tests/test_reward_ledger.py `
    tests/regression/test_track_b_regression_agent.py

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($LiveBaseUrl -ne "") {
    & $Python (Join-Path $Root "scripts\track_b_live_smoke.py") $LiveBaseUrl
    exit $LASTEXITCODE
}

exit 0
