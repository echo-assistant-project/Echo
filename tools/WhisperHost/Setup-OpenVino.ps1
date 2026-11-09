# One-time setup of the fast Intel-GPU speech recognizer (OpenVINO GenAI + Whisper small.en int8; -Model OpenVINO/whisper-large-v3-turbo-int8-ov for accuracy).
# Everything goes to %LOCALAPPDATA%\EchoAndroid\OpenVinoAsr; nothing in Git. Run-WhisperHost.ps1 uses it automatically.
param([string]$Model = 'OpenVINO/whisper-small.en-int8-ov')
$ErrorActionPreference = 'Stop'
$home_ = Join-Path $env:LOCALAPPDATA 'EchoAndroid\OpenVinoAsr'
$venv = Join-Path $home_ 'venv'
$python = Join-Path $venv 'Scripts\python.exe'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force $home_ | Out-Null
if (-not (Test-Path $python)) { py -3.12 -m venv $venv }
& $python -m pip install --disable-pip-version-check -q -r (Join-Path $here 'requirements-openvino.txt')
$dst = Join-Path $home_ ('models\' + $Model.Split('/')[1])
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
& $python -c "import sys; from huggingface_hub import snapshot_download; snapshot_download(sys.argv[1], local_dir=sys.argv[2])" $Model $dst
& $python -c "import openvino as ov; d = ov.Core().available_devices; print('Devices:', d); print('Intel GPU found.' if 'GPU' in d else 'No Intel GPU: it will run on the CPU (slower).')"
Write-Host "Done. Start the host with tools\WhisperHost\Run-WhisperHost.ps1 (it picks the Intel GPU automatically)."
