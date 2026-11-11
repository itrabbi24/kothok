# Builds the portable app:  dist\Kothok\Kothok.exe  (+ models)  and  dist\Kothok-portable.zip
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run .\setup.ps1 first.' }
& $python -m pip install -q pyinstaller
& $python tools\make_assets.py
& $python tools\make_splash.py   # startup banner shows the version number
Copy-Item assets\kothok.ico app.ico -Force
# Old build used: PyInstaller --onedir --noconsole --name BanglaVoiceToText app.py  (see legacy/)
& $python -m PyInstaller --noconfirm --clean Kothok.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$dist = Join-Path $PSScriptRoot 'dist\Kothok'
# 'whisper' (turbo, 1 GB) no longer shipped
foreach ($m in 'bn', 'lid') {
  $src = Join-Path $PSScriptRoot "models\$m"
  if (Test-Path $src) {
    New-Item -ItemType Directory -Force -Path "$dist\models\$m" | Out-Null
    Copy-Item "$src\*" "$dist\models\$m" -Force
  } else { Write-Warning "models\$m not found - run .\download-model.ps1" }
}
Copy-Item README.md $dist -Force
$zip = Join-Path $PSScriptRoot 'dist\Kothok-portable.zip'
if (Test-Path $zip) { Remove-Item $zip -Force }
# Compress-Archive failed on locked files (AV scanning) - tar.exe ships with Windows 10+
# Compress-Archive -Path $dist -DestinationPath $zip -CompressionLevel Optimal
foreach ($f in 'app.log', 'config.json') { $p = Join-Path $dist $f; if (Test-Path $p) { Remove-Item $p -Force } }
Push-Location (Join-Path $PSScriptRoot 'dist')
tar.exe -a -c -f 'Kothok-portable.zip' 'Kothok'
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { throw "zip failed ($code)" }
# App-only zip for the in-app auto updater (models never change between releases)
$stage = Join-Path $PSScriptRoot 'build\update'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
robocopy $dist (Join-Path $stage 'Kothok') /E /XD models /NFL /NDL /NJH /NJS | Out-Null
$upd = Join-Path $PSScriptRoot 'dist\Kothok-update.zip'
if (Test-Path $upd) { Remove-Item $upd -Force }
Push-Location $stage
tar.exe -a -c -f $upd 'Kothok'
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { throw "update zip failed ($code)" }
Write-Host "Done: $dist\Kothok.exe"
Write-Host "Updater asset: $upd"
Write-Host "Share: $zip  (unzip anywhere, run Kothok.exe - no install, no internet)"
