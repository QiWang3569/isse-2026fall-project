param([string]$Python)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    if (-not $Python) {
        $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
        if (Test-Path -LiteralPath $bundledPython) { $Python = $bundledPython }
        elseif (Get-Command python -ErrorAction SilentlyContinue) { $Python = (Get-Command python).Source }
        else { throw 'Python 3.12+ is required. Run setup.ps1 -Python <path-to-python.exe>.' }
    }
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python virtual environment.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r backend/requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Push-Location -LiteralPath frontend
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Node dependency installation failed.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Ready. Run .\scripts\start.ps1 -SkipBuild'
