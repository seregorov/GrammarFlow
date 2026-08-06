package com.grammarflow.keyboard.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

class LlmClient(
    private val apiKeyProvider: () -> String,
    private val folderIdProvider: () -> String,
    private val httpClient: OkHttpClient = defaultClient(),
) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    suspend fun correct(text: String): ApiResult<CorrectionResult> {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) {
            return ApiResult.Err("Пустой текст")
        }
        return chat(Prompts.CORRECT, trimmed) { content, original ->
            val payload = json.decodeFromString<CorrectionPayload>(content)
            CorrectionResult(
                originalText = original,
                correctedText = payload.correctedText.ifBlank { original },
                errors = payload.errors.mapNotNull { dto ->
                    if (dto.original.isBlank() && dto.corrected.isBlank()) null
                    else TextError(
                        original = dto.original,
                        corrected = dto.corrected,
                        errorType = ErrorType.from(dto.type),
                        explanation = dto.explanation,
                    )
                },
            )
        }
    }

    suspend fun improve(text: String): ApiResult<ImprovementResult> {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) {
            return ApiResult.Err("Пустой текст")
        }
        return chat(Prompts.IMPROVE, trimmed) { content, original ->
            val payload = json.decodeFromString<ImprovementPayload>(content)
            ImprovementResult(
                originalText = original,
                suggestions = payload.suggestions.mapNotNull { dto ->
                    if (dto.text.isBlank()) null
                    else RewriteSuggestion(
                        style = RewriteStyle.from(dto.style),
                        label = dto.label.ifBlank { dto.style },
                        text = dto.text,
                        shortDescription = dto.shortDescription,
                    )
                },
            )
        }
    }

    private suspend fun <T> chat(
        systemPrompt: String,
        userText: String,
        parse: (content: String, original: String) -> T,
    ): ApiResult<T> = withContext(Dispatchers.IO) {
        val apiKey = apiKeyProvider().trim()
        val folderId = folderIdProvider().trim()
        if (apiKey.isEmpty() || folderId.isEmpty()) {
            return@withContext ApiResult.Err("Задайте API Key и Folder ID в настройках")
        }

        val requestBody = ChatRequest(
            model = "gpt://$folderId/yandexgpt-5-lite",
            temperature = 0.3,
            maxTokens = 2048,
            messages = listOf(
                ChatMessage(role = "system", content = systemPrompt),
                ChatMessage(role = "user", content = userText),
            ),
        )
        val bodyJson = json.encodeToString(requestBody)

        val request = Request.Builder()
            .url(BASE_URL)
            .addHeader("Authorization", "Api-Key $apiKey")
            .addHeader("x-folder-id", folderId)
            .addHeader("Content-Type", "application/json")
            .post(bodyJson.toRequestBody(JSON_MEDIA))
            .build()

        val started = System.currentTimeMillis()
        var lastError: String? = null

        repeat(MAX_RETRIES) { attempt ->
            try {
                httpClient.newCall(request).execute().use { response ->
                    val raw = response.body?.string().orEmpty()
                    if (!response.isSuccessful) {
                        lastError = when (response.code) {
                            401, 403 -> "HTTP ${response.code}: неверный ключ, folder_id или нет доступа к модели"
                            404 -> "HTTP 404: модель недоступна"
                            429 -> "HTTP 429: rate limit"
                            else -> "HTTP ${response.code}"
                        }
                        if (response.code == 429 && attempt < MAX_RETRIES - 1) {
                            delay(RETRY_DELAY_MS)
                            return@repeat
                        }
                        return@withContext ApiResult.Err(
                            lastError!!,
                            System.currentTimeMillis() - started,
                        )
                    }

                    val content = extractMessageContent(raw)
                        ?: return@withContext ApiResult.Err(
                            "Пустой ответ от модели",
                            System.currentTimeMillis() - started,
                        )
                    val cleaned = stripMarkdownFence(content)
                    val jsonText = extractJsonObject(cleaned) ?: cleaned
                    return@withContext try {
                        ApiResult.Ok(
                            parse(jsonText, userText),
                            System.currentTimeMillis() - started,
                        )
                    } catch (e: Exception) {
                        ApiResult.Err(
                            "Модель вернула невалидный JSON: ${e.message}",
                            System.currentTimeMillis() - started,
                        )
                    }
                }
            } catch (e: IOException) {
                lastError = "Сеть: ${e.message ?: "нет соединения"}"
                if (attempt < MAX_RETRIES - 1) {
                    delay(RETRY_DELAY_MS)
                }
            } catch (e: Exception) {
                return@withContext ApiResult.Err(
                    e.message ?: "Ошибка запроса",
                    System.currentTimeMillis() - started,
                )
            }
        }

        ApiResult.Err(
            lastError ?: "Не удалось выполнить запрос",
            System.currentTimeMillis() - started,
        )
    }

    private fun extractMessageContent(raw: String): String? {
        return try {
            val root = json.parseToJsonElement(raw).jsonObject
            val choices = root["choices"]?.jsonArray ?: return null
            if (choices.isEmpty()) return null
            choices[0].jsonObject["message"]?.jsonObject
                ?.get("content")
                ?.jsonPrimitive
                ?.content
                ?.trim()
        } catch (_: Exception) {
            null
        }
    }

    @Serializable
    private data class ChatRequest(
        val model: String,
        val temperature: Double,
        @kotlinx.serialization.SerialName("max_tokens") val maxTokens: Int,
        val messages: List<ChatMessage>,
    )

    @Serializable
    private data class ChatMessage(
        val role: String,
        val content: String,
    )

    companion object {
        private const val BASE_URL = "https://ai.api.cloud.yandex.net/v1/chat/completions"
        private const val MAX_RETRIES = 2
        private const val RETRY_DELAY_MS = 1000L
        private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

        fun stripMarkdownFence(content: String): String {
            var text = content.trim()
            for (prefix in listOf("```json", "```")) {
                if (text.startsWith(prefix)) {
                    text = text.removePrefix(prefix)
                    break
                }
            }
            if (text.endsWith("```")) {
                text = text.dropLast(3)
            }
            return text.trim()
        }

        fun extractJsonObject(text: String): String? {
            val start = text.indexOf('{')
            val end = text.lastIndexOf('}')
            if (start < 0 || end <= start) return null
            val candidate = text.substring(start, end + 1)
            return try {
                Json.parseToJsonElement(candidate) as? JsonObject
                candidate
            } catch (_: Exception) {
                null
            }
        }
    }
}
