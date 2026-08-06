package com.grammarflow.keyboard.settings

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SecureSettings(context: Context) {
    private val prefs: SharedPreferences = createPrefs(context.applicationContext)

    var apiKey: String
        get() = prefs.getString(KEY_API_KEY, "").orEmpty()
        set(value) = prefs.edit().putString(KEY_API_KEY, value.trim()).apply()

    var folderId: String
        get() = prefs.getString(KEY_FOLDER_ID, "").orEmpty()
        set(value) = prefs.edit().putString(KEY_FOLDER_ID, value.trim()).apply()

    var onboardingDone: Boolean
        get() = prefs.getBoolean(KEY_ONBOARDING_DONE, false)
        set(value) = prefs.edit().putBoolean(KEY_ONBOARDING_DONE, value).apply()

    val hasCredentials: Boolean
        get() = apiKey.isNotBlank() && folderId.isNotBlank()

    fun clearKeys() {
        prefs.edit()
            .remove(KEY_API_KEY)
            .remove(KEY_FOLDER_ID)
            .apply()
    }

    companion object {
        private const val PREFS_NAME = "grammarflow_secure_prefs"
        private const val KEY_API_KEY = "yandex_api_key"
        private const val KEY_FOLDER_ID = "yandex_folder_id"
        private const val KEY_ONBOARDING_DONE = "onboarding_done"

        private fun createPrefs(context: Context): SharedPreferences {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            return EncryptedSharedPreferences.create(
                context,
                PREFS_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        }
    }
}
