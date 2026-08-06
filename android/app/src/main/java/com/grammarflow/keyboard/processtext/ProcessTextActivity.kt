package com.grammarflow.keyboard.processtext

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.grammarflow.keyboard.api.ApiResult
import com.grammarflow.keyboard.api.LlmClient
import com.grammarflow.keyboard.settings.SecureSettings
import com.grammarflow.keyboard.settings.SettingsActivity
import com.grammarflow.keyboard.ui.GfColors
import com.grammarflow.keyboard.ui.GrammarFlowTheme

class ProcessTextActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val sourceText = intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString()
            ?: intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString()
            ?: ""

        val secure = SecureSettings(this)
        val client = LlmClient(
            apiKeyProvider = { secure.apiKey },
            folderIdProvider = { secure.folderId },
        )

        setContent {
            GrammarFlowTheme {
                var loading by remember { mutableStateOf(true) }
                var error by remember { mutableStateOf<String?>(null) }
                var corrected by remember { mutableStateOf<String?>(null) }

                LaunchedEffect(sourceText) {
                    if (sourceText.isBlank()) {
                        loading = false
                        error = "Нет текста"
                        return@LaunchedEffect
                    }
                    if (!secure.hasCredentials) {
                        loading = false
                        error = "Задайте API Key в настройках"
                        return@LaunchedEffect
                    }
                    when (val result = client.correct(sourceText)) {
                        is ApiResult.Ok -> {
                            corrected = result.data.correctedText
                            error = null
                        }
                        is ApiResult.Err -> {
                            error = result.message
                        }
                    }
                    loading = false
                }

                Scaffold(containerColor = GfColors.Background) { padding ->
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding)
                            .padding(20.dp)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text(
                            "Исправить (GrammarFlow)",
                            color = GfColors.TextPrimary,
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                        )
                        Text("Исходный текст", color = GfColors.TextSecondary, fontSize = 13.sp)
                        Text(sourceText.ifBlank { "—" }, color = GfColors.TextPrimary)

                        Spacer(modifier = Modifier.height(4.dp))

                        when {
                            loading -> CircularProgressIndicator(color = GfColors.Accent)
                            error != null -> {
                                Text(error!!, color = GfColors.Error)
                                if (!secure.hasCredentials) {
                                    Button(
                                        onClick = {
                                            startActivity(Intent(this@ProcessTextActivity, SettingsActivity::class.java))
                                        },
                                        modifier = Modifier.fillMaxWidth(),
                                    ) { Text("Открыть настройки") }
                                }
                            }
                            else -> {
                                Text("Результат", color = GfColors.TextSecondary, fontSize = 13.sp)
                                Text(corrected.orEmpty(), color = GfColors.TextPrimary)
                                Button(
                                    onClick = {
                                        val cm = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
                                        cm.setPrimaryClip(ClipData.newPlainText("GrammarFlow", corrected.orEmpty()))
                                        Toast.makeText(this@ProcessTextActivity, "Скопировано", Toast.LENGTH_SHORT).show()
                                    },
                                    modifier = Modifier.fillMaxWidth(),
                                ) { Text("Копировать") }
                            }
                        }

                        OutlinedButton(
                            onClick = { finish() },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text("Закрыть") }
                    }
                }
            }
        }
    }
}
