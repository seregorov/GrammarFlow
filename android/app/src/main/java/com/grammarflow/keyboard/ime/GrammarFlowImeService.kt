package com.grammarflow.keyboard.ime

import android.content.Intent
import android.inputmethodservice.InputMethodService
import android.view.View
import android.view.inputmethod.EditorInfo
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.ComposeView
import androidx.lifecycle.setViewTreeLifecycleOwner
import androidx.lifecycle.setViewTreeViewModelStoreOwner
import androidx.savedstate.setViewTreeSavedStateRegistryOwner
import com.grammarflow.keyboard.api.ApiResult
import com.grammarflow.keyboard.api.LlmClient
import com.grammarflow.keyboard.settings.SecureSettings
import com.grammarflow.keyboard.settings.SettingsActivity
import com.grammarflow.keyboard.ui.GrammarFlowTheme
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class GrammarFlowImeService : InputMethodService() {
    private val serviceJob = SupervisorJob()
    private val scope = CoroutineScope(serviceJob + Dispatchers.Main.immediate)

    private lateinit var secureSettings: SecureSettings
    private lateinit var llmClient: LlmClient

    private var uiState by mutableStateOf(ImeUiState())
    private var letterLayout: KeyboardLayout = KeyboardLayout.RU
    private var requestJob: Job? = null

    private val lifecycleOwner = ImeLifecycleOwner()

    override fun onCreate() {
        super.onCreate()
        secureSettings = SecureSettings(this)
        llmClient = LlmClient(
            apiKeyProvider = { secureSettings.apiKey },
            folderIdProvider = { secureSettings.folderId },
        )
        lifecycleOwner.onCreate()
        lifecycleOwner.onResume()
    }

    override fun onCreateInputView(): View {
        val composeView = ComposeView(this).apply {
            setViewTreeLifecycleOwner(lifecycleOwner)
            setViewTreeViewModelStoreOwner(lifecycleOwner)
            setViewTreeSavedStateRegistryOwner(lifecycleOwner)
            setContent {
                GrammarFlowTheme {
                    KeyboardRoot(
                        state = uiState,
                        onCorrect = ::onCorrectClicked,
                        onVariants = ::onVariantsClicked,
                        onApplyPreview = ::onApplyPreview,
                        onCancelPreview = ::onCancelPreview,
                        onPickSuggestion = { suggestion ->
                            FieldTextHelper.replaceAll(currentInputConnection, suggestion.text)
                            uiState = uiState.copy(
                                panelMode = ImePanelMode.IDLE,
                                suggestions = emptyList(),
                                statusMessage = null,
                            )
                        },
                        onCloseVariants = {
                            uiState = uiState.copy(
                                panelMode = ImePanelMode.IDLE,
                                suggestions = emptyList(),
                                statusMessage = null,
                            )
                        },
                        onKey = ::onKeyAction,
                    )
                }
            }
        }
        return composeView
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        uiState = uiState.copy(
            panelMode = ImePanelMode.IDLE,
            statusMessage = null,
            preview = null,
            suggestions = emptyList(),
        )
    }

    override fun onDestroy() {
        requestJob?.cancel()
        scope.cancel()
        lifecycleOwner.onDestroy()
        super.onDestroy()
    }

    private fun onKeyAction(action: KeyAction) {
        val ic = currentInputConnection ?: return
        when (action) {
            is KeyAction.CharKey -> {
                val ch = if (uiState.shift) action.upper else action.lower
                ic.commitText(ch, 1)
                if (uiState.shift) {
                    uiState = uiState.copy(shift = false)
                }
            }
            KeyAction.Shift -> uiState = uiState.copy(shift = !uiState.shift)
            KeyAction.Backspace -> ic.deleteSurroundingText(1, 0)
            KeyAction.Space -> ic.commitText(" ", 1)
            KeyAction.Enter -> {
                val action = currentInputEditorInfo?.imeOptions?.and(EditorInfo.IME_MASK_ACTION)
                    ?: EditorInfo.IME_ACTION_NONE
                val handled = if (action != EditorInfo.IME_ACTION_NONE &&
                    action != EditorInfo.IME_ACTION_UNSPECIFIED
                ) {
                    ic.performEditorAction(action)
                } else {
                    false
                }
                if (!handled) ic.commitText("\n", 1)
            }
            KeyAction.Language -> {
                letterLayout = if (letterLayout == KeyboardLayout.RU) {
                    KeyboardLayout.EN
                } else {
                    KeyboardLayout.RU
                }
                uiState = uiState.copy(layout = letterLayout, shift = false)
            }
            KeyAction.Symbols -> uiState = uiState.copy(layout = KeyboardLayout.SYMBOLS, shift = false)
            KeyAction.Abc -> uiState = uiState.copy(layout = letterLayout, shift = false)
        }
    }

    private fun onCorrectClicked() {
        if (!secureSettings.hasCredentials) {
            openSettingsWithHint("Задайте API Key в настройках")
            return
        }
        val snapshot = FieldTextHelper.read(currentInputConnection)
        if (snapshot == null || snapshot.fullText.isBlank()) {
            uiState = uiState.copy(
                panelMode = ImePanelMode.ERROR,
                statusMessage = "Нет текста в поле",
            )
            return
        }

        requestJob?.cancel()
        uiState = uiState.copy(panelMode = ImePanelMode.LOADING, statusMessage = "Исправление…", preview = null)
        requestJob = scope.launch {
            when (val result = llmClient.correct(snapshot.fullText)) {
                is ApiResult.Ok -> {
                    uiState = uiState.copy(
                        panelMode = ImePanelMode.PREVIEW,
                        preview = result.data,
                        statusMessage = null,
                    )
                }
                is ApiResult.Err -> {
                    uiState = uiState.copy(
                        panelMode = ImePanelMode.ERROR,
                        statusMessage = result.message,
                    )
                }
            }
        }
    }

    private fun onVariantsClicked() {
        if (!secureSettings.hasCredentials) {
            openSettingsWithHint("Задайте API Key в настройках")
            return
        }
        val snapshot = FieldTextHelper.read(currentInputConnection)
        if (snapshot == null || snapshot.fullText.isBlank()) {
            uiState = uiState.copy(
                panelMode = ImePanelMode.ERROR,
                statusMessage = "Нет текста в поле",
            )
            return
        }

        requestJob?.cancel()
        uiState = uiState.copy(panelMode = ImePanelMode.LOADING, statusMessage = "Варианты…", suggestions = emptyList())
        requestJob = scope.launch {
            when (val result = llmClient.improve(snapshot.fullText)) {
                is ApiResult.Ok -> {
                    if (result.data.suggestions.isEmpty()) {
                        uiState = uiState.copy(
                            panelMode = ImePanelMode.ERROR,
                            statusMessage = "Нет вариантов",
                        )
                    } else {
                        uiState = uiState.copy(
                            panelMode = ImePanelMode.VARIANTS,
                            suggestions = result.data.suggestions,
                            statusMessage = null,
                        )
                    }
                }
                is ApiResult.Err -> {
                    uiState = uiState.copy(
                        panelMode = ImePanelMode.ERROR,
                        statusMessage = result.message,
                    )
                }
            }
        }
    }

    private fun onApplyPreview() {
        val text = uiState.preview?.correctedText ?: return
        FieldTextHelper.replaceAll(currentInputConnection, text)
        uiState = uiState.copy(
            panelMode = ImePanelMode.IDLE,
            preview = null,
            statusMessage = null,
        )
    }

    private fun onCancelPreview() {
        uiState = uiState.copy(
            panelMode = ImePanelMode.IDLE,
            preview = null,
            statusMessage = null,
        )
    }

    private fun openSettingsWithHint(message: String) {
        uiState = uiState.copy(panelMode = ImePanelMode.ERROR, statusMessage = message)
        val intent = Intent(this, SettingsActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
    }
}
