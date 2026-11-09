# Starts EchoDesktop (Python 3.12, standard library only). Runs in the background; quit from the orb's right-click menu.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = (Get-Command pyw.exe -ErrorAction SilentlyContinue).Source
if (-not $pyw) { throw 'The Python launcher (pyw.exe) was not found. Install Python 3.12 from python.org.' }
Start-Process -FilePath $pyw -ArgumentList '-3.12', '-m', 'echo_desktop' -WorkingDirectory $here
