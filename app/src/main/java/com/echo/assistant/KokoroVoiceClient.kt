package com.echo.assistant

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import org.json.JSONObject
import java.io.IOException
import java.security.MessageDigest
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager

/** Authenticated, fingerprint-pinned TLS client for the loopback Kokoro host. */
class KokoroVoiceClient(context: Context) {
    private val appContext = context.applicationContext
    private val preferences = appContext.getSharedPreferences("echo_voice", Context.MODE_PRIVATE)

    var endpoint: String
        get() = preferences.getString(KEY_ENDPOINT, DEFAULT_ENDPOINT) ?: DEFAULT_ENDPOINT
        private set(value) { preferences.edit().putString(KEY_ENDPOINT, value).apply() }
    var apiKey: String
        get() = readApiKey()
        private set(value) { writeApiKey(value) }
    var certificateSha256: String
        get() = preferences.getString(KEY_FINGERPRINT, "") ?: ""
        private set(value) {
            preferences.edit().putString(KEY_FINGERPRINT, value.filter { it.isLetterOrDigit() }.lowercase()).apply()
        }

    fun save(endpoint: String, key: String, fingerprint: String) {
        this.endpoint = endpoint.trim()
        apiKey = key.trim()
        certificateSha256 = fingerprint
    }

    private fun readApiKey(): String {
        val stored = preferences.getString(KEY_KEY, "").orEmpty()
        if (stored.isBlank()) return ""
        if (!stored.startsWith("enc:")) {
            writeApiKey(stored)
            return stored
        }
        return try {
            val bytes = android.util.Base64.decode(stored.removePrefix("enc:"), android.util.Base64.NO_WRAP)
            val cipher = javax.crypto.Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(javax.crypto.Cipher.DECRYPT_MODE, getEncryptionKey(),
                javax.crypto.spec.GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
            String(cipher.doFinal(bytes.copyOfRange(12, bytes.size)), Charsets.UTF_8)
        } catch (_: Exception) {
            ""
        }
    }

    private fun writeApiKey(value: String) {
        if (value.isBlank()) {
            preferences.edit().remove(KEY_KEY).apply()
            return
        }
        val cipher = javax.crypto.Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(javax.crypto.Cipher.ENCRYPT_MODE, getEncryptionKey())
        val protected = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        val encoded = android.util.Base64.encodeToString(protected, android.util.Base64.NO_WRAP)
        preferences.edit().putString(KEY_KEY, "enc:" + encoded).apply()
    }

    private fun getEncryptionKey(): java.security.Key {
        val store = java.security.KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val alias = "echo.kokoro.voice.key"
        (store.getKey(alias, null) as? java.security.Key)?.let { return it }
        val generator = javax.crypto.KeyGenerator.getInstance("AES", "AndroidKeyStore")
        val spec = android.security.keystore.KeyGenParameterSpec.Builder(
            alias,
            android.security.keystore.KeyProperties.PURPOSE_ENCRYPT or android.security.keystore.KeyProperties.PURPOSE_DECRYPT
        ).setBlockModes(android.security.keystore.KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(android.security.keystore.KeyProperties.ENCRYPTION_PADDING_NONE)
            .setRandomizedEncryptionRequired(true)
            .build()
        generator.init(spec)
        return generator.generateKey()
    }

    suspend fun synthesize(text: String, rate: Float): ByteArray = withContext(Dispatchers.IO) {
        val target = endpoint.trim()
        val parsed = runCatching { target.toHttpUrlOrNull() ?: throw IllegalArgumentException("invalid URL") }
            .getOrElse { throw IOException("Kokoro endpoint is not a valid HTTPS URL.") }
        if (parsed.scheme != "https" || parsed.host !in setOf("127.0.0.1", "localhost") ||
            parsed.port != 31416 || parsed.encodedPath != "/v1/tts" || parsed.query != null
        ) throw IOException("Use https://127.0.0.1:31416/v1/tts through ADB reverse.")
        val key = apiKey
        if (key.isBlank()) throw IOException("Enter the Kokoro bearer key from pairing.txt.")
        val pin = certificateSha256
        if (!pin.matches(Regex("[0-9a-f]{64}"))) throw IOException("Enter the 64-digit certificate SHA-256 fingerprint from pairing.txt.")

        val pinnedTrust = object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {
                throw java.security.cert.CertificateException("Client certificates are not accepted.")
            }
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                if (chain.isEmpty()) throw java.security.cert.CertificateException("Server sent no certificate.")
                chain[0].checkValidity()
                val actual = MessageDigest.getInstance("SHA-256").digest(chain[0].encoded)
                    .joinToString("") { "%02x".format(it) }
                if (!MessageDigest.isEqual(actual.toByteArray(), pin.toByteArray()))
                    throw java.security.cert.CertificateException("Kokoro certificate fingerprint does not match.")
            }
        }
        val ssl = SSLContext.getInstance("TLS").apply { init(null, arrayOf(pinnedTrust), null) }
        val http = OkHttpClient.Builder().sslSocketFactory(ssl.socketFactory, pinnedTrust)
            .connectTimeout(2, TimeUnit.SECONDS).readTimeout(45, TimeUnit.SECONDS)
            .callTimeout(50, TimeUnit.SECONDS).build()
        val request = Request.Builder().url(target).header("Authorization", "Bearer " + key)
            .header("Accept", "audio/wav")
            .post(JSONObject().put("text", text.take(4000)).put("rate", rate.coerceIn(0.6f, 1.2f))
                .toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
            .build()
        http.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                val detail = response.body?.string()?.take(180).orEmpty()
                throw IOException("Kokoro returned HTTP " + response.code + if (detail.isBlank()) "." else ": " + detail)
            }
            if (response.header("Content-Type")?.substringBefore(';')?.trim()?.lowercase() != "audio/wav")
                throw IOException("Kokoro returned an unexpected audio format.")
            val bytes = response.body?.bytes() ?: throw IOException("Kokoro returned no audio.")
            if (bytes.size < 44 || bytes.size > 12 * 1024 * 1024 ||
                String(bytes, 0, 4, Charsets.US_ASCII) != "RIFF" ||
                String(bytes, 8, 4, Charsets.US_ASCII) != "WAVE"
            ) throw IOException("Kokoro returned an invalid WAV file.")
            bytes
        }
    }

    companion object {
        const val DEFAULT_ENDPOINT = "https://127.0.0.1:31416/v1/tts"
        private const val KEY_ENDPOINT = "kokoro_endpoint"
        private const val KEY_KEY = "kokoro_key"
        private const val KEY_FINGERPRINT = "kokoro_fingerprint"
    }
}
