param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython) { $pythonRuntime = $venvPython }
elseif (Test-Path -LiteralPath $bundledPython) { $pythonRuntime = $bundledPython }
else { $pythonRuntime = (Get-Command python -ErrorAction Stop).Source }
Write-Host "ClaimLedger: http://127.0.0.1:$Port"
Write-Host 'Keep this terminal open. Press Ctrl+C to stop safely.'
& $pythonRuntime (Join-Path $projectRoot 'server.py') --port $Port
