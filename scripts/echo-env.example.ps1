# Copy to .echo-env.ps1 and edit paths if needed. Paths only; never put secrets here.
$androidBase=if(Test-Path 'F:\'){'F:\Android'}else{Join-Path $env:LOCALAPPDATA 'Echo\Android'}
$echoBase=if(Test-Path 'F:\'){'F:\Android'}else{Join-Path $env:LOCALAPPDATA 'Echo'}
$env:ECHO_ANDROID_SDK_ROOT=Join-Path $androidBase 'Sdk'
$env:ECHO_GRADLE_USER_HOME=Join-Path $androidBase 'Gradle_Home'
$env:ECHO_GRADLE_INSTALL_ROOT=Join-Path $androidBase 'Gradle'
$env:ECHO_JDK_ROOT=Join-Path $androidBase 'Jdk17'
$env:ECHO_TEMP_ROOT=if(Test-Path 'F:\'){'F:\Temp'}else{Join-Path $echoBase 'Temp'}
$env:ECHO_BUILD_ROOT=Join-Path $androidBase 'Build\EchoPhone'
$env:ECHO_KOKORO_ROOT=Join-Path $echoBase 'KokoroVoice'
$env:ECHO_VOICE_STATE_ROOT=Join-Path $echoBase 'EchoVoice'
Write-Host 'Echo local paths loaded for this PowerShell session.'
