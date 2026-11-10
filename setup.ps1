$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3.12+ is required. Install Python, then run this script again.' }
if (-not (Test-Path (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))) {
  & $python.Source -m venv (Join-Path $PSScriptRoot '.venv')
}
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
Write-Host 'Virtual environment ready. Run .\download-model.ps1 once, then .\run.ps1.'
