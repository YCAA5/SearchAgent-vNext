param([switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required to build the application.' }
}
& $python -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $python tools/build_icon.py
if (-not $SkipTests) {
    & $python -m pytest tests -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
}
& $python -m PyInstaller --noconfirm --clean SearchAgent.spec
if ($LASTEXITCODE -ne 0) { throw 'Windows application build failed.' }
Write-Output 'Application: dist\SearchAgent\SearchAgent.exe'
