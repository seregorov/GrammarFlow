package com.grammarflow.keyboard.ime

import android.os.Bundle
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.ViewModelStore
import androidx.lifecycle.ViewModelStoreOwner
import androidx.savedstate.SavedStateRegistry
import androidx.savedstate.SavedStateRegistryController
import androidx.savedstate.SavedStateRegistryOwner

/**
 * Minimal lifecycle / ViewModel / SavedState host so ComposeView works inside InputMethodService.
 */
class ImeLifecycleOwner :
    LifecycleOwner,
    ViewModelStoreOwner,
    SavedStateRegistryOwner {

    private val lifecycleRegistry = LifecycleRegistry(this)
    private val store = ViewModelStore()
    private val savedStateController = SavedStateRegistryController.create(this)

    override val lifecycle: Lifecycle get() = lifecycleRegistry
    override val viewModelStore: ViewModelStore get() = store
    override val savedStateRegistry: SavedStateRegistry get() = savedStateController.savedStateRegistry

    fun onCreate() {
        if (lifecycleRegistry.currentState == Lifecycle.State.INITIALIZED) {
            savedStateController.performRestore(Bundle())
            lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_CREATE)
        }
    }

    fun onResume() {
        if (lifecycleRegistry.currentState == Lifecycle.State.INITIALIZED) {
            onCreate()
        }
        if (lifecycleRegistry.currentState.isAtLeast(Lifecycle.State.CREATED) &&
            !lifecycleRegistry.currentState.isAtLeast(Lifecycle.State.STARTED)
        ) {
            lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_START)
        }
        if (lifecycleRegistry.currentState.isAtLeast(Lifecycle.State.STARTED) &&
            !lifecycleRegistry.currentState.isAtLeast(Lifecycle.State.RESUMED)
        ) {
            lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_RESUME)
        }
    }

    fun onDestroy() {
        if (lifecycleRegistry.currentState.isAtLeast(Lifecycle.State.RESUMED)) {
            lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_PAUSE)
        }
        if (lifecycleRegistry.currentState.isAtLeast(Lifecycle.State.STARTED)) {
            lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_STOP)
        }
        if (lifecycleRegistry.currentState.isAtLeast(Lifecycle.State.CREATED)) {
            lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_DESTROY)
        }
        store.clear()
    }
}
