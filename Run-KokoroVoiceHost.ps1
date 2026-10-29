$ErrorActionPreference = 'Stop'
$voiceRoot = 'F:\Android\KokoroVoice'
$state = 'F:\Android\EchoVoice'
$temp = 'F:\Temp\KokoroVoice'
$python = Join-Path $voiceRoot 'venv\Scripts\python.exe'
$server = Join-Path $PSScriptRoot 'tools\KokoroVoice\server.py'
$cert = Join-Path $state 'server-cert.pem'
$keyFile = Join-Path $state 'server-key.pem'
$tokenFile = Join-Path $state 'api-key.txt'
if (!(Test-Path $python) -or !(Test-Path $server) -or !(Test-Path $cert) -or !(Test-Path $keyFile) -or !(Test-Path $tokenFile)) {
    throw 'Run Setup-KokoroVoice.ps1 first.'
}
New-Item -ItemType Directory -Force -Path $temp | Out-Null
$env:TEMP = $temp
$env:TMP = $temp
$env:ECHO_VOICE_API_KEY = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
$env:ECHO_VOICE_CERT_FILE = $cert
$env:ECHO_VOICE_KEY_FILE = $keyFile
$env:ECHO_KOKORO_MODEL = Join-Path $voiceRoot 'models\kokoro-v1.0.int8.onnx'
$env:ECHO_KOKORO_VOICES = Join-Path $voiceRoot 'models\voices-v1.0.bin'
try {
    & $python $server
    if ($LASTEXITCODE -ne 0) { throw "Kokoro voice host stopped with code $LASTEXITCODE." }
}
finally {
    Remove-Item Env:ECHO_VOICE_API_KEY,Env:ECHO_VOICE_CERT_FILE,Env:ECHO_VOICE_KEY_FILE,Env:ECHO_KOKORO_MODEL,Env:ECHO_KOKORO_VOICES -ErrorAction SilentlyContinue
}
