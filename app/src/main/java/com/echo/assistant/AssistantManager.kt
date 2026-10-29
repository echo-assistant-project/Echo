package com.echo.assistant

import android.content.Context
import android.net.Uri
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Routes requests to a PC FreeLLMAPI OpenAI-compatible endpoint, then to a local MediaPipe text model. */
class AssistantManager(context: Context) {
    enum class BackendState { CHECKING, PC_ONLINE, LOCAL_FALLBACK, LOCAL_MODEL_MISSING }
    data class UiState(val backend: BackendState, val message: String)
    private data class ProbeResult(val reachable: Boolean, val detail: String)
    private data class ApiConfig(val baseUrl: HttpUrl, val apiKey: String) {
        fun url(path: String): String = baseUrl.newBuilder().addPathSegments(path).build().toString()
    }

    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences("echo_connection", Context.MODE_PRIVATE)
    private val client = OkHttpClient.Builder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .callTimeout(95, TimeUnit.SECONDS)
        .build()
    private val jsonType = "application/json; charset=utf-8".toMediaType()
    private val generationMutex = Mutex()
    private data class ChatTurn(val user: Any, val assistant: String)
    private val historyLock = Any()
    private val recentTurns = ArrayDeque<ChatTurn>()
    private var localEngine: LlmInference? = null
    private val modelFile = File(File(appContext.filesDir, "models"), "echo-local-model.bin")

    private val mutableUiState = MutableStateFlow(UiState(BackendState.CHECKING, "Checking PC brain…"))
    val uiState: StateFlow<UiState> = mutableUiState

    var endpoint: String
        get() = prefs.getString(KEY_ENDPOINT, "") ?: ""
        private set(value) { prefs.edit().putString(KEY_ENDPOINT, value.trim()).apply() }

    var apiKey: String
        get() = prefs.getString(KEY_API_KEY, "") ?: ""
        private set(value) { prefs.edit().putString(KEY_API_KEY, value.trim()).apply() }

    fun saveConnection(url: String, key: String) {
        endpoint = url.trim().trimEnd('/')
        apiKey = key.trim()
    }

    suspend fun refreshConnection(): BackendState = withContext(Dispatchers.IO) {
        val config = runCatching { apiConfig() }.getOrNull()
        val probe = if (config == null) ProbeResult(false, "Enter a valid PC API base URL ending in /v1.")
            else probeServer(config)
        val backend = when {
            probe.reachable -> BackendState.PC_ONLINE
            hasLocalModel() -> BackendState.LOCAL_FALLBACK
            else -> BackendState.LOCAL_MODEL_MISSING
        }
        mutableUiState.value = UiState(backend, when (backend) {
            BackendState.PC_ONLINE -> "PC brain online · Full power"
            BackendState.LOCAL_FALLBACK -> "PC API unavailable: ${probe.detail}. Running on local fallback."
            BackendState.LOCAL_MODEL_MISSING -> "PC API unavailable: ${probe.detail}. No local model is imported."
            BackendState.CHECKING -> "Checking PC brain…"
        })
        backend
    }

    private fun probeServer(config: ApiConfig): ProbeResult = try {
        val request = requestBuilder(config, "models").get().build()
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val authHint = if (response.code == 401 || response.code == 403) " (API key rejected or missing)" else ""
                ProbeResult(false, "GET /v1/models returned HTTP ${response.code}$authHint")
            } else if (!isJson(response.header("Content-Type"))) {
                ProbeResult(false, nonJsonMessage("GET /v1/models", response.code, response.header("Content-Type"), body))
            } else {
                val parsed = runCatching { JSONObject(body) }.getOrNull()
                if (parsed?.opt("data") is JSONArray) ProbeResult(true, "HTTP ${response.code}; valid models JSON")
                else ProbeResult(false, "GET /v1/models returned JSON in an unexpected format.")
            }
        }
    } catch (error: Exception) {
        ProbeResult(false, describe(error))
    }

    private fun describe(error: Throwable): String =
        error.message?.lineSequence()?.firstOrNull()?.take(180)?.ifBlank { null }
            ?: error.javaClass.simpleName

    /** Optional JPEG base64 lets the online vision model receive an OpenAI-compatible image_url. */
    suspend fun ask(userText: String, imageJpegBase64: String? = null): String = withContext(Dispatchers.IO) {
        require(userText.isNotBlank()) { "Please enter or say a request first." }
        val configResult = runCatching { apiConfig() }
        val config = configResult.getOrNull()
        val probe = config?.let { probeServer(it) }
            ?: ProbeResult(false, configResult.exceptionOrNull()?.let { describe(it) } ?: "PC API base URL is invalid.")
        if (config == null && !hasLocalModel()) {
            throw IllegalStateException("PC API unavailable: ${probe.detail}. No compatible local .task model is imported.")
        }
        var remoteFailure = probe.detail
        if (probe.reachable && config != null) {
            mutableUiState.value = UiState(BackendState.PC_ONLINE, "PC brain online · Full power")
            try {
                return@withContext askPc(config, userText, imageJpegBase64)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                remoteFailure = describe(error)
            }
        }
        if (!hasLocalModel()) {
            val message = "PC API unavailable: $remoteFailure. No compatible local .task model is imported."
            mutableUiState.value = UiState(BackendState.LOCAL_MODEL_MISSING, message)
            throw IllegalStateException(message)
        }
        if (imageJpegBase64 != null) {
            mutableUiState.value = UiState(BackendState.LOCAL_FALLBACK, "PC API unavailable: $remoteFailure. Local model is text-only.")
            throw IllegalStateException("Screen vision needs the PC API online; the local model supports text only.")
        }
        mutableUiState.value = UiState(BackendState.LOCAL_FALLBACK, "PC API unavailable: $remoteFailure. Running on local fallback.")
        generationMutex.withLock {
            val engine = localEngine ?: createLocalEngine().also { localEngine = it }
            val previous = synchronized(historyLock) { recentTurns.toList() }
            val prompt = buildString {
                append(PERSONA).append(10.toChar())
                previous.forEach { turn ->
                    if (turn.user is String) append("User: ").append(turn.user).append(10.toChar())
                    append("Echo: ").append(turn.assistant).append(10.toChar())
                }
                append("User: ").append(userText).append(10.toChar()).append("Echo:")
            }
            engine.generateResponse(prompt).also { rememberTurn(userText, it) }
        }
    }

    private fun askPc(config: ApiConfig, userText: String, imageJpegBase64: String?): String {
        val userContent: Any = if (imageJpegBase64 == null) userText else JSONArray()
            .put(JSONObject().put("type", "text").put("text", userText))
            .put(JSONObject().put("type", "image_url").put("image_url",
                JSONObject().put("url", "data:image/jpeg;base64," + imageJpegBase64)))
        val messages = JSONArray().put(JSONObject().put("role", "system").put("content", PERSONA))
        synchronized(historyLock) {
            recentTurns.forEach { turn ->
                messages.put(JSONObject().put("role", "user").put("content", turn.user))
                messages.put(JSONObject().put("role", "assistant").put("content", turn.assistant))
            }
        }
        messages.put(JSONObject().put("role", "user").put("content", userContent))
        val payload = JSONObject().put("model", "auto").put("messages", messages).put("stream", false)
        val request = requestBuilder(config, "chat/completions")
            .post(payload.toString().toRequestBody(jsonType)).build()
        return client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            val contentType = response.header("Content-Type")
            if (!response.isSuccessful) {
                val authHint = if (response.code == 401 || response.code == 403) " (API key rejected or missing)" else ""
                throw IOException("FreeLLMAPI POST /v1/chat/completions returned HTTP ${response.code}$authHint${if (isJson(contentType)) "." else " with non-JSON content; check the API URL."}")
            }
            if (!isJson(contentType)) {
                throw IOException(nonJsonMessage("POST /v1/chat/completions", response.code, contentType, body))
            }
            val root = try { JSONObject(body) } catch (_: Exception) {
                throw IOException("FreeLLMAPI POST /v1/chat/completions returned invalid JSON.")
            }
            val choice = root.optJSONArray("choices")?.optJSONObject(0)
                ?: throw IOException("FreeLLMAPI response JSON has no choices[0].")
            val message = choice.optJSONObject("message")
                ?: throw IOException("FreeLLMAPI response JSON has no choices[0].message.")
            val content = message.opt("content")
                ?: throw IOException("FreeLLMAPI response JSON has no message content.")
            val reply = if (content is String) content else {
                val parts = content as? JSONArray ?: throw IllegalStateException("Unexpected LLM response format")
                buildString {
                    for (i in 0 until parts.length()) {
                        val item = parts.optJSONObject(i)
                        if (item?.optString("type") == "text") append(item.optString("text"))
                    }
                }
            }
            rememberTurn(userContent, reply)
            reply
        }
    }

    private fun rememberTurn(user: Any, assistant: String) {
        synchronized(historyLock) {
            recentTurns.addLast(ChatTurn(user, assistant))
            while (recentTurns.size > 8) recentTurns.removeFirst()
        }
    }

    private fun requestBuilder(config: ApiConfig, path: String) = Request.Builder().url(config.url(path)).apply {
        if (config.apiKey.isNotBlank()) header("Authorization", "Bearer " + config.apiKey)
        header("Accept", "application/json")
    }

    private fun apiConfig(): ApiConfig {
        val raw = endpoint.trim().trimEnd('/')
        val parsed = raw.toHttpUrlOrNull() ?: throw IllegalArgumentException("Enter a valid PC API base URL ending in /v1.")
        require(parsed.encodedPath == "/v1") { "PC API URL must end in exactly one /v1 (for example, http://127.0.0.1:31415/v1)." }
        return ApiConfig(parsed, apiKey.trim())
    }

    private fun isJson(contentType: String?): Boolean {
        val mediaType = contentType?.substringBefore(';')?.trim()?.lowercase() ?: return false
        return mediaType == "application/json" || mediaType.endsWith("+json")
    }

    private fun nonJsonMessage(path: String, status: Int, contentType: String?, body: String): String {
        val looksHtml = body.trimStart().startsWith("<!doctype html", ignoreCase = true) ||
            body.trimStart().startsWith("<html", ignoreCase = true)
        val received = if (looksHtml) "an HTML page (likely the web dashboard)" else "a non-JSON response"
        return "$path returned HTTP $status with ${contentType ?: "no Content-Type"}: $received. Check that the base URL is the API server ending in /v1."
    }

    private fun createLocalEngine(): LlmInference {
        val options = LlmInference.LlmInferenceOptions.builder()
            .setModelPath(modelFile.absolutePath)
            .setMaxTokens(512)
            .build()
        return LlmInference.createFromOptions(appContext, options)
    }

    /** Copies a user-selected compatible model into Echo's private app storage. */
    suspend fun importLocalModel(uri: Uri) = withContext(Dispatchers.IO) {
        val temporary = File(modelFile.parentFile, modelFile.name + ".tmp")
        modelFile.parentFile?.mkdirs()
        appContext.contentResolver.openInputStream(uri)?.use { input ->
            temporary.outputStream().use { output -> input.copyTo(output) }
        } ?: throw IllegalArgumentException("Could not open the selected model file.")
        check(temporary.length() > 0L) { "The selected model file is empty." }
        localEngine?.close()
        localEngine = null
        if (modelFile.exists()) check(modelFile.delete()) { "Could not replace the previous model." }
        check(temporary.renameTo(modelFile)) { "Could not save the model in Echo's private storage." }
        refreshConnection()
    }

    fun hasLocalModel(): Boolean = modelFile.isFile && modelFile.length() > 0L

    fun close() {
        localEngine?.close()
        localEngine = null
        client.dispatcher.cancelAll()
    }

    companion object {
        const val PERSONA = "You are Echo, a gentle, warm, and supportive female companion. Keep your tone friendly, soft, and conversational."
        private const val KEY_ENDPOINT = "pc_endpoint"
        private const val KEY_API_KEY = "pc_api_key"
    }
}

