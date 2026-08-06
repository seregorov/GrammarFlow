package com.grammarflow.keyboard.ime

sealed class KeyAction {
    data class CharKey(val lower: String, val upper: String = lower.uppercase()) : KeyAction()
    data object Shift : KeyAction()
    data object Backspace : KeyAction()
    data object Space : KeyAction()
    data object Enter : KeyAction()
    data object Language : KeyAction()
    data object Symbols : KeyAction()
    data object Abc : KeyAction()
}

enum class KeyboardLayout { RU, EN, SYMBOLS }

object KeyboardLayouts {
    val RU_ROWS: List<List<KeyAction>> = listOf(
        "йцукенгшщзх".map { KeyAction.CharKey(it.toString()) },
        "фывапролджэ".map { KeyAction.CharKey(it.toString()) },
        listOf(KeyAction.Shift) +
            "ячсмитьбю".map { KeyAction.CharKey(it.toString()) } +
            listOf(KeyAction.Backspace),
        listOf(
            KeyAction.Symbols,
            KeyAction.Language,
            KeyAction.Space,
            KeyAction.Enter,
        ),
    )

    val EN_ROWS: List<List<KeyAction>> = listOf(
        "qwertyuiop".map { KeyAction.CharKey(it.toString()) },
        "asdfghjkl".map { KeyAction.CharKey(it.toString()) },
        listOf(KeyAction.Shift) +
            "zxcvbnm".map { KeyAction.CharKey(it.toString()) } +
            listOf(KeyAction.Backspace),
        listOf(
            KeyAction.Symbols,
            KeyAction.Language,
            KeyAction.Space,
            KeyAction.Enter,
        ),
    )

    val SYMBOL_ROWS: List<List<KeyAction>> = listOf(
        "1234567890".map { KeyAction.CharKey(it.toString()) },
        listOf("-", "/", ":", ";", "(", ")", "₽", "&", "@", "\"").map { KeyAction.CharKey(it) },
        listOf(".", ",", "?", "!", "'", "«", "»").map { KeyAction.CharKey(it) } +
            listOf(KeyAction.Backspace),
        listOf(
            KeyAction.Abc,
            KeyAction.Language,
            KeyAction.Space,
            KeyAction.Enter,
        ),
    )

    fun rows(layout: KeyboardLayout): List<List<KeyAction>> = when (layout) {
        KeyboardLayout.RU -> RU_ROWS
        KeyboardLayout.EN -> EN_ROWS
        KeyboardLayout.SYMBOLS -> SYMBOL_ROWS
    }
}
