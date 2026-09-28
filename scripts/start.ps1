param([ValidateRange(1024,65535)][int]$Port = 8000, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir
$pythonPath = [System.IO.Path]::GetFullPath((Join-Path $projectDir '.venv/Scripts/python.exe'))
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run .\scripts\setup.ps1 first.' }
if (-not $SkipBuild -or -not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
    Push-Location -LiteralPath frontend
    try { npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
    finally { Pop-Location }
}
$listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($listeners.Count -gt 0) {
    $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $($listeners[0].OwningProcess)"
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($existing.ParentProcessId)"
    $isProjectProcess = $existing.ExecutablePath -eq $pythonPath -or ($parent -and $parent.ExecutablePath -eq $pythonPath -and $parent.CommandLine -match 'uvicorn.*app.main:app')
    if ($isProjectProcess -and $existing.CommandLine -match 'uvicorn.*app.main:app') {
        Write-Host "Yandu is already running at http://127.0.0.1:$Port"
        exit 0
    }
    throw "Port $Port is in use by another application. Choose -Port <number>."
}
New-Item -ItemType Directory -Path data -Force | Out-Null
if ($Port -ne 8000) {
    $baseOrigins = if ($env:ALLOWED_ORIGINS) { $env:ALLOWED_ORIGINS } else { 'http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5173,http://localhost:5173' }
    $env:ALLOWED_ORIGINS = "$baseOrigins,http://127.0.0.1:$Port,http://localhost:$Port"
}
$server = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $projectDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectDir 'data/server.log') -RedirectStandardError (Join-Path $projectDir 'data/server-error.log')
$server.Id | Set-Content -LiteralPath 'data/server.pid'
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/health" -TimeoutSec 1
        if ($health.status -eq 'ok') { Write-Host "Yandu is running at http://127.0.0.1:$Port"; exit 0 }
    } catch { Start-Sleep -Milliseconds 300 }
}
throw 'Startup did not complete. Read data/server-error.log for details.'
