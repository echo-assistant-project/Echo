# Opens the Echo voice test: a window that types whatever you say and can score its accuracy.
# Uses the Whisper host's Python when it exists (Whisper then runs inside the window), else Python 3.12.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $env:LOCALAPPDATA 'EchoAndroid\OpenVinoAsr\venv\Scripts\pythonw.exe'      # Intel GPU (fastest)
if (-not (Test-Path $venv)) { $venv = Join-Path $env:LOCALAPPDATA 'EchoAndroid\WhisperHost\venv\Scripts\pythonw.exe' }
Push-Location $here
try {
    if (Test-Path $venv) { & $venv -m echo_desktop.voicetest } else { pyw -3.12 -m echo_desktop.voicetest }
} finally { Pop-Location }
