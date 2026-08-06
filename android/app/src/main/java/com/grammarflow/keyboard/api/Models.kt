package com.grammarflow.keyboard.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

enum class ErrorType {
    SPELLING, GRAMMAR, PUNCTUATION, STYLE, TYPO;

    companion object {
        fun from(raw: String?): ErrorType = when (raw?.lowercase()) {
            "grammar" -> GRAMMAR
            "punctuation" -> PUNCTUATION
            "style" -> STYLE
            "typo" -> TYPO
            else -> SPELLING
        }
    }
}

enum class RewriteStyle {
    FORMAL, CONCISE, CREATIVE, ACADEMIC, FRIENDLY;

    companion object {
        fun from(raw: String?): RewriteStyle = when (raw?.lowercase()) {
            "concise" -> CONCISE
            "creative" -> CREATIVE
            "academic" -> ACADEMIC
            "friendly" -> FRIENDLY
            else -> FORMAL
        }
    }
}

@Serializable
data class TextErrorDto(
    val original: String = "",
    val corrected: String = "",
    val type: String = "spelling",
    val explanation: String = "",
)

data class TextError(
    val original: String,
    val corrected: String,
    val errorType: ErrorType = ErrorType.SPELLING,
    val explanation: String = "",
)

@Serializable
data class CorrectionPayload(
    @SerialName("corrected_text") val correctedText: String = "",
    val errors: List<TextErrorDto> = emptyList(),
)

data class CorrectionResult(
    val originalText: String,
    val correctedText: String,
    val errors: List<TextError> = emptyList(),
) {
    val hasChanges: Boolean get() = originalText != correctedText
}

@Serializable
data class RewriteSuggestionDto(
    val style: String = "formal",
    val label: String = "",
    val text: String = "",
    @SerialName("short_description") val shortDescription: String = "",
)

data class RewriteSuggestion(
    val style: RewriteStyle,
    val label: String,
    val text: String,
    val shortDescription: String = "",
)

@Serializable
data class ImprovementPayload(
    val suggestions: List<RewriteSuggestionDto> = emptyList(),
)

data class ImprovementResult(
    val originalText: String,
    val suggestions: List<RewriteSuggestion> = emptyList(),
)

sealed class ApiResult<out T> {
    data class Ok<T>(
        val data: T,
        val latencyMs: Long = 0,
    ) : ApiResult<T>()

    data class Err(
        val message: String,
        val latencyMs: Long = 0,
    ) : ApiResult<Nothing>()
}
