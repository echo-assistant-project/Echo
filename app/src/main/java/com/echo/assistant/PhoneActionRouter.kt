package com.echo.assistant

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.Locale

/** Only maps explicit, allow-listed phrases to Android intents; never evaluates model output as code. */
object PhoneActionRouter {
    data class Result(val handled: Boolean, val message: String)

    @JvmStatic
    fun tryHandle(context: Context, raw: String): Result {
        val request = raw.trim()
        if (request.isEmpty()) return Result(false, "")
        val lower = request.lowercase(Locale.ROOT)

        val googleQuery = Regex("^(?:google|search google for|search for)\\s+(.+?)(?:\\s+on google)?$", RegexOption.IGNORE_CASE)
            .matchEntire(request)?.groupValues?.get(1)?.trim()
        if (!googleQuery.isNullOrBlank() && (lower.startsWith("google ") || lower.startsWith("search "))) {
            val url = "https://www.google.com/search?q=" + encode(googleQuery)
            return openUri(context, url, "Showing Google results for $googleQuery.")
        }

        val youtubeQuery = Regex("^(?:search youtube for|find on youtube)\\s+(.+)$", RegexOption.IGNORE_CASE)
            .matchEntire(request)?.groupValues?.get(1)?.trim()
        if (!youtubeQuery.isNullOrBlank()) {
            val url = "https://www.youtube.com/results?search_query=" + encode(youtubeQuery)
            return openUri(context, url, "Showing YouTube results for $youtubeQuery.")
        }

        val spotifyQuery = Regex("^(?:search spotify for|find on spotify)\\s+(.+)$", RegexOption.IGNORE_CASE)
            .matchEntire(request)?.groupValues?.get(1)?.trim()
        if (!spotifyQuery.isNullOrBlank()) {
            val url = "https://open.spotify.com/search/" + encode(spotifyQuery)
            return openUri(context, url, "Opening Spotify search for $spotifyQuery. Choose a result in Spotify to play it.")
        }

        val openTarget = Regex("^(?:open|launch|start)\\s+(.+)$", RegexOption.IGNORE_CASE)
            .matchEntire(request)?.groupValues?.get(1)?.trim()?.removeSuffix(" on my phone")?.trim()
        if (!openTarget.isNullOrBlank()) {
            if (openTarget.startsWith("https://", true) || openTarget.startsWith("http://", true)) {
                val uri = runCatching { Uri.parse(openTarget) }.getOrNull()
                if (uri != null && uri.scheme in setOf("http", "https") && !uri.host.isNullOrBlank())
                    return openUri(context, uri.toString(), "Opening ${uri.host}.")
                return Result(true, "That website address is not valid.")
            }
            val target = when (openTarget.lowercase(Locale.ROOT)) {
                "youtube" -> "YouTube"
                "spotify" -> "Spotify"
                else -> openTarget
            }
            return launchApp(context, target)
        }
        return Result(false, "")
    }

    private fun launchApp(context: Context, wanted: String): Result {
        val pm = context.packageManager
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val matches = if (android.os.Build.VERSION.SDK_INT >= 33) {
            pm.queryIntentActivities(launcher, PackageManager.ResolveInfoFlags.of(0))
        } else {
            @Suppress("DEPRECATION")
            pm.queryIntentActivities(launcher, 0)
        }
        val exact = matches.firstOrNull { it.loadLabel(pm).toString().equals(wanted, true) }
        val partial = exact ?: matches.firstOrNull {
            val label = it.loadLabel(pm).toString()
            label.startsWith(wanted, true) || wanted.startsWith(label, true)
        }
        val info = partial?.activityInfo ?: return Result(true, "I couldn’t find $wanted on this phone.")
        val intent = pm.getLaunchIntentForPackage(info.packageName)
            ?: return Result(true, "${info.loadLabel(pm)} does not provide a launch screen.")
        return try {
            context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            Result(true, "Opening ${info.loadLabel(pm)}.")
        } catch (_: Exception) {
            Result(true, "Android could not open ${info.loadLabel(pm)}.")
        }
    }

    private fun openUri(context: Context, url: String, success: String): Result = try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        Result(true, success)
    } catch (_: Exception) {
        Result(true, "No app on this phone could open that link.")
    }

    private fun encode(value: String): String = URLEncoder.encode(value, StandardCharsets.UTF_8.name())
}
