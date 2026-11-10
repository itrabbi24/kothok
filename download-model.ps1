# Downloads the offline speech models into .\models
#   .\download-model.ps1                 -> both models
#   .\download-model.ps1 -Engine bangla  -> only the fast Bangla streaming model (~90 MB)
#   .\download-model.ps1 -Engine english -> only the small English/language-detect model (~160 MB)
# (Whisper Turbo was dropped: it cannot write Bangla correctly in sherpa-onnx - see app.py WhisperEngine)
param([ValidateSet('all', 'bangla', 'english')][string]$Engine = 'all')
$ErrorActionPreference = 'Stop'
$base = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models'
$models = Join-Path $PSScriptRoot 'models'
New-Item -ItemType Directory -Force -Path $models | Out-Null

function Get-Model($archiveName, $destName, $files) {
  $dest = Join-Path $models $destName
  if ((Test-Path $dest) -and (Get-ChildItem $dest -Filter *.onnx -ErrorAction SilentlyContinue)) {
    Write-Host "$destName already installed - skipping"; return
  }
  $archive = Join-Path $env:TEMP "$archiveName.tar.bz2"; $tmp = Join-Path $models 'extract'
  Write-Host "Downloading $archiveName (one time)..."
  curl.exe -L --fail --output $archive "$base/$archiveName.tar.bz2"
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null; tar -xjf $archive -C $tmp
  $source = Get-ChildItem $tmp -Directory | Select-Object -First 1
  New-Item -ItemType Directory -Force -Path $dest | Out-Null
  foreach ($pattern in $files) { Get-ChildItem $source.FullName -Filter $pattern | Copy-Item -Destination $dest -Force }
  Remove-Item $archive -Force; Remove-Item $tmp -Recurse -Force
  Write-Host "Installed models\$destName"
}

if ($Engine -in 'all', 'bangla') {
  Get-Model 'sherpa-onnx-streaming-zipformer-bn-vosk-2026-02-09' 'bn' @('encoder.onnx', 'decoder.onnx', 'joiner.onnx', 'tokens.txt')
}
# Disabled - old Bangla+English engine (turbo, ~1 GB):
# if ($Engine -in 'all', 'whisper') {
#   Get-Model 'sherpa-onnx-whisper-turbo' 'whisper' @('*encoder.int8.onnx', '*decoder.int8.onnx', '*tokens.txt')
# }
if ($Engine -in 'all', 'english') {
  # whisper base (multilingual) - detects English phrases and writes them; int8 files only
  Get-Model 'sherpa-onnx-whisper-base' 'lid' @('*encoder.int8.onnx', '*decoder.int8.onnx', '*tokens.txt')
}
