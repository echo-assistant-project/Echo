# Generated-audio grammar test. Does not open a microphone or play audio.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$helper = Join-Path $repo 'desktop\EchoDesktop\echo_desktop\helpers\speech.ps1'
$tokens = $null
$errors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'The local speech helper has syntax errors.' }
$text = Get-Content -LiteralPath $helper -Raw
$wake = $text.Substring($text.IndexOf("'wake' {"))
$grammar = [regex]::Match($wake, 'New-Engine @\(([^)]+)\)').Groups[1].Value
$phrases = [string[]]@([regex]::Matches($grammar, "'([^']+)'") | ForEach-Object { $_.Groups[1].Value })
if ($phrases -notcontains 'echo') { throw 'The standalone ECHO phrase is missing.' }
Add-Type -AssemblyName System.Speech
$sample = Join-Path ([IO.Path]::GetTempPath()) ('echo-wake-' + [guid]::NewGuid().ToString('N') + '.wav')
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
try {
    $synth.SetOutputToWaveFile($sample)
    $synth.Speak('Echo')
    $synth.SetOutputToNull()
    $choices = New-Object System.Speech.Recognition.Choices
    $choices.Add($phrases)
    $builder = New-Object System.Speech.Recognition.GrammarBuilder
    $builder.Culture = $engine.RecognizerInfo.Culture
    $builder.Append($choices)
    $engine.LoadGrammar((New-Object System.Speech.Recognition.Grammar($builder)))
    $engine.SetInputToWaveFile($sample)
    $result = $engine.Recognize([TimeSpan]::FromSeconds(5))
    if (-not $result -or $result.Text.ToLowerInvariant() -ne 'echo' -or $result.Confidence -lt 0.6) {
        throw 'Generated ECHO audio did not meet the existing wake confidence threshold.'
    }
    Write-Output 'PASS local ECHO wake grammar, generated audio and confidence threshold'
} finally {
    $synth.Dispose()
    $engine.Dispose()
    if (Test-Path -LiteralPath $sample) { Remove-Item -LiteralPath $sample -Force }
}
