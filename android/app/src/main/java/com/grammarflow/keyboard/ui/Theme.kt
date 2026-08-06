package com.grammarflow.keyboard.ui

import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography

object GfColors {
    val Background = Color(0xFF161E2E)
    val Surface = Color(0xFF1E293B)
    val SurfaceVariant = Color(0xFF273449)
    val Accent = Color(0xFF3B82F6)
    val OnAccent = Color.White
    val TextPrimary = Color(0xFFE2E8F0)
    val TextSecondary = Color(0xFF94A3B8)
    val Success = Color(0xFF22C55E)
    val Error = Color(0xFFEF4444)
    val Key = Color(0xFF334155)
    val KeyPressed = Color(0xFF475569)
    val Highlight = Color(0x5922C55E)
}

private val DarkScheme = darkColorScheme(
    primary = GfColors.Accent,
    onPrimary = GfColors.OnAccent,
    background = GfColors.Background,
    onBackground = GfColors.TextPrimary,
    surface = GfColors.Surface,
    onSurface = GfColors.TextPrimary,
    surfaceVariant = GfColors.SurfaceVariant,
    onSurfaceVariant = GfColors.TextSecondary,
    error = GfColors.Error,
)

@Composable
fun GrammarFlowTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkScheme,
        typography = Typography(),
        content = content,
    )
}
