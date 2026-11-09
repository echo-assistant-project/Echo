# Starts EchoGestures (webcam hand gestures for Echo). First run creates a private Python environment with
# MediaPipe + OpenCV under %LOCALAPPDATA%\EchoAndroid\EchoGestures (nothing is installed system-wide).
param([int]$Camera = 0, [string]$DevRoot = (Join-Path $env:LOCALAPPDATA 'EchoAndroid'), [switch]$SetupOnly)
$ErrorActionPreference = 'Stop'
$home_ = Join-Path $DevRoot 'EchoGestures'
$python = Join-Path $home_ 'venv\Scripts\python.exe'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path $python)) {
    New-Item -ItemType Directory -Force $home_ | Out-Null
    py -3.12 -m venv (Join-Path $home_ 'venv')
    & $python -m pip install --disable-pip-version-check -q -r (Join-Path $here 'requirements.txt')
}
if ($SetupOnly) { Write-Host 'Hand gestures are set up.'; exit 0 }
& $python (Join-Path $here 'echo_gestures.py') $Camera
