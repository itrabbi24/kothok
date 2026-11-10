$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
  Write-Host 'Virtual environment not found. Run setup commands from README.md first.'
  exit 1
}
& $python (Join-Path $PSScriptRoot 'app.py')
