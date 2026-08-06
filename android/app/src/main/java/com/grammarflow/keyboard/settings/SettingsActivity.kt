package com.grammarflow.keyboard.settings

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.view.inputmethod.InputMethodManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.grammarflow.keyboard.api.ApiResult
import com.grammarflow.keyboard.api.LlmClient
import com.grammarflow.keyboard.ui.GfColors
import com.grammarflow.keyboard.ui.GrammarFlowTheme
import kotlinx.coroutines.launch

class SettingsActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val secure = SecureSettings(this)
        setContent {
            GrammarFlowTheme {
                var showOnboarding by remember { mutableStateOf(!secure.onboardingDone) }
                if (showOnboarding) {
                    OnboardingScreen(
                        onOpenImeSettings = {
                            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
                        },
                        onFinish = {
                            secure.onboardingDone = true
                            showOnboarding = false
                        },
                    )
                } else {
                    SettingsScreen(
                        secureSettings = secure,
                        onOpenImeSettings = {
                            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
                        },
                        onShowImePicker = {
                            val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
                            imm.showInputMethodPicker()
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun OnboardingScreen(
    onOpenImeSettings: () -> Unit,
    onFinish: () -> Unit,
) {
    var step by remember { mutableIntStateOf(0) }
    Scaffold(
        containerColor = GfColors.Background,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                text = "GrammarFlow Keyboard",
                color = GfColors.TextPrimary,
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
            )
            when (step) {
                0 -> {
                    Text(
                        "Правка русского текста прямо в поле ввода: кнопки «Исправить» и «Варианты» на клавиатуре.",
                        color = GfColors.TextSecondary,
                    )
                }
                1 -> {
                    Text(
                        "Включите GrammarFlow в Настройки → Язык и ввод → Клавиатуры, затем выберите её как текущую.",
                        color = GfColors.TextSecondary,
                    )
                    Button(onClick = onOpenImeSettings, modifier = Modifier.fillMaxWidth()) {
                        Text("Открыть настройки клавиатур")
                    }
                }
                else -> {
                    Text(
                        "Текст отправляется в Yandex AI Studio только когда вы нажимаете «Исправить» или «Варианты». Нажатия клавиш не логируются.",
                        color = GfColors.TextSecondary,
                    )
                }
            }
            Spacer(Modifier = Modifier.weight(1f))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (step > 0) {
                    OutlinedButton(
                        onClick = { step-- },
                        modifier = Modifier.weight(1f),
                    ) { Text("Назад") }
                }
                Button(
                    onClick = {
                        if (step < 2) step++ else onFinish()
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Text(if (step < 2) "Далее" else "Начать")
                }
            }
        }
    }
}

@Composable
private fun SettingsScreen(
    secureSettings: SecureSettings,
    onOpenImeSettings: () -> Unit,
    onShowImePicker: () -> Unit,
) {
    var apiKey by remember { mutableStateOf(secureSettings.apiKey) }
    var folderId by remember { mutableStateOf(secureSettings.folderId) }
    var showKey by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<String?>(null) }
    var statusOk by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val client = remember {
        LlmClient(
            apiKeyProvider = { secureSettings.apiKey },
            folderIdProvider = { secureSettings.folderId },
        )
    }

    Scaffold(
        containerColor = GfColors.Background,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "GrammarFlow",
                color = GfColors.TextPrimary,
                fontSize = 26.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Yandex AI Studio",
                color = GfColors.TextSecondary,
                fontSize = 14.sp,
            )

            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it },
                label = { Text("API Key") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                visualTransformation = if (showKey) {
                    VisualTransformation.None
                } else {
                    PasswordVisualTransformation()
                },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                trailingIcon = {
                    TextButton(onClick = { showKey = !showKey }) {
                        Text(if (showKey) "Скрыть" else "Показать", color = GfColors.Accent)
                    }
                },
            )

            OutlinedTextField(
                value = folderId,
                onValueChange = { folderId = it },
                label = { Text("Folder ID") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )

            Button(
                onClick = {
                    secureSettings.apiKey = apiKey
                    secureSettings.folderId = folderId
                    status = "Сохранено"
                    statusOk = true
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Сохранить")
            }

            Button(
                onClick = {
                    secureSettings.apiKey = apiKey
                    secureSettings.folderId = folderId
                    loading = true
                    status = null
                    scope.launch {
                        when (val result = client.correct("Как дила")) {
                            is ApiResult.Ok -> {
                                statusOk = true
                                status = "Ping OK (${result.latencyMs} мс): ${result.data.correctedText}"
                            }
                            is ApiResult.Err -> {
                                statusOk = false
                                status = result.message
                            }
                        }
                        loading = false
                    }
                },
                enabled = !loading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp),
                        color = GfColors.OnAccent,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text("Ping API («Как дила»)")
                }
            }

            status?.let {
                Text(
                    text = it,
                    color = if (statusOk) GfColors.Success else GfColors.Error,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }

            Spacer(modifier = Modifier.height(8.dp))
            Text("Клавиатура", color = GfColors.TextPrimary, fontWeight = FontWeight.SemiBold)
            OutlinedButton(onClick = onOpenImeSettings, modifier = Modifier.fillMaxWidth()) {
                Text("Открыть настройки клавиатур")
            }
            OutlinedButton(onClick = onShowImePicker, modifier = Modifier.fillMaxWidth()) {
                Text("Выбрать текущую клавиатуру")
            }

            Spacer(modifier = Modifier.height(8.dp))
            Text(
                "Текст на сервер уходит только по кнопкам «Исправить» / «Варианты».",
                color = GfColors.TextSecondary,
                fontSize = 13.sp,
            )

            TextButton(
                onClick = {
                    secureSettings.clearKeys()
                    apiKey = ""
                    folderId = ""
                    status = "Ключи удалены"
                    statusOk = true
                },
                modifier = Modifier.align(Alignment.Start),
            ) {
                Text("Удалить ключи", color = GfColors.Error)
            }
        }
    }
}
