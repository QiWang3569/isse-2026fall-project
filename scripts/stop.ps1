$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectDir 'data/server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No Yandu server PID file found.'; exit 0 }
$serverPid = [int](Get-Content -LiteralPath $pidFile -Raw).Trim()
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid"
if (-not $process) { Write-Host 'Yandu is already stopped.'; exit 0 }
$expectedPython = [System.IO.Path]::GetFullPath((Join-Path $projectDir '.venv/Scripts/python.exe'))
if ($process.ExecutablePath -ne $expectedPython -or $process.CommandLine -notmatch 'uvicorn.*app.main:app') {
    throw 'The saved PID no longer belongs to this project. No process was stopped.'
}
# A Windows venv launcher can have a child interpreter that owns the socket.
$children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $serverPid")
foreach ($child in $children) {
    if ($child.CommandLine -match 'uvicorn.*app.main:app') { Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue }
}
Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
Write-Host 'Yandu stopped. All saved data has been retained.'
