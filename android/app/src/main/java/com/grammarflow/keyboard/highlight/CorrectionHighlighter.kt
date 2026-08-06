package com.grammarflow.keyboard.highlight

import com.grammarflow.keyboard.api.TextError

data class TextSpan(val start: Int, val end: Int)

object CorrectionHighlighter {
    fun spans(
        correctedText: String,
        errors: List<TextError>,
        originalText: String = "",
    ): List<TextSpan> {
        val fromErrors = spansFromErrors(correctedText, errors)
        if (fromErrors.isNotEmpty()) return fromErrors
        if (originalText.isNotEmpty()) {
            return spansFromDiff(originalText, correctedText)
        }
        return emptyList()
    }

    private fun spansFromErrors(corrected: String, errors: List<TextError>): List<TextSpan> {
        val spans = mutableListOf<TextSpan>()
        val occupied = mutableListOf<Pair<Int, Int>>()
        var searchFrom = 0

        for (err in errors) {
            val fragment = err.corrected.trim()
            if (fragment.isEmpty()) continue
            var idx = corrected.indexOf(fragment, searchFrom)
            if (idx < 0) idx = corrected.indexOf(fragment)
            if (idx < 0) continue
            val end = idx + fragment.length
            if (occupied.any { (a, b) -> !(end <= a || idx >= b) }) continue
            spans += TextSpan(idx, end)
            occupied += idx to end
            searchFrom = end
        }
        return spans
    }

    private fun spansFromDiff(original: String, corrected: String): List<TextSpan> {
        if (corrected.isEmpty() || original == corrected) return emptyList()

        val origTokens = original.split(Regex("\\s+")).filter { it.isNotEmpty() }
        val corrTokens = corrected.split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (corrTokens.isEmpty()) return emptyList()

        val positions = mutableListOf<Int>()
        var pos = 0
        for ((i, tok) in corrTokens.withIndex()) {
            if (i > 0) {
                while (pos < corrected.length && corrected[pos].isWhitespace()) pos++
            }
            positions += pos
            pos += tok.length
        }

        val opcodes = sequenceMatcher(origTokens, corrTokens)
        val spans = mutableListOf<TextSpan>()
        for ((tag, _, _, j1, j2) in opcodes) {
            if (tag != "replace" && tag != "insert") continue
            if (j1 >= j2) continue
            val start = positions[j1]
            val last = corrTokens[j2 - 1]
            val end = positions[j2 - 1] + last.length
            spans += TextSpan(start, end)
        }
        return spans
    }

    /** Minimal SequenceMatcher-style opcodes (word level). */
    private fun sequenceMatcher(
        a: List<String>,
        b: List<String>,
    ): List<Opcode> {
        val n = a.size
        val m = b.size
        val dp = Array(n + 1) { IntArray(m + 1) }
        for (i in n - 1 downTo 0) {
            for (j in m - 1 downTo 0) {
                dp[i][j] = if (a[i] == b[j]) {
                    dp[i + 1][j + 1] + 1
                } else {
                    maxOf(dp[i + 1][j], dp[i][j + 1])
                }
            }
        }

        val matching = mutableListOf<Pair<Int, Int>>()
        var i = 0
        var j = 0
        while (i < n && j < m) {
            when {
                a[i] == b[j] -> {
                    matching += i to j
                    i++
                    j++
                }
                dp[i + 1][j] >= dp[i][j + 1] -> i++
                else -> j++
            }
        }

        val opcodes = mutableListOf<Opcode>()
        var ai = 0
        var bj = 0
        for ((ma, mb) in matching) {
            if (ai < ma || bj < mb) {
                val tag = when {
                    ai < ma && bj < mb -> "replace"
                    ai < ma -> "delete"
                    else -> "insert"
                }
                opcodes += Opcode(tag, ai, ma, bj, mb)
            }
            opcodes += Opcode("equal", ma, ma + 1, mb, mb + 1)
            ai = ma + 1
            bj = mb + 1
        }
        if (ai < n || bj < m) {
            val tag = when {
                ai < n && bj < m -> "replace"
                ai < n -> "delete"
                else -> "insert"
            }
            opcodes += Opcode(tag, ai, n, bj, m)
        }
        return opcodes
    }

    private data class Opcode(
        val tag: String,
        val i1: Int,
        val i2: Int,
        val j1: Int,
        val j2: Int,
    )
}
