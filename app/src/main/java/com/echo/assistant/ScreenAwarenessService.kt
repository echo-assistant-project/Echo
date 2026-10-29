package com.echo.assistant

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/** Opt-in accessibility scaffold. It reads visible UI text in memory only; it does not take screenshots or upload data. */
class ScreenAwarenessService : AccessibilityService() {
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val root = rootInActiveWindow ?: return
        val visibleText = mutableListOf<String>()
        collectText(root, visibleText)
        latestScreenText = visibleText.distinct().take(MAX_ITEMS).joinToString("\n")
        root.recycle()
    }

    override fun onInterrupt() { latestScreenText = "" }

    private fun collectText(node: AccessibilityNodeInfo, output: MutableList<String>) {
        node.text?.toString()?.trim()?.takeIf(String::isNotEmpty)?.let(output::add)
        node.contentDescription?.toString()?.trim()?.takeIf(String::isNotEmpty)?.let(output::add)
        for (i in 0 until node.childCount) node.getChild(i)?.let { child ->
            collectText(child, output)
            child.recycle()
        }
    }

    companion object {
        @Volatile var latestScreenText: String = ""
            private set
        private const val MAX_ITEMS = 200
    }
}
