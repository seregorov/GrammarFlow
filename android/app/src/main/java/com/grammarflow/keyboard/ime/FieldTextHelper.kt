package com.grammarflow.keyboard.ime

import android.view.inputmethod.ExtractedTextRequest
import android.view.inputmethod.InputConnection

object FieldTextHelper {
    const val MAX_CHARS = 8000

    data class FieldSnapshot(
        val fullText: String,
        val beforeLength: Int,
        val afterLength: Int,
        val selected: Boolean,
    )

    fun read(ic: InputConnection?): FieldSnapshot? {
        if (ic == null) return null

        val selected = ic.getSelectedText(0)?.toString()
        if (!selected.isNullOrEmpty()) {
            return FieldSnapshot(
                fullText = selected.take(MAX_CHARS),
                beforeLength = 0,
                afterLength = 0,
                selected = true,
            )
        }

        val extracted = ic.getExtractedText(ExtractedTextRequest(), 0)
        if (extracted?.text != null) {
            val text = extracted.text.toString()
            if (text.isNotEmpty()) {
                return FieldSnapshot(
                    fullText = text.take(MAX_CHARS),
                    beforeLength = text.length,
                    afterLength = 0,
                    selected = false,
                )
            }
        }

        val before = ic.getTextBeforeCursor(MAX_CHARS, 0)?.toString().orEmpty()
        val after = ic.getTextAfterCursor(MAX_CHARS, 0)?.toString().orEmpty()
        val full = (before + after).take(MAX_CHARS)
        if (full.isEmpty()) return null
        return FieldSnapshot(
            fullText = full,
            beforeLength = before.length,
            afterLength = after.length,
            selected = false,
        )
    }

    fun replaceAll(ic: InputConnection?, newText: String) {
        if (ic == null) return
        ic.beginBatchEdit()
        try {
            val selected = ic.getSelectedText(0)
            if (!selected.isNullOrEmpty()) {
                ic.commitText(newText, 1)
                return
            }

            ic.performContextMenuAction(android.R.id.selectAll)
            val afterSelect = ic.getSelectedText(0)
            if (!afterSelect.isNullOrEmpty()) {
                ic.commitText(newText, 1)
                return
            }

            val extracted = ic.getExtractedText(ExtractedTextRequest(), 0)
            if (extracted?.text != null && extracted.text.isNotEmpty()) {
                val len = extracted.text.length
                ic.setSelection(0, len)
                ic.commitText(newText, 1)
                return
            }

            val beforeLen = ic.getTextBeforeCursor(MAX_CHARS, 0)?.length ?: 0
            val afterLen = ic.getTextAfterCursor(MAX_CHARS, 0)?.length ?: 0
            ic.deleteSurroundingText(beforeLen, afterLen)
            ic.commitText(newText, 1)
        } finally {
            ic.endBatchEdit()
        }
    }
}
