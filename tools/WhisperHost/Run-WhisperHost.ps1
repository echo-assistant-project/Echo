# Starts the Echo Whisper speech-recognition host on 127.0.0.1:31417 (first run: sets it up).
# Usage:  powershell -ExecutionPolicy Bypass -File tools\WhisperHost\Run-WhisperHost.ps1 [-Model small.en] [-Setup]
# Everything lives in %LOCALAPPDATA%\EchoAndroid\WhisperHost (venv, models, certificate, pairing.json); nothing in Git.
# -Backend auto (default): the Intel GPU (OpenVINO, small.en: fastest; -Model large-v3-turbo for accuracy) when Setup-OpenVino.ps1 has been run, else
# faster-whisper on the CPU.
param(
    [string]$Model = '',
    [switch]$Setup,
    [switch]$SetupOnly,      # set everything up, then stop (Echo's setup app uses this; Echo starts the host itself)
    [ValidateSet('auto', 'openvino', 'faster-whisper')][string]$Backend = 'auto',
    [string]$DevRoot = (Join-Path $env:LOCALAPPDATA 'EchoAndroid')
)
$ErrorActionPreference = 'Stop'
$home_ = Join-Path $DevRoot 'WhisperHost'
$venv = Join-Path $home_ 'venv'
$python = Join-Path $venv 'Scripts\python.exe'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pairing = Join-Path $home_ 'pairing.json'

if (-not (Test-Path $python)) {
    New-Item -ItemType Directory -Force $home_ | Out-Null
    py -3.12 -m venv $venv
    & $python -m pip install --disable-pip-version-check -q -r (Join-Path $here 'requirements.txt')
}
if ($Setup -or -not (Test-Path $pairing) -or $Model) {
    $chosen = if ($Model) { $Model } else { 'small.en' }
    & $python (Join-Path $here 'setup_host.py') --home $home_ --model $chosen
    # The pairing file and private key are readable by the current user only.
    foreach ($secret in @($pairing, (Join-Path $home_ 'key.pem'))) {
        icacls $secret /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    }
}
if ($SetupOnly) { Write-Host 'Whisper is set up.'; exit 0 }
$p = Get-Content $pairing -Raw | ConvertFrom-Json
$env:ECHO_WHISPER_MODEL = $p.model
$env:ECHO_WHISPER_MODELS_DIR = Join-Path $home_ 'models'
$env:ECHO_WHISPER_API_KEY = $p.key
$env:ECHO_WHISPER_CERT_FILE = Join-Path $home_ 'cert.pem'
$env:ECHO_WHISPER_KEY_FILE = Join-Path $home_ 'key.pem'
$ovPython = Join-Path $DevRoot 'OpenVinoAsr\venv\Scripts\python.exe'
$ovName = if ($Model -match 'turbo') { 'whisper-large-v3-turbo-int8-ov' } else { 'whisper-small.en-int8-ov' }
if (-not (Test-Path (Join-Path $DevRoot "OpenVinoAsr\models\$ovName\openvino_encoder_model.xml"))) { $ovName = 'whisper-large-v3-turbo-int8-ov' }
$env:ECHO_OV_MODEL = $ovName
$ovModel = Join-Path $DevRoot "OpenVinoAsr\models\$ovName\openvino_encoder_model.xml"
if ($Backend -eq 'auto') { $Backend = if ((Test-Path $ovPython) -and (Test-Path $ovModel)) { 'openvino' } else { 'faster-whisper' } }
$env:ECHO_WHISPER_BACKEND = $Backend
if ($Backend -eq 'openvino') {
    if (-not (Test-Path $ovPython)) { throw 'Run tools\WhisperHost\Setup-OpenVino.ps1 first.' }
    & $ovPython (Join-Path $here 'server.py')
} else {
    & $python (Join-Path $here 'server.py')
}
