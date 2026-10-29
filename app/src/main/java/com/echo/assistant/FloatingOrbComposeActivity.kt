package com.echo.assistant

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
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
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import java.util.Locale

private enum class OrbMode { IDLE, LISTENING, THINKING, SPEAKING }

class FloatingOrbComposeActivity : ComponentActivity() {
    private lateinit var assistant: AssistantManager
    private lateinit var speechLauncher: ActivityResultLauncher<Intent>
    private lateinit var modelPicker: ActivityResultLauncher<Array<String>>

    private var answerText by mutableStateOf("")
    private var visibleStatus by mutableStateOf("Checking PC brain…")
    private var errorText by mutableStateOf("")
    private var orbMode by mutableStateOf(OrbMode.IDLE)
    private var tts: TextToSpeech? = null
    private var ttsReady = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        assistant = AssistantManager(this)
        connectionUrl = assistant.endpoint
        connectionKey = assistant.apiKey

        speechLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == Activity.RESULT_OK) {
                val text = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull().orEmpty()
                if (text.isNotBlank()) askEcho(text) else {
                    visibleStatus = "I didn’t catch that. Tap the orb to try again."
                    orbMode = OrbMode.IDLE
                }
            } else {
                visibleStatus = "Listening cancelled."
                orbMode = OrbMode.IDLE
            }
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
                targetValue = if (online) Color(0xFF42D9FF) else Color(0xFFFFB347),
                label = "backend-orb-color"
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
                        Text(
                            connection.message,
                            color = if (online) Color(0xFF72E4FF) else Color(0xFFFFC66D),
                            textAlign = TextAlign.Center,
                            style = MaterialTheme.typography.bodyMedium
                        )
                        if (!online && connection.backend == AssistantManager.BackendState.LOCAL_FALLBACK) {
                            Text("PC Brain is asleep. Running on local fallback.", color = Color(0xFFFFC66D), textAlign = TextAlign.Center)
                        }
                        Spacer(Modifier.height(18.dp))
                        PulsingOrb(
                            modifier = Modifier.size(180.dp),
                            tint = orbTint,
                            mode = orbMode,
                            onTap = { startListening() }
                        )
                        Spacer(Modifier.height(12.dp))
                        Text(
                            when (orbMode) {
                                OrbMode.IDLE -> "Tap the orb to speak"
                                OrbMode.LISTENING -> "Listening…"
                                OrbMode.THINKING -> "Thinking…"
                                OrbMode.SPEAKING -> "Echo is speaking"
                            },
                            color = orbTint,
                            textAlign = TextAlign.Center
                        )
                        Spacer(Modifier.height(12.dp))
                        OutlinedTextField(
                            value = answerText,
                            onValueChange = { answerText = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Ask Echo") },
                            placeholder = { Text("Type a question or command") },
                            minLines = 2
                        )
                        Button(
                            onClick = { askEcho(answerText) },
                            modifier = Modifier.fillMaxWidth(),
                            enabled = answerText.isNotBlank() && orbMode != OrbMode.THINKING
                        ) { Text("Send and speak reply") }

                        Spacer(Modifier.height(16.dp))
                        Text("PC CONNECTION", color = Color(0xFF83F5F2), style = MaterialTheme.typography.labelLarge)
                        OutlinedTextField(
                            value = connectionUrl,
                            onValueChange = { connectionUrl = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("FreeLLMAPI base URL") },
                            placeholder = { Text("http://192.168.1.x:<port>/v1") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri)
                        )
                        OutlinedTextField(
                            value = connectionKey,
                            onValueChange = { connectionKey = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Unified API key (optional)") },
                            singleLine = true,
                            visualTransformation = PasswordVisualTransformation()
                        )
                        Button(onClick = {
                            assistant.saveConnection(connectionUrl, connectionKey)
                            lifecycleScope.launch { assistant.refreshConnection() }
                        }, modifier = Modifier.fillMaxWidth()) { Text("Save and check PC") }
                        Text(
                            "Use your PC’s LAN/Tailscale address. On the phone, localhost means the phone itself. For HTTP, connect only on a trusted network; HTTPS is safer for API keys.",
                            color = Color(0xFF9EB2C3),
                            style = MaterialTheme.typography.bodySmall,
                            textAlign = TextAlign.Center
                        )
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = { modelPicker.launch(arrayOf("*/*")) }, modifier = Modifier.fillMaxWidth()) {
                            Text(if (assistant.hasLocalModel()) "Replace local model" else "Choose local model")
                        }
                        Text(
                            "Import a compatible MediaPipe LLM model file. It is copied into Echo’s private app storage and may use substantial phone storage.",
                            color = Color(0xFF9EB2C3),
                            style = MaterialTheme.typography.bodySmall,
                            textAlign = TextAlign.Center
                        )
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

    private var connectionUrl by mutableStateOf("")
    private var connectionKey by mutableStateOf("")

    @Composable
    private fun LaunchedConnectionRefresh() {
        val latest by assistant.uiState.collectAsState()
        androidx.compose.runtime.LaunchedEffect(latest.backend) {
            while (true) {
                delay(20_000)
                assistant.refreshConnection()
            }
        }
    }

    private fun configureEchoVoice() {
        tts = TextToSpeech(this) { result ->
            if (result != TextToSpeech.SUCCESS) return@TextToSpeech
            val engine = tts ?: return@TextToSpeech
            val locale = Locale.US
            engine.language = locale
            engine.setPitch(1.0f)
            engine.setSpeechRate(0.9f)
            val available = engine.voices.orEmpty().filter { it.locale.language == "en" }
            val preferred = available.firstOrNull {
                val name = it.name.lowercase(Locale.ROOT)
                (name.contains("female") || name.contains("soft") || name.contains("journey")) &&
                    !it.isNetworkConnectionRequired
            } ?: available.firstOrNull {
                val name = it.name.lowercase(Locale.ROOT)
                name.contains("female") || name.contains("soft") || name.contains("journey")
            }
            if (preferred != null) engine.voice = preferred
            ttsReady = true
            engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) { runOnUiThread { orbMode = OrbMode.SPEAKING } }
                override fun onDone(utteranceId: String?) { runOnUiThread { orbMode = OrbMode.IDLE } }
                @Deprecated("Deprecated by Android")
                override fun onError(utteranceId: String?) { runOnUiThread { orbMode = OrbMode.IDLE } }
            })
        }
    }

    private fun startListening() {
        if (orbMode == OrbMode.SPEAKING) tts?.stop()
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN")
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak to Echo")
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        try {
            orbMode = OrbMode.LISTENING
            visibleStatus = "Listening…"
            speechLauncher.launch(intent)
        } catch (_: ActivityNotFoundException) {
            orbMode = OrbMode.IDLE
            visibleStatus = "No speech recognition service is available."
        }
    }

    private fun askEcho(text: String) {
        val request = text.trim()
        if (request.isBlank()) return
        tts?.stop()
        answerText = request
        errorText = ""
        orbMode = OrbMode.THINKING
        visibleStatus = "Thinking…"
        lifecycleScope.launch {
            try {
                val reply = assistant.ask(request)
                answerText = reply
                visibleStatus = assistant.uiState.value.message
                speak(reply)
            } catch (e: Exception) {
                val problem = e.message ?: "Echo could not complete that request."
                errorText = problem
                visibleStatus = assistant.uiState.value.message
                orbMode = OrbMode.IDLE
            }
        }
    }

    private fun speak(text: String) {
        if (!ttsReady) {
            orbMode = OrbMode.IDLE
            visibleStatus = "Reply is ready. Android Text-to-Speech is not ready."
            return
        }
        orbMode = OrbMode.SPEAKING
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "echo-reply")
    }

    override fun onDestroy() {
        tts?.stop()
        tts?.shutdown()
        assistant.close()
        super.onDestroy()
    }
}

@Composable
private fun PulsingOrb(modifier: Modifier, tint: Color, mode: OrbMode, onTap: () -> Unit) {
    val transition = rememberInfiniteTransition(label = "orb")
    val pulse by transition.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.06f,
        animationSpec = infiniteRepeatable(tween(950), RepeatMode.Reverse),
        label = "pulse"
    )
    val phase by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(if (mode == OrbMode.THINKING) 1200 else 2200), RepeatMode.Restart),
        label = "phase"
    )
    val scale = if (mode == OrbMode.IDLE) 1f else pulse
    Box(
        modifier.scale(scale).background(tint.copy(alpha = 0.08f), CircleShape)
            .clickable(onClick = onTap),
        contentAlignment = Alignment.Center
    ) {
        Canvas(Modifier.fillMaxSize().alpha(0.98f)) {
            val center = this.center
            val radius = size.minDimension * 0.46f
            drawCircle(Brush.radialGradient(listOf(tint.copy(alpha = 0.85f), tint.copy(alpha = 0.24f), Color.Transparent)), radius = radius * 0.88f, center = center)
            if (mode == OrbMode.THINKING) {
                drawArc(color = tint, startAngle = phase, sweepAngle = 270f, useCenter = false, topLeft = Offset(center.x - radius, center.y - radius), size = Size(radius * 2, radius * 2), style = Stroke(width = 5.dp.toPx()))
            } else {
                val expansion = if (mode == OrbMode.SPEAKING || mode == OrbMode.LISTENING) pulse else 1f
                drawCircle(tint.copy(alpha = 0.6f), radius = radius * 0.82f * expansion, center = center, style = Stroke(width = 3.dp.toPx()))
                drawCircle(tint, radius = radius * 0.64f, center = center, style = Stroke(width = 2.dp.toPx()))
                if (mode == OrbMode.LISTENING || mode == OrbMode.SPEAKING) {
                    val barCount = 9
                    for (index in 0 until barCount) {
                        val barHeight = (0.10f + ((index + phase / 24f).toInt() % 4) * 0.045f) * size.minDimension
                        val x = center.x + (index - (barCount - 1) / 2f) * 8.dp.toPx()
                        drawLine(tint, androidx.compose.ui.geometry.Offset(x, center.y - barHeight / 2), androidx.compose.ui.geometry.Offset(x, center.y + barHeight / 2), strokeWidth = 3.dp.toPx())
                    }
                } else {
                    drawCircle(Color.White.copy(alpha = 0.82f), radius = radius * 0.17f, center = center)
                }
            }
        }
    }
}




