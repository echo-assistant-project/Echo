# EchoDesktop speech helper (Windows PowerShell 5.1, built-in System.Speech; no downloads).
# Modes:
#   listen  - recognise one utterance (dictation) and print it
#   wake    - listen continuously; print WAKE when "hey echo" (or similar) is heard
#   speak   - read text from stdin and speak it with the Windows voice
#   interrupt - while Echo talks: print STOP when the user says stop / wait / hold on (barge-in)
# listen prints up to five guesses, one per line: <confidence><TAB><text> (best first).
# Text to speak arrives on stdin only; nothing from the AI is ever placed on a command line.
#
# Speed: -Standby loads the voice/recogniser first and then waits for one stdin line ("go"; for speak: the rate)
# before doing anything, so EchoDesktop can keep one ready and skip ~0.4-0.6 s of start-up per reply or listen.
# The microphone is not attached until "go". -Stream (speak): every further stdin line is one sentence, spoken as it
# arrives, until stdin closes - Echo starts talking while the AI is still writing.
param(
    [ValidateSet('listen', 'wake', 'speak', 'interrupt')][string]$Mode = 'listen',
    [ValidateRange(-10, 10)][int]$Rate = 0,
    [ValidateRange(3, 30)][int]$TimeoutSeconds = 8,
    [switch]$Standby,
    [switch]$Stream
)
$ErrorActionPreference = 'Stop'
# ECHO_SPEECH_BENCH=1 (tools/SpeedBench only): no sound and no microphone (null output/input), and a marker line the
# moment speaking or listening begins, so start-up delays can be timed exactly.
$Bench = $env:ECHO_SPEECH_BENCH -eq '1'
function Mark([string]$What) { if ($Bench) { [Console]::Out.WriteLine($What); [Console]::Out.Flush() } }
Add-Type -AssemblyName System.Speech
[Console]::OutputEncoding = [Text.Encoding]::UTF8
[Console]::InputEncoding = [Text.Encoding]::UTF8

function Wait-Go {
    # Standby: everything is loaded; wait for EchoDesktop to say go. Closed stdin = not needed, exit quietly.
    if ($Standby) {
        [Console]::Out.WriteLine('WAITING'); [Console]::Out.Flush()     # loaded; EchoDesktop may hand us out now
        $line = [Console]::In.ReadLine()
        if ($null -eq $line) { exit 0 }
        return $line
    }
    return $null
}

function New-Engine([string[]]$Phrases) {
    # The microphone is attached later, after "go", so a waiting helper never holds it.
    $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    if ($Phrases) {
        $choices = New-Object System.Speech.Recognition.Choices
        $choices.Add($Phrases)
        $builder = New-Object System.Speech.Recognition.GrammarBuilder
        $builder.Append($choices)
        $engine.LoadGrammar((New-Object System.Speech.Recognition.Grammar($builder)))
    } else {
        $engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
    }
    return $engine
}

switch ($Mode) {
    'speak' {
        $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $female = $synth.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Gender -eq 'Female' -and $_.VoiceInfo.Culture.Name -like 'en-*' } | Select-Object -First 1
        if ($female) { $synth.SelectVoice($female.VoiceInfo.Name) }
        if ($Bench) { $synth.SetOutputToNull() } else { $synth.SetOutputToDefaultAudioDevice() }
        $synth.Rate = $Rate
        $go = Wait-Go
        if ($null -ne $go) {
            $r = 0
            if ([int]::TryParse($go.Trim(), [ref]$r)) { $synth.Rate = [Math]::Max(-10, [Math]::Min(10, $r)) }
        }
        if ($Stream) {
            $spoken = 0
            while ($null -ne ($line = [Console]::In.ReadLine())) {
                if ([string]::IsNullOrWhiteSpace($line) -or $spoken -ge 8000) { continue }
                $part = $line.Substring(0, [Math]::Min($line.Length, 2000))
                $spoken += $part.Length
                Mark 'SPEAKING'
                $synth.Speak($part)
            }
        } else {
            $text = [Console]::In.ReadToEnd()
            if (-not [string]::IsNullOrWhiteSpace($text)) { Mark 'SPEAKING'; $synth.Speak($text.Substring(0, [Math]::Min($text.Length, 4000))) }
        }
        $synth.Dispose()
    }
    'listen' {
        $engine = New-Engine $null
        $engine.InitialSilenceTimeout = [TimeSpan]::FromSeconds(5)
        $engine.EndSilenceTimeout = [TimeSpan]::FromSeconds(0.8)
        $null = Wait-Go
        if ($Bench) { $engine.SetInputToNull() } else { $engine.SetInputToDefaultAudioDevice() }
        Mark 'LISTENING'
        $result = $engine.Recognize([TimeSpan]::FromSeconds($TimeoutSeconds))
        if ($result -and $result.Text) {
            $seen = @{}
            foreach ($alt in @($result) + @($result.Alternates)) {
                if ($alt -and $alt.Text -and -not $seen.ContainsKey($alt.Text) -and $seen.Count -lt 5) {
                    $seen[$alt.Text] = 1
                    [Console]::Out.WriteLine(('{0:F3}' -f $alt.Confidence) + "`t" + $alt.Text)
                }
            }
        } else { [Console]::Out.WriteLine('') }
        $engine.Dispose()
    }
    'wake' {
        $engine = New-Engine @('echo', 'hey echo', 'hi echo', 'ok echo', 'okay echo', 'hello echo')
        $engine.SetInputToDefaultAudioDevice()
        [Console]::Out.WriteLine('READY'); [Console]::Out.Flush()
        while ($true) {
            $result = $engine.Recognize([TimeSpan]::FromSeconds(30))
            if ($result -and $result.Confidence -ge 0.6) { [Console]::Out.WriteLine('WAKE'); [Console]::Out.Flush() }
        }
    }
    'interrupt' {
        $engine = New-Engine @('stop', 'echo stop', 'okay stop', 'wait', 'hold on', 'wait a second', 'pause', 'enough', 'be quiet', 'never mind', 'excuse me', 'hey echo')
        $null = Wait-Go
        $engine.SetInputToDefaultAudioDevice()
        [Console]::Out.WriteLine('READY'); [Console]::Out.Flush()
        while ($true) {
            $result = $engine.Recognize([TimeSpan]::FromSeconds(30))
            # Higher bar than the wake word: Echo's own voice is playing through the speakers.
            if ($result -and $result.Confidence -ge 0.75) { [Console]::Out.WriteLine('STOP'); [Console]::Out.Flush() }
        }
    }
}
