[CmdletBinding()]
param([string]$VoiceRoot,[string]$StateRoot,[string]$TempRoot,[string]$PythonExe)
$ErrorActionPreference='Stop'
$localEchoRoot=Join-Path $env:LOCALAPPDATA 'Echo'
$defaultBase=if(Test-Path -LiteralPath 'F:\'){'F:\Android'}else{$localEchoRoot}
if(!$VoiceRoot){$VoiceRoot=if($env:ECHO_KOKORO_ROOT){$env:ECHO_KOKORO_ROOT}else{Join-Path $defaultBase 'KokoroVoice'}}
if(!$StateRoot){$StateRoot=if($env:ECHO_VOICE_STATE_ROOT){$env:ECHO_VOICE_STATE_ROOT}else{Join-Path $defaultBase 'EchoVoice'}}
if(!$TempRoot){$TempRoot=if($env:ECHO_TEMP_ROOT){Join-Path $env:ECHO_TEMP_ROOT 'KokoroSetup'}elseif(Test-Path -LiteralPath 'F:\'){'F:\Temp\KokoroSetup'}else{Join-Path $localEchoRoot 'Temp\KokoroSetup'}}
$python=Join-Path $VoiceRoot 'venv\Scripts\python.exe'
$pythonBase=$null; $pythonBaseArgs=@()
if($PythonExe){$pythonBase=$PythonExe}
else{
 $pyLauncher=Get-Command py -ErrorAction SilentlyContinue
 if($pyLauncher){$testVersion=& $pyLauncher.Source -3.12 --version 2>&1; if($LASTEXITCODE -eq 0){$pythonBase=$pyLauncher.Source; $pythonBaseArgs=@('-3.12')}}
 if(!$pythonBase){$pythonCommand=Get-Command python -ErrorAction SilentlyContinue; if($pythonCommand){$testVersion=& $pythonCommand.Source --version 2>&1; if("$testVersion" -match 'Python 3\.12\.'){$pythonBase=$pythonCommand.Source}}}
}
if(!$pythonBase){throw 'Python 3.12 was not found. Install it or pass -PythonExe with the Python 3.12 executable path.'}
$versionOutput=& $pythonBase @pythonBaseArgs --version 2>&1
if("$versionOutput" -notmatch 'Python 3\.12\.') {throw 'Kokoro requires Python 3.12. Install it or pass -PythonExe with that version.'}
$requirements=Join-Path $PSScriptRoot 'tools\KokoroVoice\requirements.txt'
$modelDir=Join-Path $VoiceRoot 'models'
$model=Join-Path $modelDir 'kokoro-v1.0.int8.onnx'
$voices=Join-Path $modelDir 'voices-v1.0.bin'
New-Item -ItemType Directory -Force -Path $VoiceRoot,$StateRoot,$TempRoot,$modelDir|Out-Null
$env:TEMP=$TempRoot; $env:TMP=$TempRoot
if(!(Test-Path $python)){& $pythonBase @pythonBaseArgs -m venv (Join-Path $VoiceRoot 'venv'); if($LASTEXITCODE -ne 0){throw 'Could not create the isolated Kokoro Python environment.'}}
& $python -m pip install --disable-pip-version-check --no-cache-dir -r $requirements
if($LASTEXITCODE -ne 0){throw 'Kokoro ONNX dependencies could not be installed.'}
$adbPath = if ($env:ECHO_ANDROID_SDK_ROOT) { Join-Path $env:ECHO_ANDROID_SDK_ROOT 'platform-tools\adb.exe' } else { (Get-Command adb -ErrorAction SilentlyContinue).Source }
if (!$adbPath) { $adbPath = 'adb' }
$assets = @(
    @{ Path=$model; Url='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.int8.onnx'; Bytes=114119327; Sha256='ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c' },
    @{ Path=$voices; Url='https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin'; Bytes=28214398; Sha256='bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d' }
)
foreach ($asset in $assets) {
    if (!(Test-Path $asset.Path)) { Invoke-WebRequest -UseBasicParsing -Uri $asset.Url -OutFile $asset.Path }
    if ((Get-Item $asset.Path).Length -ne $asset.Bytes) { throw "Unexpected model asset size: $($asset.Path)" }
    if ((Get-FileHash -LiteralPath $asset.Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset.Sha256) {
        throw "SHA-256 verification failed for $($asset.Path)"
    }
}

$certPem = Join-Path $StateRoot 'server-cert.pem'
$keyPem = Join-Path $StateRoot 'server-key.pem'
$publicCert = Join-Path $StateRoot 'server.cer'
$keyPath = Join-Path $StateRoot 'api-key.txt'
$regenerateCert = !(Test-Path $certPem) -or !(Test-Path $keyPem) -or !(Test-Path $publicCert)
if (!$regenerateCert) {
    $existing = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($publicCert)
    $sanExtension = $existing.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.17' } | Select-Object -First 1
    $regenerateCert = !$sanExtension -or $sanExtension.Format($false) -notmatch '127\.0\.0\.1'
    $existing.Dispose()
}
if ($regenerateCert) {
    foreach ($file in @($certPem,$keyPem,$publicCert)) { if(Test-Path $file){Remove-Item -LiteralPath $file -Force} }
    $rsa = [System.Security.Cryptography.RSA]::Create(2048)
    $request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
        'CN=Echo Kokoro Local',
        $rsa,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256,
        [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
    $san = [System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new()
    $san.AddDnsName('localhost')
    $san.AddIpAddress([Net.IPAddress]::Loopback)
    $request.CertificateExtensions.Add($san.Build())
    $request.CertificateExtensions.Add([System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false,$false,0,$true))
    $usage = [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature -bor [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyEncipherment
    $request.CertificateExtensions.Add([System.Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new($usage,$true))
    $oids = [System.Security.Cryptography.OidCollection]::new()
    [void]$oids.Add([System.Security.Cryptography.Oid]::new('1.3.6.1.5.5.7.3.1'))
    $request.CertificateExtensions.Add([System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new($oids,$false))
    $certificate = $request.CreateSelfSigned([DateTimeOffset]::UtcNow.AddMinutes(-5),[DateTimeOffset]::UtcNow.AddYears(5))
    [IO.File]::WriteAllBytes($publicCert,$certificate.RawData)
    [IO.File]::WriteAllText($certPem,$certificate.ExportCertificatePem(),[Text.Encoding]::ASCII)
    [IO.File]::WriteAllText($keyPem,$rsa.ExportPkcs8PrivateKeyPem(),[Text.Encoding]::ASCII)
    $certificate.Dispose()
    $rsa.Dispose()
}
if (!(Test-Path $keyPath)) {
    $bytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
    [IO.File]::WriteAllText($keyPath, [Convert]::ToBase64String($bytes), [Text.Encoding]::ASCII)
    [Array]::Clear($bytes, 0, $bytes.Length)
}
$pin = (Get-FileHash -LiteralPath $publicCert -Algorithm SHA256).Hash.ToLowerInvariant()
$plainKey = (Get-Content -LiteralPath $keyPath -Raw).Trim()
$pairing = Join-Path $StateRoot 'pairing.txt'
@(
    'EchoPhone Kokoro voice pairing (private; do not share)'
    'Endpoint: https://127.0.0.1:31416/v1/tts'
    ('ADB reverse command: ' + [char]34 + $adbPath + [char]34 + ' reverse tcp:31416 tcp:31416')
    "Bearer key: $plainKey"
    "Server certificate SHA-256: $pin"
    'Voice: Kokoro-82M af_heart'
    'The service binds only to 127.0.0.1. Do not forward the port on your router.'
) | Set-Content -LiteralPath $pairing -Encoding utf8
$plainKey = $null
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
foreach ($privateFile in @($keyPath,$keyPem,$pairing)) {
    & icacls.exe $privateFile /inheritance:r /grant:r "$($identity):(F)" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not restrict permissions on $privateFile" }
}



Write-Host 'Kokoro-82M af_heart is configured on F:.' -ForegroundColor Green
Write-Host "Pairing file: $pairing"
Write-Host 'Copy endpoint, bearer key, and certificate fingerprint into EchoPhone voice settings.'
Write-Host 'Then run Run-KokoroVoiceHost.ps1 and execute the ADB reverse command from pairing.txt.'
