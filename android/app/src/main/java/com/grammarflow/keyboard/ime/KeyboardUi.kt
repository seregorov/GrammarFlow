package com.grammarflow.keyboard.ime

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.grammarflow.keyboard.api.CorrectionResult
import com.grammarflow.keyboard.api.RewriteSuggestion
import com.grammarflow.keyboard.highlight.CorrectionHighlighter
import com.grammarflow.keyboard.ui.GfColors

enum class ImePanelMode {
    IDLE,
    LOADING,
    PREVIEW,
    VARIANTS,
    ERROR,
}

data class ImeUiState(
    val layout: KeyboardLayout = KeyboardLayout.RU,
    val shift: Boolean = false,
    val panelMode: ImePanelMode = ImePanelMode.IDLE,
    val statusMessage: String? = null,
    val preview: CorrectionResult? = null,
    val suggestions: List<RewriteSuggestion> = emptyList(),
)

@Composable
fun KeyboardRoot(
    state: ImeUiState,
    onCorrect: () -> Unit,
    onVariants: () -> Unit,
    onApplyPreview: () -> Unit,
    onCancelPreview: () -> Unit,
    onPickSuggestion: (RewriteSuggestion) -> Unit,
    onCloseVariants: () -> Unit,
    onKey: (KeyAction) -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(GfColors.Background)
            .padding(bottom = 6.dp),
    ) {
        when (state.panelMode) {
            ImePanelMode.PREVIEW -> PreviewBar(
                preview = state.preview,
                onApply = onApplyPreview,
                onCancel = onCancelPreview,
            )
            ImePanelMode.VARIANTS -> VariantsSheet(
                suggestions = state.suggestions,
                onPick = onPickSuggestion,
                onClose = onCloseVariants,
            )
            else -> ActionBar(
                loading = state.panelMode == ImePanelMode.LOADING,
                error = state.panelMode == ImePanelMode.ERROR,
                message = state.statusMessage,
                variantsEnabled = state.panelMode != ImePanelMode.LOADING,
                onCorrect = onCorrect,
                onVariants = onVariants,
            )
        }

        if (state.panelMode != ImePanelMode.VARIANTS) {
            KeyGrid(
                layout = state.layout,
                shift = state.shift,
                dimmed = state.panelMode == ImePanelMode.LOADING,
                onKey = onKey,
            )
        } else {
            KeyGrid(
                layout = state.layout,
                shift = state.shift,
                dimmed = true,
                onKey = onKey,
            )
        }
    }
}

@Composable
private fun ActionBar(
    loading: Boolean,
    error: Boolean,
    message: String?,
    variantsEnabled: Boolean,
    onCorrect: () -> Unit,
    onVariants: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 6.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ActionChip(
                label = if (loading) "…" else "Исправить",
                enabled = !loading,
                filled = true,
                onClick = onCorrect,
                modifier = Modifier.weight(1f),
            )
            ActionChip(
                label = "Варианты",
                enabled = variantsEnabled && !loading,
                filled = false,
                onClick = onVariants,
                modifier = Modifier.weight(1f),
            )
            if (loading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    color = GfColors.Accent,
                )
            }
        }
        if (!message.isNullOrBlank()) {
            Text(
                text = message,
                color = if (error) GfColors.Error else GfColors.TextSecondary,
                fontSize = 12.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = 4.dp, start = 4.dp),
            )
        }
    }
}

@Composable
private fun PreviewBar(
    preview: CorrectionResult?,
    onApply: () -> Unit,
    onCancel: () -> Unit,
) {
    val text = preview?.correctedText.orEmpty()
    val spans = if (preview != null) {
        CorrectionHighlighter.spans(
            correctedText = preview.correctedText,
            errors = preview.errors,
            originalText = preview.originalText,
        )
    } else {
        emptyList()
    }
    val annotated = buildAnnotatedString {
        if (spans.isEmpty()) {
            append(text)
        } else {
            var cursor = 0
            for (span in spans.sortedBy { it.start }) {
                val start = span.start.coerceIn(0, text.length)
                val end = span.end.coerceIn(0, text.length)
                if (start > cursor) append(text.substring(cursor, start))
                if (end > start) {
                    withStyle(SpanStyle(background = GfColors.Highlight, color = GfColors.TextPrimary)) {
                        append(text.substring(start, end))
                    }
                }
                cursor = maxOf(cursor, end)
            }
            if (cursor < text.length) append(text.substring(cursor))
        }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(GfColors.Surface)
            .padding(10.dp),
    ) {
        Text(
            text = annotated,
            color = GfColors.TextPrimary,
            fontSize = 15.sp,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 88.dp)
                .verticalScroll(rememberScrollState()),
        )
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ActionChip(
                label = "Применить",
                enabled = true,
                filled = true,
                onClick = onApply,
                modifier = Modifier.weight(1f),
            )
            ActionChip(
                label = "Отмена",
                enabled = true,
                filled = false,
                onClick = onCancel,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun VariantsSheet(
    suggestions: List<RewriteSuggestion>,
    onPick: (RewriteSuggestion) -> Unit,
    onClose: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Варианты", color = GfColors.TextPrimary, fontWeight = FontWeight.SemiBold)
            Text(
                text = "×",
                color = GfColors.TextSecondary,
                fontSize = 22.sp,
                modifier = Modifier
                    .clickable(onClick = onClose)
                    .padding(8.dp),
            )
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            suggestions.forEach { suggestion ->
                Column(
                    modifier = Modifier
                        .width(180.dp)
                        .heightIn(min = 100.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(GfColors.Surface)
                        .clickable { onPick(suggestion) }
                        .padding(10.dp),
                ) {
                    Text(
                        suggestion.label,
                        color = GfColors.Accent,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 13.sp,
                    )
                    if (suggestion.shortDescription.isNotBlank()) {
                        Text(
                            suggestion.shortDescription,
                            color = GfColors.TextSecondary,
                            fontSize = 11.sp,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        suggestion.text,
                        color = GfColors.TextPrimary,
                        fontSize = 13.sp,
                        maxLines = 5,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun ActionChip(
    label: String,
    enabled: Boolean,
    filled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val bg = when {
        !enabled -> GfColors.Key.copy(alpha = 0.5f)
        filled -> GfColors.Accent
        else -> GfColors.SurfaceVariant
    }
    val fg = when {
        !enabled -> GfColors.TextSecondary
        filled -> GfColors.OnAccent
        else -> GfColors.TextPrimary
    }
    Box(
        modifier = modifier
            .height(40.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(bg)
            .clickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, color = fg, fontWeight = FontWeight.Medium, fontSize = 14.sp)
    }
}

@Composable
private fun KeyGrid(
    layout: KeyboardLayout,
    shift: Boolean,
    dimmed: Boolean,
    onKey: (KeyAction) -> Unit,
) {
    val rows = KeyboardLayouts.rows(layout)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp),
        verticalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        rows.forEach { row ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                row.forEach { action ->
                    val weight = keyWeight(action)
                    KeyButton(
                        label = keyLabel(action, shift),
                        modifier = Modifier.weight(weight),
                        dimmed = dimmed,
                        onClick = { if (!dimmed || action is KeyAction.Language) onKey(action) },
                    )
                }
            }
        }
    }
}

private fun keyWeight(action: KeyAction): Float = when (action) {
    KeyAction.Space -> 4f
    KeyAction.Shift, KeyAction.Backspace, KeyAction.Enter,
    KeyAction.Symbols, KeyAction.Abc, KeyAction.Language -> 1.4f
    else -> 1f
}

private fun keyLabel(action: KeyAction, shift: Boolean): String = when (action) {
    is KeyAction.CharKey -> if (shift) action.upper else action.lower
    KeyAction.Shift -> "⇧"
    KeyAction.Backspace -> "⌫"
    KeyAction.Space -> "пробел"
    KeyAction.Enter -> "↵"
    KeyAction.Language -> "🌐"
    KeyAction.Symbols -> "123"
    KeyAction.Abc -> "ABC"
}

@Composable
private fun KeyButton(
    label: String,
    modifier: Modifier = Modifier,
    dimmed: Boolean,
    onClick: () -> Unit,
) {
    Box(
        modifier = modifier
            .height(46.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(if (dimmed) GfColors.Key.copy(alpha = 0.5f) else GfColors.Key)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = label,
            color = if (dimmed) GfColors.TextSecondary else GfColors.TextPrimary,
            fontSize = if (label.length > 2) 12.sp else 16.sp,
            maxLines = 1,
        )
    }
}
