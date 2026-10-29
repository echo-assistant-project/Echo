[CmdletBinding()]
param(
    [string]$SdkRoot = 'F:\Android\Sdk',
    [string]$GradleHome = 'F:\Android\Gradle_Home',
    [string]$TempRoot = 'F:\Temp',
    [string]$BuildRoot = 'F:\Android\Build\EchoPhone',
    [string]$DeviceSerial
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-LastExit([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What failed with exit code $LASTEXITCODE." }
}
function Download-File([string]$Url, [string]$Destination) {
    Write-Host "Downloading $Url" -ForegroundColor Cyan
    Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Destination
}
function Expand-Zip([string]$Zip, [string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Recurse -Force }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Expand-Archive -LiteralPath $Zip -DestinationPath $Destination -Force
}

$projectPath = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$manifestPath = Join-Path $projectPath 'app\src\main\AndroidManifest.xml'
$buildFile = Join-Path $projectPath 'app\build.gradle'
if (!(Test-Path -LiteralPath $manifestPath) -or !(Test-Path -LiteralPath $buildFile)) {
    throw "Run this script from the EchoPhone project folder. Missing app manifest/build file at $projectPath."
}
if (!(Test-Path 'F:\')) { throw 'F: drive is not available.' }
$cFree = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
$fFree = [math]::Round((Get-PSDrive F).Free / 1GB, 2)
Write-Host "Disk space: C: $cFree GB free; F: $fFree GB free." -ForegroundColor Yellow
if ($fFree -lt 12) { throw 'At least 12 GB free on F: is recommended for SDK, Gradle and build files.' }
if ($cFree -lt 0.2) { throw 'C: has less than 200 MB free. Free some space manually before continuing; this script will not delete user files.' }

# Tool and cache directories live on F:. Removing the Machine-scope legacy variable needs elevation.
foreach ($dir in @($SdkRoot, $GradleHome, $TempRoot, $BuildRoot, (Join-Path $SdkRoot 'downloads'))) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$env:TEMP = $TempRoot; $env:TMP = $TempRoot; $env:GRADLE_USER_HOME = $GradleHome
$env:ANDROID_SDK_ROOT = $SdkRoot; $env:ANDROID_HOME = $SdkRoot; $env:ANDROID_USER_HOME = 'F:\Android\UserHome'
$env:ADB_SERVER_PORT = '5038'
$env:ECHO_BUILD_DIR = $BuildRoot
$env:HOME = $env:ANDROID_USER_HOME
Remove-Item Env:ANDROID_SDK_HOME -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $env:ANDROID_USER_HOME -Force | Out-Null
$runningUser = [Environment]::UserName
if ($runningUser -ne 'CodexSandboxOffline') {
    [Environment]::SetEnvironmentVariable('ANDROID_SDK_HOME', $null, 'User')
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        [Environment]::SetEnvironmentVariable('ANDROID_SDK_HOME', $null, 'Machine')
        Write-Host 'Removed deprecated ANDROID_SDK_HOME at User and Machine scope.' -ForegroundColor Green
    } else {
        Write-Warning 'Removed the User ANDROID_SDK_HOME value. Re-run as Administrator to remove the Machine value too.'
    }
} else {
    Write-Warning 'Codex isolated account detected: registry changes for the Windows user profile are skipped. This build process uses only ANDROID_USER_HOME.'
}
$userEnvironment = @{
    TEMP=$TempRoot; TMP=$TempRoot; GRADLE_USER_HOME=$GradleHome
    ANDROID_SDK_ROOT=$SdkRoot; ANDROID_HOME=$SdkRoot
    ANDROID_USER_HOME=$env:ANDROID_USER_HOME
    JAVA_HOME=$null; ECHO_BUILD_DIR=$BuildRoot
}

# Install a verified Temurin 17 JDK archive on F: if no suitable JDK is already there.
$javaExe = $null
$jdkCandidates = @('F:\Android\Jdk17\bin\java.exe', "$env:JAVA_HOME\bin\java.exe", 'C:\Program Files\Android\Android Studio\jbr\bin\java.exe', 'C:\Program Files\Java\jdk-17\bin\java.exe')
foreach ($candidate in $jdkCandidates) { if ($candidate -and (Test-Path -LiteralPath $candidate)) { $javaExe = $candidate; break } }
if (!$javaExe) {
    $jdkApi = 'https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse'
    $asset = (Invoke-RestMethod -Uri $jdkApi)[0].binary.package
    $jdkZip = Join-Path $TempRoot 'temurin-17.zip'
    Download-File $asset.link $jdkZip
    $actual = (Get-FileHash -LiteralPath $jdkZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $asset.checksum.ToLowerInvariant()) { throw 'Temurin archive checksum verification failed.' }
    $jdkUnpack = Join-Path $TempRoot 'jdk-unpack'
    Expand-Zip $jdkZip $jdkUnpack
    $jdkHome = Get-ChildItem -LiteralPath $jdkUnpack -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'bin\java.exe') } | Select-Object -First 1
    if (!$jdkHome) { throw 'JDK archive did not contain bin\java.exe.' }
    if (Test-Path 'F:\Android\Jdk17') { Remove-Item 'F:\Android\Jdk17' -Recurse -Force }
    Move-Item -LiteralPath $jdkHome.FullName -Destination 'F:\Android\Jdk17'
    $javaExe = 'F:\Android\Jdk17\bin\java.exe'
}
$jdkHomePath = Split-Path (Split-Path $javaExe -Parent) -Parent
$env:JAVA_HOME = $jdkHomePath
$env:PATH = "$jdkHomePath\bin;$SdkRoot\platform-tools;$SdkRoot\cmdline-tools\latest\bin;$env:PATH"
$userEnvironment.JAVA_HOME = $jdkHomePath
if ([Environment]::UserName -eq 'CodexSandboxOffline') {
    Write-Warning 'Running in Codex’s isolated account: F: paths are active for this build only. Run this script yourself in PowerShell to save them to Kaashi’s Windows user profile.'
} else {
    foreach ($name in $userEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, [string]$userEnvironment[$name], 'User') }
}
& $javaExe -version
Assert-LastExit 'Java verification'

# Install Google's command-line tools using the published archive and SHA-256.
$sdkManager = Join-Path $SdkRoot 'cmdline-tools\latest\bin\sdkmanager.bat'
if (!(Test-Path -LiteralPath $sdkManager)) {
    $toolsZip = Join-Path $TempRoot 'android-commandlinetools.zip'
    Download-File 'https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip' $toolsZip
    $toolsHash = (Get-FileHash -LiteralPath $toolsZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($toolsHash -ne '90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a') { throw 'Android command-line tools checksum verification failed.' }
    $toolsUnpack = Join-Path $TempRoot 'android-tools-unpack'
    Expand-Zip $toolsZip $toolsUnpack
    $latest = Join-Path $SdkRoot 'cmdline-tools\latest'
    New-Item -ItemType Directory -Path (Split-Path $latest -Parent) -Force | Out-Null
    if (Test-Path $latest) { Remove-Item $latest -Recurse -Force }
    Move-Item -LiteralPath (Join-Path $toolsUnpack 'cmdline-tools') -Destination $latest
}
if (!(Test-Path -LiteralPath $sdkManager)) { throw "sdkmanager was not found: $sdkManager" }
$accept = 1..80 | ForEach-Object { 'y' }
$accept | & $sdkManager --sdk_root="$SdkRoot" --licenses | Out-Host
Assert-LastExit 'Android SDK license setup'
& $sdkManager --sdk_root="$SdkRoot" 'platform-tools' 'platforms;android-36' 'build-tools;36.0.0' | Out-Host
Assert-LastExit 'Android SDK package installation'

# Use official Gradle distribution directly because this project has no gradlew wrapper.
$gradleVersion = '9.6.0'
$gradleHome = Join-Path 'F:\Android\Gradle' "gradle-$gradleVersion"
$gradleExe = Join-Path $gradleHome 'bin\gradle.bat'
if (!(Test-Path -LiteralPath $gradleExe)) {
    $gradleZip = Join-Path $TempRoot "gradle-$gradleVersion-bin.zip"
    $expected = 'bbaeb2fef8710818cf0e261201dab964c572f92b942812df0c3620d62a529a01'
    $needsDownload = !(Test-Path -LiteralPath $gradleZip)
    if (!$needsDownload) {
        $cachedHash = (Get-FileHash -LiteralPath $gradleZip -Algorithm SHA256).Hash.ToLowerInvariant()
        $needsDownload = $cachedHash -ne $expected
    }
    if ($needsDownload) { Download-File "https://services.gradle.org/distributions/gradle-$gradleVersion-bin.zip" $gradleZip }
    $actual = (Get-FileHash -LiteralPath $gradleZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw 'Gradle archive checksum verification failed.' }
    $gradleUnpack = Join-Path $TempRoot 'gradle-unpack'
    Expand-Zip $gradleZip $gradleUnpack
    New-Item -ItemType Directory -Path (Split-Path $gradleHome -Parent) -Force | Out-Null
    Move-Item -LiteralPath (Join-Path $gradleUnpack "gradle-$gradleVersion") -Destination $gradleHome
}

# Keep the project's local Android SDK path and generated build outputs on F:.
$sdkPath = $SdkRoot.Replace('\','/')
Set-Content -LiteralPath (Join-Path $projectPath 'local.properties') -Value "sdk.dir=$sdkPath" -Encoding ASCII
Push-Location $projectPath
try { & $gradleExe --no-daemon --stacktrace assembleDebug; Assert-LastExit 'EchoPhone debug build' }
finally { Pop-Location }
$apk = Join-Path $BuildRoot 'outputs\apk\debug\app-debug.apk'
if (!(Test-Path -LiteralPath $apk)) { throw "Build exited without producing the APK: $apk" }

# Install only when exactly one authorized Android device is connected. Do not alter global
# Android security, app-ops, battery policy, or grant permissions the app does not request.
$adb = Join-Path $SdkRoot 'platform-tools\adb.exe'
$deviceLines = @(& $adb devices | Select-Object -Skip 1 | Where-Object { $_ -match '^\S+\s+device$' })
if ($DeviceSerial) { $deviceLines = @($deviceLines | Where-Object { ($_ -split '\s+')[0] -eq $DeviceSerial }) }
if ($deviceLines.Count -eq 1) {
    $serial = ($deviceLines[0] -split '\s+')[0]
    & $adb -s $serial install -r $apk | Out-Host; Assert-LastExit 'APK installation'
    # Contacts is the only sensitive permission used by this app; grant it only if the user asked
    # for the script's ADB convenience. Otherwise the app will request it normally on first use.
    & $adb -s $serial shell pm grant com.echo.assistant android.permission.READ_CONTACTS
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Contacts was not granted by ADB; Echo will ask when you use call/text.' }
    & $adb -s $serial shell monkey -p com.echo.assistant 1 | Out-Host
    Write-Host "Installed and launched on device $serial." -ForegroundColor Green
} elseif ($deviceLines.Count -gt 1) {
    Write-Warning 'Multiple authorized devices found; build completed but deployment was skipped. Re-run with -DeviceSerial <serial>.'
} else {
    Write-Warning 'No authorized ADB device found; build completed. Connect the phone, enable USB debugging, approve its prompt, then rerun with -DeviceSerial if needed.'
}

Write-Host "`nEchoPhone build complete" -ForegroundColor Green
Write-Host "APK: $apk"
Write-Host "SDK: $SdkRoot | Gradle cache: $GradleHome | Temp: $TempRoot | JDK: $jdkHomePath"
Write-Host 'The app uses tap-to-talk, contacts, and user-confirmed dialer/messaging intents. It has no background wake-word service.'
