$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $appRoot 'dist/Lingyezhou/Lingyezhou.exe'
$startup = Join-Path $appRoot 'output/exe-startup.json'
$offline = Join-Path $appRoot 'output/exe-offline.json'
$audio = Join-Path $appRoot 'output/runtime-smoke/example_16k.wav'

$startupProcess = Start-Process -FilePath $exe -ArgumentList @('--self-test-report', $startup) -WindowStyle Hidden -Wait -PassThru
if ($startupProcess.ExitCode -ne 0) { throw 'Startup self-test failed' }

$offlineProcess = Start-Process -FilePath $exe -ArgumentList @(
    '--self-test-report', $offline,
    '--smoke-engine', 'whisper',
    '--smoke-audio', $audio
) -WindowStyle Hidden -Wait -PassThru
if ($offlineProcess.ExitCode -ne 0) { throw 'Whisper self-test failed' }

Get-Content -LiteralPath $offline -Encoding UTF8
