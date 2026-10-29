$ErrorActionPreference = 'Stop'
$voiceRoot = 'F:\Android\KokoroVoice'
$state = 'F:\Android\EchoVoice'
$temp = 'F:\Temp\KokoroSetup'
$python = Join-Path $voiceRoot 'venv\Scripts\python.exe'
$pythonBase = 'C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.12_3.12.2800.0_x64__qbz5n2kfra8p0\python3.12.exe'
$requirements = Join-Path $PSScriptRoot 'tools\KokoroVoice\requirements.txt'
$modelDir = Join-Path $voiceRoot 'models'
$model = Join-Path $modelDir 'kokoro-v1.0.int8.onnx'
$voices = Join-Path $modelDir 'voices-v1.0.bin'
New-Item -ItemType Directory -Force -Path $voiceRoot,$state,$temp,$modelDir | Out-Null
$env:TEMP = $temp
$env:TMP = $temp
if (!(Test-Path $python)) {
    if (!(Test-Path $pythonBase)) { throw 'Python 3.12 was not found.' }
    & $pythonBase -m venv (Join-Path $voiceRoot 'venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated Kokoro Python environment.' }
}
& $python -m pip install --disable-pip-version-check --no-cache-dir -r $requirements
if ($LASTEXITCODE -ne 0) { throw 'Kokoro ONNX dependencies could not be installed.' }

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

$certPem = Join-Path $state 'server-cert.pem'
$keyPem = Join-Path $state 'server-key.pem'
$publicCert = Join-Path $state 'server.cer'
$keyPath = Join-Path $state 'api-key.txt'
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
$pairing = Join-Path $state 'pairing.txt'
@(
    'EchoPhone Kokoro voice pairing (private; do not share)'
    'Endpoint: https://127.0.0.1:31416/v1/tts'
    'ADB reverse command: F:\Android\Sdk\platform-tools\adb.exe reverse tcp:31416 tcp:31416'
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
