# Windows Hello check for Echo's vault (face, fingerprint or Windows Hello PIN).
#   hello.ps1 -Check            prints AVAILABLE / NOTSETUP / UNAVAILABLE (no prompt)
#   hello.ps1 -Message "..."    shows the Windows Security prompt; prints VERIFIED / CANCELED / FAILED / UNAVAILABLE
param([switch]$Check, [string]$Message = "Echo wants to use a saved secret.")
$ErrorActionPreference = 'Stop'
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Security.Credentials.UI.UserConsentVerifier, Windows.Security.Credentials.UI, ContentType = WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } |
        Select-Object -First 1
    function Await($op, [Type]$type) {
        $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
        $null = $task.Wait(-1)
        $task.Result
    }
    $avail = Await ([Windows.Security.Credentials.UI.UserConsentVerifier]::CheckAvailabilityAsync()) ([Windows.Security.Credentials.UI.UserConsentVerifierAvailability])
    if ($Check) {
        switch ("$avail") { 'Available' { 'AVAILABLE' } 'NotConfiguredForUser' { 'NOTSETUP' } default { 'UNAVAILABLE' } }
        exit 0
    }
    if ("$avail" -ne 'Available') { 'UNAVAILABLE'; exit 0 }
    $result = Await ([Windows.Security.Credentials.UI.UserConsentVerifier]::RequestVerificationAsync($Message)) ([Windows.Security.Credentials.UI.UserConsentVerificationResult])
    switch ("$result") { 'Verified' { 'VERIFIED' } 'Canceled' { 'CANCELED' } default { 'FAILED' } }
} catch {
    'UNAVAILABLE'
}
