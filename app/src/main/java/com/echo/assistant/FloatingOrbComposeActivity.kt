package com.echo.assistant
import android.Manifest
import android.media.MediaPlayer
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.File
import java.util.Locale

private enum class OrbMode { IDLE, LISTENING, THINKING, SPEAKING }

class FloatingOrbComposeActivity : ComponentActivity() {
    private lateinit var assistant: AssistantManager
    private lateinit var kokoroClient: KokoroVoiceClient
    private lateinit var modelPicker: ActivityResultLauncher<Array<String>>
    private lateinit var microphonePermission: ActivityResultLauncher<String>
    private var recognizer: SpeechRecognizer? = null
    private var mediaPlayer: MediaPlayer? = null

    private var promptText by mutableStateOf("")
    private var answerText by mutableStateOf("")
    private var visibleStatus by mutableStateOf("Checking PC brain…")
    private var errorText by mutableStateOf("")
    private var orbMode by mutableStateOf(OrbMode.IDLE)
    private var voiceSessionActive by mutableStateOf(false)
    private var useKokoroVoice by mutableStateOf(true)
    private var kokoroEndpoint by mutableStateOf(KokoroVoiceClient.DEFAULT_ENDPOINT)
    private var kokoroKey by mutableStateOf("")
    private var kokoroFingerprint by mutableStateOf("")
    private var androidVoiceNames by mutableStateOf(listOf<String>())
    private var selectedAndroidVoice by mutableStateOf("")
    private var pitch by mutableStateOf(1.0f)
    private var speechRate by mutableStateOf(0.9f)
    private var voiceMenuOpen by mutableStateOf(false)
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var connectionUrl by mutableStateOf("")
    private var connectionKey by mutableStateOf("")
    private var resumeAfterSpeech = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        assistant = AssistantManager(this)
        kokoroClient = KokoroVoiceClient(this)
        connectionUrl = assistant.endpoint
        connectionKey = assistant.apiKey
        val voicePrefs = getSharedPreferences("echo_voice", MODE_PRIVATE)
        useKokoroVoice = voicePrefs.getBoolean("use_kokoro_voice", true)
        selectedAndroidVoice = voicePrefs.getString("android_voice", "") ?: ""
        pitch = voicePrefs.getFloat("android_pitch", 1.0f).coerceIn(0.75f, 1.25f)
        speechRate = voicePrefs.getFloat("speech_rate", 0.9f).coerceIn(0.65f, 1.15f)

        kokoroEndpoint = kokoroClient.endpoint
        kokoroKey = kokoroClient.apiKey
        kokoroFingerprint = kokoroClient.certificateSha256
        microphonePermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted && voiceSessionActive) beginListening()
            else stopVoiceSession("Microphone permission is needed for voice conversation.")
        }
        modelPicker = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) lifecycleScope.launch {
                try {
                    visibleStatus = "Importing local model…"
                    assistant.importLocalModel(uri)
                    visibleStatus = assistant.uiState.value.message
                    errorText = ""
                } catch (e: Exception) {
                    errorText = e.message ?: "Could not import the model."
                    visibleStatus = "Model import failed."
                }
            }
        }
        configureEchoVoice()
        setContent {
            val connection by assistant.uiState.collectAsState()
            val online = connection.backend == AssistantManager.BackendState.PC_ONLINE
            val orbTint by animateColorAsState(
                targetValue = if (online) Color(0xFF42D9FF) else Color(0xFFFFB347), label = "backend-orb-color"
            )
            LaunchedConnectionRefresh()
            MaterialTheme {
                Surface(Modifier.fillMaxSize(), color = Color(0xFF07101C)) {
                    Column(
                        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(22.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text("E C H O", color = Color(0xFF83F5F2), style = MaterialTheme.typography.labelLarge)
                        Spacer(Modifier.height(14.dp))
                        Text("Your phone, hands-free.", color = Color.White, style = MaterialTheme.typography.headlineSmall)
                        Spacer(Modifier.height(8.dp))
                        Text(connection.message, color = if (online) Color(0xFF72E4FF) else Color(0xFFFFC66D),
                            textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyMedium)
                        if (!online && connection.backend == AssistantManager.BackendState.LOCAL_FALLBACK) {
                            Text("PC Brain is asleep. Running on local fallback.", color = Color(0xFFFFC66D), textAlign = TextAlign.Center)
                        }
                        Spacer(Modifier.height(18.dp))
                        PulsingOrb(
                            modifier = Modifier.size(180.dp), tint = orbTint, mode = orbMode,
                            onTap = { if (voiceSessionActive) stopVoiceSession() else startVoiceSession() }
                        )
                        Spacer(Modifier.height(12.dp))
                        Text(
                            when (orbMode) {
                                OrbMode.IDLE -> if (voiceSessionActive) "Voice session paused" else "Tap the orb to start talking"
                                OrbMode.LISTENING -> "Listening… tap Stop to end"
                                OrbMode.THINKING -> "Thinking…"
                                OrbMode.SPEAKING -> "Echo is speaking"
                            }, color = orbTint, textAlign = TextAlign.Center
                        )
                        if (voiceSessionActive) {
                            Button(onClick = { stopVoiceSession() }, modifier = Modifier.fillMaxWidth()) { Text("Stop voice session") }
                        }
                        Spacer(Modifier.height(12.dp))
                        OutlinedTextField(
                            value = promptText, onValueChange = { promptText = it }, modifier = Modifier.fillMaxWidth(),
                            label = { Text("Ask Echo") }, placeholder = { Text("Type a question or command") }, minLines = 2
                        )
                        Button(onClick = { askEcho(promptText) }, modifier = Modifier.fillMaxWidth(),
                            enabled = promptText.isNotBlank() && orbMode != OrbMode.THINKING) { Text("Send and speak reply") }
                        if (answerText.isNotBlank()) {
                            Spacer(Modifier.height(16.dp))
                            Text("ECHO", color = Color(0xFF83F5F2), style = MaterialTheme.typography.labelLarge,
                                modifier = Modifier.fillMaxWidth())
                            Surface(Modifier.fillMaxWidth().padding(top = 6.dp), color = Color(0xFF0A1625)) {
                                Text(answerText, color = Color(0xFFE6F1FA), modifier = Modifier.padding(16.dp),
                                    style = MaterialTheme.typography.bodyLarge)
                            }
                        }

                        Spacer(Modifier.height(22.dp))
                        Text("VOICE OUTPUT", color = Color(0xFF83F5F2), style = MaterialTheme.typography.labelLarge)
                        Text("Choose Kokoro af_heart or an installed Android voice.", color = Color(0xFF9EB2C3),
                            textAlign = TextAlign.Center, style = MaterialTheme.typography.bodySmall)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { useKokoroVoice = true }, modifier = Modifier.weight(1f)) {
                                Text(if (useKokoroVoice) "✓ Kokoro af_heart on PC" else "Kokoro af_heart on PC")
                            }
                            Button(onClick = { useKokoroVoice = false }, modifier = Modifier.weight(1f)) {
                                Text(if (!useKokoroVoice) "✓ Android" else "Android")
                            }
                        }
                        if (androidVoiceNames.isNotEmpty()) {
                            Button(onClick = { voiceMenuOpen = true }, modifier = Modifier.fillMaxWidth()) {
                                Text("Android voice: " + selectedAndroidVoice.ifBlank { "System default" })
                            }
                            DropdownMenu(expanded = voiceMenuOpen, onDismissRequest = { voiceMenuOpen = false }) {
                                androidVoiceNames.forEach { name ->
                                    DropdownMenuItem(text = { Text(name) }, onClick = {
                                        selectedAndroidVoice = name
                                        voiceMenuOpen = false
                                        applyAndroidVoiceSettings()
                                    })
                                }
                            }
                        }
                        Text("Android pitch: " + String.format(Locale.ROOT, "%.2f", pitch), color = Color.White)
                        Slider(value = pitch, onValueChange = { pitch = it; applyAndroidVoiceSettings() }, valueRange = 0.75f..1.25f)
                        Text("Speech rate: " + String.format(Locale.ROOT, "%.2f", speechRate), color = Color.White)
                        Slider(value = speechRate, onValueChange = { speechRate = it; applyAndroidVoiceSettings() }, valueRange = 0.65f..1.15f)
                        OutlinedTextField(value = kokoroEndpoint, onValueChange = { kokoroEndpoint = it },
                            modifier = Modifier.fillMaxWidth(), label = { Text("Kokoro af_heart HTTPS endpoint") }, singleLine = true)
                        OutlinedTextField(value = kokoroKey, onValueChange = { kokoroKey = it },
                            modifier = Modifier.fillMaxWidth(), label = { Text("Kokoro voice bearer key") }, singleLine = true,
                            visualTransformation = PasswordVisualTransformation())
                        OutlinedTextField(value = kokoroFingerprint, onValueChange = { kokoroFingerprint = it },
                            modifier = Modifier.fillMaxWidth(), label = { Text("Certificate SHA-256 fingerprint") },
                            placeholder = { Text("64 hexadecimal characters") }, singleLine = true)
                        Button(onClick = {
                            kokoroClient.save(kokoroEndpoint, kokoroKey, kokoroFingerprint)
                            getSharedPreferences("echo_voice", MODE_PRIVATE).edit()
                                .putBoolean("use_kokoro_voice", useKokoroVoice)
                                .putString("android_voice", selectedAndroidVoice)
                                .putFloat("android_pitch", pitch).putFloat("speech_rate", speechRate).apply()
                            visibleStatus = "Voice settings saved."
                        }, modifier = Modifier.fillMaxWidth()) { Text("Save voice settings") }
                        Button(onClick = { speak("Hello, I’m Echo. This is a voice check.", false) },
                            modifier = Modifier.fillMaxWidth()) { Text("Test selected voice") }

                        Spacer(Modifier.height(20.dp))
                        Text("PC CONNECTION", color = Color(0xFF83F5F2), style = MaterialTheme.typography.labelLarge)
                        OutlinedTextField(value = connectionUrl, onValueChange = { connectionUrl = it },
                            modifier = Modifier.fillMaxWidth(), label = { Text("FreeLLMAPI base URL") },
                            placeholder = { Text("http://127.0.0.1:31415/v1") }, singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri))
                        OutlinedTextField(value = connectionKey, onValueChange = { connectionKey = it },
                            modifier = Modifier.fillMaxWidth(), label = { Text("Unified API key (optional)") },
                            singleLine = true, visualTransformation = PasswordVisualTransformation())
                        Button(onClick = {
                            assistant.saveConnection(connectionUrl, connectionKey)
                            lifecycleScope.launch { assistant.refreshConnection() }
                        }, modifier = Modifier.fillMaxWidth()) { Text("Save and check PC") }
                        Text("For USB, run adb reverse tcp:31415 tcp:31415 and adb reverse tcp:31416 tcp:31416. Use the PC’s LAN/Tailscale address only on a trusted private network.",
                            color = Color(0xFF9EB2C3), style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center)
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = { modelPicker.launch(arrayOf("*/*")) }, modifier = Modifier.fillMaxWidth()) {
                            Text(if (assistant.hasLocalModel()) "Replace local model" else "Choose local model")
                        }
                        Text("Import a compatible MediaPipe LLM model file. It is copied into Echo’s private app storage and may use substantial phone storage.",
                            color = Color(0xFF9EB2C3), style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center)
                        if (visibleStatus.isNotBlank()) {
                            Spacer(Modifier.height(8.dp))
                            Text(visibleStatus, color = Color(0xFFB5C8D8), textAlign = TextAlign.Center)
                        }
                        if (errorText.isNotBlank()) {
                            Spacer(Modifier.height(8.dp))
                            Text(errorText, color = Color(0xFFFF8A8A), textAlign = TextAlign.Center)
                        }
                    }
                }
            }
        }
        lifecycleScope.launch { assistant.refreshConnection() }
    }

    @Composable private fun LaunchedConnectionRefresh() {
        val latest by assistant.uiState.collectAsState()
        androidx.compose.runtime.LaunchedEffect(latest.backend) {
            while (true) { delay(20_000); assistant.refreshConnection() }
        }
    }

    private fun configureEchoVoice() {
        tts = TextToSpeech(this) { result ->
            if (result != TextToSpeech.SUCCESS) return@TextToSpeech
            val engine = tts ?: return@TextToSpeech
            engine.language = Locale.US
            val voices = engine.voices.orEmpty().filter { it.locale.language == "en" }
            androidVoiceNames = voices.map { it.name }.distinct().sorted()
            if (androidVoiceNames.none { it == selectedAndroidVoice })
                selectedAndroidVoice = voices.firstOrNull { !it.isNetworkConnectionRequired }?.name ?: voices.firstOrNull()?.name.orEmpty()
            ttsReady = true
            applyAndroidVoiceSettings()
            engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) { runOnUiThread { orbMode = OrbMode.SPEAKING } }
                override fun onDone(utteranceId: String?) { runOnUiThread { onSpeechFinished() } }
                @Deprecated("Deprecated by Android")
                override fun onError(utteranceId: String?) { runOnUiThread { visibleStatus = "Android speech synthesis failed."; onSpeechFinished() } }
                override fun onError(utteranceId: String?, errorCode: Int) {
                    runOnUiThread { visibleStatus = "Android speech synthesis failed (" + errorCode + ")."; onSpeechFinished() }
                }
            })
        }
    }

    private fun applyAndroidVoiceSettings() {
        val engine = tts ?: return
        engine.language = Locale.US
        engine.voices.orEmpty().firstOrNull { it.name == selectedAndroidVoice }?.let { engine.voice = it }
        engine.setPitch(pitch)
        engine.setSpeechRate(speechRate)
    }

    private fun startVoiceSession() {
        voiceSessionActive = true
        errorText = ""
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED)
            microphonePermission.launch(Manifest.permission.RECORD_AUDIO)
        else beginListening()
    }

    private fun beginListening() {
        if (!voiceSessionActive) return
        if (!SpeechRecognizer.isRecognitionAvailable(this)) { stopVoiceSession("No speech recognition service is available."); return }
        if (recognizer == null) recognizer = SpeechRecognizer.createSpeechRecognizer(this).also { service ->
            service.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) { runOnUiThread { orbMode = OrbMode.LISTENING; visibleStatus = "Listening… say a request." } }
                override fun onBeginningOfSpeech() { runOnUiThread { orbMode = OrbMode.LISTENING } }
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() { runOnUiThread { orbMode = OrbMode.THINKING; visibleStatus = "Processing your words…" } }
                override fun onError(error: Int) {
                    runOnUiThread {
                        if (voiceSessionActive) {
                            visibleStatus = when (error) {
                                SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "I didn’t catch that. Listening again…"
                                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission was denied."
                                else -> "Speech recognition issue (" + error + "). Retrying…"
                            }
                            if (error == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) stopVoiceSession(visibleStatus)
                            else lifecycleScope.launch { delay(700); beginListening() }
                        }
                    }
                }
                override fun onResults(results: Bundle?) {
                    val transcript = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
                    runOnUiThread {
                        if (transcript.isBlank()) {
                            visibleStatus = "I didn’t catch that. Listening again…"
                            lifecycleScope.launch { delay(500); beginListening() }
                        } else askEcho(transcript)
                    }
                }
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
        }
        try {
            val request = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            }
            orbMode = OrbMode.LISTENING
            recognizer?.startListening(request)
        } catch (e: Exception) { stopVoiceSession("Could not start listening: " + (e.message ?: "speech service error")) }
    }

    private fun stopVoiceSession(message: String = "Voice session stopped.") {
        voiceSessionActive = false
        runCatching { recognizer?.cancel() }
        runCatching { tts?.stop() }
        runCatching { mediaPlayer?.stop() }
        mediaPlayer?.release()
        mediaPlayer = null
        orbMode = OrbMode.IDLE
        visibleStatus = message
    }

    private fun askEcho(text: String) {
        val request = text.trim()
        if (request.isBlank()) return
        runCatching { recognizer?.cancel() }
        tts?.stop()
        mediaPlayer?.release()
        mediaPlayer = null
        promptText = request
        errorText = ""
        val action = PhoneActionRouter.tryHandle(this, request)
        if (action.handled) {
            answerText = action.message
            visibleStatus = "Phone action"
            speak(action.message, true)
            return
        }
        answerText = ""
        orbMode = OrbMode.THINKING
        visibleStatus = "Thinking…"
        lifecycleScope.launch {
            try {
                val reply = assistant.ask(request)
                answerText = reply
                visibleStatus = assistant.uiState.value.message
                speak(reply, true)
            } catch (e: Exception) {
                errorText = e.message ?: "Echo could not complete that request."
                visibleStatus = assistant.uiState.value.message
                orbMode = OrbMode.IDLE
                if (voiceSessionActive) lifecycleScope.launch { delay(800); beginListening() }
            }
        }
    }

    private fun speak(text: String, resumeConversation: Boolean) {
        resumeAfterSpeech = resumeConversation
        tts?.stop()
        mediaPlayer?.release()
        mediaPlayer = null
        if (useKokoroVoice) {
            lifecycleScope.launch {
                try {
                    playKokoroAudio(kokoroClient.synthesize(text, speechRate))
                } catch (e: Exception) {
                    visibleStatus = "Kokoro af_heart unavailable; using Android voice. " + (e.message ?: "")
                    speakOnAndroid(text, resumeConversation)
                }
            }
        } else speakOnAndroid(text, resumeConversation)
    }

    private fun playKokoroAudio(audio: ByteArray) {
        val file = File(cacheDir, "echo-kokoro-" + System.currentTimeMillis() + ".wav")
        try {
            file.writeBytes(audio)
            val player = MediaPlayer()
            mediaPlayer = player
            player.setDataSource(file.absolutePath)
            player.setOnCompletionListener {
                player.release()
                mediaPlayer = null
                file.delete()
                onSpeechFinished()
            }
            player.setOnErrorListener { _, _, _ ->
                player.release()
                mediaPlayer = null
                file.delete()
                visibleStatus = "Could not play Kokoro audio; using Android voice."
                speakOnAndroid(answerText.ifBlank { "Hello, this is Echo." }, resumeAfterSpeech)
                true
            }
            player.setOnPreparedListener {
                if (mediaPlayer === player) {
                    player.start()
                    orbMode = OrbMode.SPEAKING
                } else {
                    player.release()
                    file.delete()
                }
            }
            player.prepareAsync()
        } catch (_: Exception) {
            file.delete()
            mediaPlayer?.release()
            mediaPlayer = null
            visibleStatus = "Could not play Kokoro audio; using Android voice."
            speakOnAndroid(answerText.ifBlank { "Hello, this is Echo." }, resumeAfterSpeech)
        }
    }

    private fun speakOnAndroid(text: String, resumeConversation: Boolean) {
        resumeAfterSpeech = resumeConversation
        if (!ttsReady) {
            orbMode = OrbMode.IDLE
            visibleStatus = "Reply is visible, but Android Text-to-Speech is not ready."
            return
        }
        applyAndroidVoiceSettings()
        orbMode = OrbMode.SPEAKING
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "echo-reply")
    }

    private fun onSpeechFinished() {
        orbMode = OrbMode.IDLE
        if (resumeAfterSpeech && voiceSessionActive) {
            resumeAfterSpeech = false
            lifecycleScope.launch { delay(450); beginListening() }
        }
    }

    override fun onDestroy() {
        voiceSessionActive = false
        runCatching { recognizer?.cancel() }
        recognizer?.destroy()
        recognizer = null
        tts?.stop()
        tts?.shutdown()
        mediaPlayer?.release()
        mediaPlayer = null
        assistant.close()
        super.onDestroy()
    }
}

@Composable
private fun PulsingOrb(modifier: Modifier, tint: Color, mode: OrbMode, onTap: () -> Unit) {
    val transition = rememberInfiniteTransition(label = "orb")
    val pulse by transition.animateFloat(initialValue = 0.92f, targetValue = 1.06f,
        animationSpec = infiniteRepeatable(tween(950), RepeatMode.Reverse), label = "pulse")
    val phase by transition.animateFloat(initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(if (mode == OrbMode.THINKING) 1200 else 2200), RepeatMode.Restart), label = "phase")
    val scale = if (mode == OrbMode.IDLE) 1f else pulse
    Box(modifier.scale(scale).background(tint.copy(alpha = 0.08f), CircleShape).clickable(onClick = onTap),
        contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize().alpha(0.98f)) {
            val center = this.center
            val radius = size.minDimension * 0.46f
            drawCircle(Brush.radialGradient(listOf(tint.copy(alpha = 0.85f), tint.copy(alpha = 0.24f), Color.Transparent)),
                radius = radius * 0.88f, center = center)
            if (mode == OrbMode.THINKING) {
                drawArc(color = tint, startAngle = phase, sweepAngle = 270f, useCenter = false,
                    topLeft = Offset(center.x - radius, center.y - radius), size = Size(radius * 2, radius * 2),
                    style = Stroke(width = 5.dp.toPx()))
            } else {
                val expansion = if (mode == OrbMode.SPEAKING || mode == OrbMode.LISTENING) pulse else 1f
                drawCircle(tint.copy(alpha = 0.6f), radius = radius * 0.82f * expansion, center = center,
                    style = Stroke(width = 3.dp.toPx()))
                drawCircle(tint, radius = radius * 0.64f, center = center, style = Stroke(width = 2.dp.toPx()))
                if (mode == OrbMode.LISTENING || mode == OrbMode.SPEAKING) {
                    val barCount = 9
                    for (index in 0 until barCount) {
                        val barHeight = (0.10f + ((index + phase / 24f).toInt() % 4) * 0.045f) * size.minDimension
                        val x = center.x + (index - (barCount - 1) / 2f) * 8.dp.toPx()
                        drawLine(tint, Offset(x, center.y - barHeight / 2), Offset(x, center.y + barHeight / 2),
                            strokeWidth = 3.dp.toPx())
                    }
                } else drawCircle(Color.White.copy(alpha = 0.82f), radius = radius * 0.17f, center = center)
            }
        }
    }
}




