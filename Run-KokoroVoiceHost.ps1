[CmdletBinding()]
param([string]$VoiceRoot,[string]$StateRoot,[string]$TempRoot)
$ErrorActionPreference='Stop'
$localEchoRoot=Join-Path $env:LOCALAPPDATA 'Echo'
$defaultBase=if(Test-Path -LiteralPath 'F:\'){'F:\Android'}else{$localEchoRoot}
if(!$VoiceRoot){$VoiceRoot=if($env:ECHO_KOKORO_ROOT){$env:ECHO_KOKORO_ROOT}else{Join-Path $defaultBase 'KokoroVoice'}}
if(!$StateRoot){$StateRoot=if($env:ECHO_VOICE_STATE_ROOT){$env:ECHO_VOICE_STATE_ROOT}else{Join-Path $defaultBase 'EchoVoice'}}
if(!$TempRoot){$TempRoot=if($env:ECHO_TEMP_ROOT){Join-Path $env:ECHO_TEMP_ROOT 'KokoroVoice'}elseif(Test-Path -LiteralPath 'F:\'){'F:\Temp\KokoroVoice'}else{Join-Path $localEchoRoot 'Temp\KokoroVoice'}}
$python=Join-Path $VoiceRoot 'venv\Scripts\python.exe'
$server=Join-Path $PSScriptRoot 'tools\KokoroVoice\server.py'
$cert=Join-Path $StateRoot 'server-cert.pem'; $keyFile=Join-Path $StateRoot 'server-key.pem'; $tokenFile=Join-Path $StateRoot 'api-key.txt'
if(!(Test-Path $python) -or !(Test-Path $server) -or !(Test-Path $cert) -or !(Test-Path $keyFile) -or !(Test-Path $tokenFile)){throw 'Run Setup-KokoroVoice.ps1 first.'}
New-Item -ItemType Directory -Force -Path $TempRoot|Out-Null
$env:TEMP=$TempRoot; $env:TMP=$TempRoot
$env:ECHO_VOICE_API_KEY=(Get-Content -LiteralPath $tokenFile -Raw).Trim()
$env:ECHO_VOICE_CERT_FILE=$cert; $env:ECHO_VOICE_KEY_FILE=$keyFile
$env:ECHO_KOKORO_MODEL=Join-Path $VoiceRoot 'models\kokoro-v1.0.int8.onnx'
$env:ECHO_KOKORO_VOICES=Join-Path $VoiceRoot 'models\voices-v1.0.bin'
try{& $python $server; if($LASTEXITCODE -ne 0){throw "Kokoro voice host stopped with code $LASTEXITCODE."}}
finally{Remove-Item Env:ECHO_VOICE_API_KEY,Env:ECHO_VOICE_CERT_FILE,Env:ECHO_VOICE_KEY_FILE,Env:ECHO_KOKORO_MODEL,Env:ECHO_KOKORO_VOICES -ErrorAction SilentlyContinue}