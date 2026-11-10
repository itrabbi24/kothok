$ErrorActionPreference = 'Stop'
$exe = Join-Path $PSScriptRoot 'dist\Kothok\Kothok.exe'
if (-not (Test-Path $exe)) { throw 'Build the portable app first with .\build-portable.ps1' }
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'Kothok.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = Split-Path $exe
$shortcut.Description = 'Kothok - offline Bangla + English voice typing'
$shortcut.Save()
Write-Host "Startup shortcut installed: $shortcutPath"
