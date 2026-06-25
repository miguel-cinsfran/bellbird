"""PreferencesDialog — preferences dialog with 6-tab notebook.

Reads/writes BellbirdConfig fields via wx.Notebook with 6 tabs:
General, Modelo, Chat, Herramientas, Avanzado, Atajos. Every control has
name= and a preceding StaticText label. Speech resolution for sliders walks
the parent chain to find the MainWindow._speech attribute (same pattern
as MessageDetailDialog._on_open_browser).
"""

import dataclasses

import wx

from bellbird.core.config import BellbirdConfig
from bellbird.core.keymap import (
    DEFAULT_KEYMAP,
    Keymap,
    _format_combo,
)


# ─── Spanish action labels (stable, one per DEFAULT_KEYMAP entry) ──────────────

_ACTION_LABELS: dict[str, str] = {
    "abort_generation": "Detener generación",
    "announce_status": "Estado de sesión",
    "copy_last": "Copiar último mensaje",
    "cycle_panels": "Ciclar paneles",
    "delete_last_exchange": "Eliminar último intercambio",
    "edit_next": "Editar siguiente",
    "edit_previous": "Editar anterior",
    "exit": "Salir",
    "focus_chat": "Enfocar chat",
    "focus_models": "Enfocar modelos",
    "focus_params": "Enfocar parámetros",
    "focus_server": "Enfocar servidor",
    "new_conversation": "Nueva conversación",
    "open_conversation": "Abrir conversación",
    "preferences": "Preferencias",
    "regenerate": "Regenerar respuesta",
    "save_conversation": "Guardar conversación",
    "scan_models": "Buscar modelos",
    "start_server": "Iniciar servidor",
    "stop_server": "Detener servidor",
}


def _parse_stop_text(text: str) -> list[str]:
    """Parse multiline stop-strings text into a cleaned list.

    Strips whitespace per line, drops empty lines, handles \\r\\n.
    """
    return [line.strip() for line in text.splitlines() if line.strip()]


# ─── Key capture controls ─────────────────────────────────────────────────────


class KeyCaptureControl(wx.Panel):
    """Single-shot key capture panel.

    Binds ``EVT_KEY_DOWN`` and, on the next event with a non-modifier
    keycode, displays a formatted label and speaks it. ``Tab`` and
    ``Escape`` are reserved: Tab speaks "Tecla reservada" and does NOT
    advance focus; Escape closes the parent dialog. Single-shot per
    construction — re-show the control for a new capture.

    Args:
        parent: Parent wx window (the capture mini-dialog).
        speech: Speech instance (or anything with a ``speak`` method).
    """

    def __init__(self, parent: wx.Window, speech: object) -> None:
        super().__init__(parent, name="key_capture_panel")
        self._speech = speech
        self._captured_modifiers: int = 0
        self._captured_keycode: int = 0
        self._captured: bool = False

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(self, label="Pulsa la combinación de teclas:"),
            flag=wx.ALL, border=8,
        )
        self._capture_label = wx.StaticText(
            self, label="", name="key_capture_label",
        )
        sizer.Add(self._capture_label, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)

        self.SetSizer(sizer)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def captured(self) -> bool:
        """True if a non-modifier key has been captured."""
        return self._captured

    @property
    def captured_modifiers(self) -> int:
        """Captured modifier bitmask."""
        return self._captured_modifiers

    @property
    def captured_keycode(self) -> int:
        """Captured keycode."""
        return self._captured_keycode

    # ── Event handler ───────────────────────────────────────────────────

    def _on_key_down(self, event: wx.KeyEvent) -> None:
        """Handle EVT_KEY_DOWN: capture the next non-modifier key."""
        keycode = event.GetKeyCode()
        modifiers = event.GetModifiers()

        # Reserved keys
        if keycode == wx.WXK_TAB:
            self._speak("Tecla reservada")
            return  # Consumed — do NOT advance focus

        if keycode == wx.WXK_ESCAPE:
            self._speak("Tecla reservada")
            wx.CallAfter(self._close_parent_dialog)
            return

        # Modifier-only keys — ignore, wait for the next key
        if keycode in (wx.WXK_SHIFT, wx.WXK_CONTROL, wx.WXK_ALT, wx.WXK_MENU):
            return

        # Capture this key
        self._captured_modifiers = modifiers
        self._captured_keycode = keycode
        self._captured = True

        label = _format_combo(modifiers, keycode)
        self._capture_label.SetLabel(label)
        self._speak(label)

        # Let the event propagate so it doesn't interfere with other controls
        event.Skip()

    # ── Helpers ──────────────────────────────────────────────────────────

    def _speak(self, text: str) -> None:
        """Announce text via speech, if available."""
        if self._speech is not None:
            try:
                self._speech.speak(text, interrupt=True)
            except Exception:
                pass

    def _close_parent_dialog(self) -> None:
        """Close the parent mini-dialog with wx.ID_CANCEL (Escape path)."""
        parent = self.GetParent()
        if isinstance(parent, wx.Dialog):
            parent.EndModal(wx.ID_CANCEL)


class _CaptureDialog(wx.Dialog):
    """Modal mini-dialog for capturing a key combination.

    Contains a ``KeyCaptureControl``, an "Aceptar" button, and a
    "Cancelar" button. On Accept, validates the captured combo against
    ``keymap.find_conflict()``. On collision, speaks a Spanish message,
    closes with ``wx.ID_CANCEL``, and keeps the previous binding.

    Args:
        parent: Parent wx window.
        keymap: ``Keymap`` instance (resolved state for conflict
                detection).
        action_id: The action id being rebound.
        speech: Speech instance for announcements.
    """

    def __init__(
        self,
        parent: wx.Window,
        keymap: Keymap,
        action_id: str,
        speech: object,
    ) -> None:
        super().__init__(
            parent, name="keymap_capture_dialog", title="Capturar atajo",
        )
        self._keymap = keymap
        self._action_id = action_id
        self._speech = speech

        root = wx.BoxSizer(wx.VERTICAL)

        # Capture panel
        self._capture = KeyCaptureControl(self, speech)
        root.Add(self._capture, flag=wx.EXPAND | wx.ALL, border=8)

        # ── Buttons ─────────────────────────────────────────────────────
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.accept_btn = wx.Button(
            self, label="Aceptar", name="key_capture_accept_button",
        )
        self.accept_btn.Bind(wx.EVT_BUTTON, self._on_accept)
        self.accept_btn.Disable()  # Enabled after capture
        btn_sizer.Add(self.accept_btn, flag=wx.RIGHT, border=4)

        self.cancel_btn = wx.Button(
            self, label="Cancelar", name="key_capture_cancel_button",
        )
        self.cancel_btn.Bind(
            wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL),
        )
        btn_sizer.Add(self.cancel_btn)

        root.Add(btn_sizer, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=8)

        self.SetSizer(root)
        self.SetEscapeId(wx.ID_CANCEL)
        self.Fit()
        self.SetInitialSize()
        # Focus the capture panel so EVT_KEY_DOWN fires immediately
        wx.CallAfter(self._capture.SetFocus)

    # ── Event handlers ──────────────────────────────────────────────────

    def _on_accept(self, event: wx.CommandEvent) -> None:
        """Validate the captured combo and close with ID_OK or ID_CANCEL."""
        if not self._capture.captured:
            return  # Should not happen (button is disabled), but guard

        mod = self._capture.captured_modifiers
        kc = self._capture.captured_keycode

        # Check for conflicts excluding the action itself
        conflict = self._keymap.find_conflict(mod, kc)
        if conflict is not None and conflict != self._action_id:
            label = _ACTION_LABELS.get(conflict, conflict)
            msg = f"Combinación ya usada por {label}"
            self._speak(msg)
            self.EndModal(wx.ID_CANCEL)
            return

        self.EndModal(wx.ID_OK)

    def get_captured_combo(self) -> tuple[int, int]:
        """Return the captured ``(modifiers, keycode)`` pair."""
        return (self._capture.captured_modifiers, self._capture.captured_keycode)

    def _speak(self, text: str) -> None:
        """Announce text via speech, if available."""
        if self._speech is not None:
            try:
                self._speech.speak(text, interrupt=True)
            except Exception:
                pass


# ─── PreferencesDialog ─────────────────────────────────────────────────────────


class PreferencesDialog(wx.Dialog):
    """Preferences dialog with 6-tab notebook editing BellbirdConfig.

    Args:
        parent: Parent wx window.
        config: BellbirdConfig to edit (copied via dataclasses.replace
                so Cancel/Escape are no-ops).
    """

    def __init__(self, parent: wx.Window, config: BellbirdConfig) -> None:
        super().__init__(parent, title="Preferencias",
                         name="preferences_dialog")
        self._config = dataclasses.replace(config)

        # Resolve speech from parent chain. Walk up the parent tree until
        # we find an object with _speech (MainWindow exposes _speech).
        # If not found, self._speech stays None and speak() is skipped
        # defensively. Same pattern as MessageDetailDialog._on_open_browser.
        self._speech = None
        p = parent
        while p is not None:
            if hasattr(p, "_speech"):
                self._speech = p._speech
                break
            p = p.GetParent()

        # Keymap for Atajos tab — rebuilt from config overrides
        self._keymap = Keymap(DEFAULT_KEYMAP,
                              overrides=self._config.keymap_overrides)
        # Row widgets keyed by action_id: {action_id: {...}}
        self._keymap_rows: dict[str, dict[str, wx.Window]] = {}

        self._build_ui()
        self.SetSize((620, 520))
        wx.CallAfter(self._focus_first_control)

    def _build_ui(self) -> None:
        """Build the dialog layout: notebook + OK/Cancel footer."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(self, name="preferences_notebook")

        self._build_general_page(notebook)
        self._build_model_page(notebook)
        self._build_chat_page(notebook)
        self._build_tools_page(notebook)
        self._build_advanced_page(notebook)
        self._build_keymap_page(notebook)

        main_sizer.Add(notebook, proportion=1,
                       flag=wx.EXPAND | wx.ALL, border=8)

        # ── Footer: OK / Cancel ────────────────────────────────────────
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.ok_button = wx.Button(
            self, id=wx.ID_OK, label="Aceptar", name="pref_ok_button",
        )
        self.ok_button.Bind(wx.EVT_BUTTON, self._on_ok)
        btn_sizer.Add(self.ok_button, flag=wx.RIGHT, border=4)

        self.cancel_button = wx.Button(
            self, id=wx.ID_CANCEL, label="Cancelar", name="pref_cancel_button",
        )
        self.cancel_button.Bind(
            wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL)
        )
        btn_sizer.Add(self.cancel_button)

        main_sizer.Add(btn_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=8)

        self.SetSizer(main_sizer)
        self.SetEscapeId(wx.ID_CANCEL)

    def _build_general_page(self, notebook: wx.Notebook) -> None:
        """Build General tab: extra model folders list + add/remove buttons."""
        panel = wx.Panel(notebook, name="general_page")
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(panel, label="Carpetas de modelos adicionales:"),
            flag=wx.LEFT | wx.TOP | wx.BOTTOM, border=8,
        )

        self.extra_folders_list = wx.ListBox(
            panel, name="Carpetas de modelos adicionales",
            choices=self._config.extra_model_folders,
        )
        sizer.Add(self.extra_folders_list, proportion=1,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        folder_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.add_folder_button = wx.Button(
            panel, label="Agregar carpeta", name="pref_add_folder_button",
        )
        self.add_folder_button.Bind(wx.EVT_BUTTON, self._on_add_folder)
        folder_btn_sizer.Add(self.add_folder_button, flag=wx.RIGHT, border=4)

        self.remove_folder_button = wx.Button(
            panel, label="Quitar seleccionada",
            name="pref_remove_folder_button",
        )
        self.remove_folder_button.Bind(
            wx.EVT_BUTTON, self._on_remove_folder
        )
        folder_btn_sizer.Add(self.remove_folder_button)

        sizer.Add(folder_btn_sizer,
                  flag=wx.LEFT | wx.TOP | wx.BOTTOM, border=8)

        panel.SetSizer(sizer)
        notebook.AddPage(panel, "General")

    def _build_model_page(self, notebook: wx.Notebook) -> None:
        """Build Modelo tab: system prompt + 2 primary samplers (temp + min_p) + max_tokens."""
        panel = wx.Panel(notebook, name="model_page")
        sizer = wx.BoxSizer(wx.VERTICAL)

        # ── System prompt ──────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Prompt de sistema:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_system_prompt = wx.TextCtrl(
            panel, value=self._config.system_prompt,
            style=wx.TE_MULTILINE, size=(-1, 80), name="Prompt de sistema",
        )
        sizer.Add(self.pref_system_prompt,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        # ── Temperature slider ─────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Temperatura:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        temp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pref_temp_slider = wx.Slider(
            panel, minValue=0, maxValue=200,
            value=int(self._config.temperature * 100),
            name="pref_temp_slider", style=wx.SL_HORIZONTAL,
        )
        self.pref_temp_label = wx.StaticText(
            panel, label=f"{self._config.temperature:.2f}",
            name="temp_value_label",
        )
        temp_sizer.Add(self.pref_temp_slider, proportion=1, flag=wx.EXPAND)
        temp_sizer.Add(self.pref_temp_label, flag=wx.LEFT, border=4)
        sizer.Add(temp_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)
        self.pref_temp_slider.Bind(wx.EVT_SLIDER, self._on_slider_change)

        # ── Min-p slider ───────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Min-p:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        min_p_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pref_min_p_slider = wx.Slider(
            panel, minValue=0, maxValue=100,
            value=int(self._config.min_p * 100),
            name="pref_min_p_slider", style=wx.SL_HORIZONTAL,
        )
        self.pref_min_p_label = wx.StaticText(
            panel, label=f"{self._config.min_p:.2f}",
            name="min_p_value_label",
        )
        min_p_sizer.Add(self.pref_min_p_slider, proportion=1, flag=wx.EXPAND)
        min_p_sizer.Add(self.pref_min_p_label, flag=wx.LEFT, border=4)
        sizer.Add(min_p_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)
        self.pref_min_p_slider.Bind(wx.EVT_SLIDER, self._on_slider_change)

        # ── Max tokens ─────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Máximo de tokens:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_max_tokens_spin = wx.SpinCtrl(
            panel, min=64, max=8192,
            initial=self._config.max_tokens,
            name="pref_max_tokens_spin",
        )
        sizer.Add(self.pref_max_tokens_spin,
                  flag=wx.LEFT | wx.RIGHT, border=8)

        sizer.AddStretchSpacer()
        panel.SetSizer(sizer)
        notebook.AddPage(panel, "Modelo")

    def _build_chat_page(self, notebook: wx.Notebook) -> None:
        """Build Chat tab: confirm_new_conversation checkbox."""
        panel = wx.Panel(notebook, name="chat_page")
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(panel, label="Comportamiento:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_confirm_new_conv = wx.CheckBox(
            panel, label="Confirmar al iniciar nueva conversación",
            name="pref_confirm_new_conv",
        )
        self.pref_confirm_new_conv.SetValue(
            self._config.confirm_new_conversation
        )
        sizer.Add(self.pref_confirm_new_conv,
                  flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)

        sizer.AddStretchSpacer()
        panel.SetSizer(sizer)
        notebook.AddPage(panel, "Chat")

    def _build_tools_page(self, notebook: wx.Notebook) -> None:
        """Build Herramientas tab: tools_enabled checkbox."""
        panel = wx.Panel(notebook, name="tools_page")
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(
            wx.StaticText(panel, label="PowerShell:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_tools_checkbox = wx.CheckBox(
            panel, label="Permitir herramientas (PowerShell)",
            name="pref_tools_checkbox",
        )
        self.pref_tools_checkbox.SetValue(self._config.tools_enabled)
        sizer.Add(self.pref_tools_checkbox,
                  flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)

        sizer.AddStretchSpacer()
        panel.SetSizer(sizer)
        notebook.AddPage(panel, "Herramientas")

    def _build_advanced_page(self, notebook: wx.Notebook) -> None:
        """Build Avanzado tab: moved samplers + seed + stop + server fields."""
        panel = wx.Panel(notebook, name="advanced_page")
        sizer = wx.BoxSizer(wx.VERTICAL)

        # ── Top-p slider (moved from Modelo) ───────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Top-p:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        top_p_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pref_top_p_slider = wx.Slider(
            panel, minValue=0, maxValue=100,
            value=int(self._config.top_p * 100),
            name="pref_top_p_slider", style=wx.SL_HORIZONTAL,
        )
        self.pref_top_p_label = wx.StaticText(
            panel, label=f"{self._config.top_p:.2f}",
            name="top_p_value_label",
        )
        top_p_sizer.Add(self.pref_top_p_slider, proportion=1, flag=wx.EXPAND)
        top_p_sizer.Add(self.pref_top_p_label, flag=wx.LEFT, border=4)
        sizer.Add(top_p_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)
        self.pref_top_p_slider.Bind(wx.EVT_SLIDER, self._on_slider_change)

        # ── Top-k (moved from Modelo) ──────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Top-k:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_top_k_spin = wx.SpinCtrl(
            panel, min=1, max=200,
            initial=self._config.top_k,
            name="pref_top_k_spin",
        )
        sizer.Add(self.pref_top_k_spin,
                  flag=wx.LEFT | wx.RIGHT, border=8)

        # ── Repeat penalty slider (moved from Modelo) ──────────────────
        sizer.Add(
            wx.StaticText(panel, label="Penalización de repetición:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        rp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pref_repeat_slider = wx.Slider(
            panel, minValue=100, maxValue=200,
            value=int(self._config.repeat_penalty * 100),
            name="pref_repeat_slider", style=wx.SL_HORIZONTAL,
        )
        self.pref_repeat_label = wx.StaticText(
            panel, label=f"{self._config.repeat_penalty:.2f}",
            name="repeat_value_label",
        )
        rp_sizer.Add(self.pref_repeat_slider, proportion=1, flag=wx.EXPAND)
        rp_sizer.Add(self.pref_repeat_label, flag=wx.LEFT, border=4)
        sizer.Add(rp_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)
        self.pref_repeat_slider.Bind(wx.EVT_SLIDER, self._on_slider_change)

        # ── Seed spin (new) ────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Semilla:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_seed_spin = wx.SpinCtrl(
            panel, min=-1, max=2147483647,
            initial=self._config.seed,
            name="pref_seed_spin",
        )
        sizer.Add(self.pref_seed_spin,
                  flag=wx.LEFT | wx.RIGHT, border=8)

        # ── Stop text (new) ────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Cadenas de parada (una por línea):"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_stop_text = wx.TextCtrl(
            panel, value="\n".join(self._config.stop),
            style=wx.TE_MULTILINE, size=(-1, 60),
            name="pref_stop_text",
        )
        sizer.Add(self.pref_stop_text,
                  flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        # ── Context size ───────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Tamaño de contexto (tokens):"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_ctx_size_spin = wx.SpinCtrl(
            panel, min=512, max=131072,
            initial=self._config.ctx_size,
            name="pref_ctx_size_spin",
        )
        sizer.Add(self.pref_ctx_size_spin,
                  flag=wx.LEFT | wx.RIGHT, border=8)

        # ── GPU layers ─────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Capas GPU (0 = CPU, 99 = todas):"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_gpu_layers_spin = wx.SpinCtrl(
            panel, min=0, max=200,
            initial=self._config.n_gpu_layers,
            name="pref_gpu_layers_spin",
        )
        sizer.Add(self.pref_gpu_layers_spin,
                  flag=wx.LEFT | wx.RIGHT, border=8)

        # ── Server port ────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(panel, label="Puerto del servidor:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.pref_port_spin = wx.SpinCtrl(
            panel, min=1024, max=65535,
            initial=self._config.port,
            name="pref_port_spin",
        )
        sizer.Add(self.pref_port_spin,
                  flag=wx.LEFT | wx.RIGHT, border=8)

        sizer.AddStretchSpacer()
        panel.SetSizer(sizer)
        notebook.AddPage(panel, "Avanzado")

    def _build_keymap_page(self, notebook: wx.Notebook) -> None:
        """Build Atajos tab: one row per DEFAULT_KEYMAP entry.

        Each row has a Spanish action-label StaticText, the current binding
        StaticText, a "Cambiar" button, and a "Restablecer" button.
        Actions are sorted alphabetically by action_id for stability.
        """
        panel = wx.Panel(notebook, name="keymap_page")
        outer_sizer = wx.BoxSizer(wx.VERTICAL)

        outer_sizer.Add(
            wx.StaticText(panel, label="Atajos de teclado (pulsa Cambiar para reasignar):"),
            flag=wx.LEFT | wx.TOP | wx.BOTTOM, border=8,
        )

        # Scrollable container for the row list
        scroll = wx.ScrolledWindow(panel, name="keymap_scroll")
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        sorted_ids = sorted(DEFAULT_KEYMAP.keys())
        for action_id in sorted_ids:
            row_sizer = wx.BoxSizer(wx.HORIZONTAL)

            # Spanish action label
            action_label = _ACTION_LABELS.get(action_id, action_id)
            label_st = wx.StaticText(scroll, label=action_label,
                                     name=f"keymap_action_{action_id}")
            row_sizer.Add(label_st, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)

            # Current binding display (computed from resolved combo, not label)
            resolved = self._keymap.actions.get(action_id)
            binding_text = (
                _format_combo(resolved.modifiers, resolved.keycode)
                if resolved else ""
            )
            binding_st = wx.StaticText(scroll, label=binding_text,
                                       name=f"keymap_binding_{action_id}")
            row_sizer.Add(binding_st, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)

            # Cambiar button
            cambiar_btn = wx.Button(
                scroll, label="Cambiar", name="keymap_capture_button",
            )
            cambiar_btn.Bind(
                wx.EVT_BUTTON,
                lambda e, aid=action_id: self._on_cambiar(aid),
            )
            row_sizer.Add(cambiar_btn, flag=wx.RIGHT, border=4)

            # Restablecer button
            restablecer_btn = wx.Button(
                scroll, label="Restablecer", name="keymap_reset_button",
            )
            restablecer_btn.Bind(
                wx.EVT_BUTTON,
                lambda e, aid=action_id: self._on_restablecer(aid),
            )
            row_sizer.Add(restablecer_btn)

            scroll_sizer.Add(row_sizer, flag=wx.ALL, border=4)

            self._keymap_rows[action_id] = {
                "label": label_st,
                "binding": binding_st,
                "cambiar": cambiar_btn,
                "restablecer": restablecer_btn,
            }

        scroll.SetSizer(scroll_sizer)

        # Configure scroll rate and auto-scroll
        scroll.SetScrollRate(0, 16)
        scroll_sizer.Fit(scroll)

        outer_sizer.Add(scroll, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        panel.SetSizer(outer_sizer)
        notebook.AddPage(panel, "Atajos")

    # ── Atajos tab event handlers ──────────────────────────────────────────

    def _on_cambiar(self, action_id: str) -> None:
        """Open capture dialog for ``action_id`` and apply the captured combo."""
        dlg = _CaptureDialog(self, self._keymap, action_id, self._speech)
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            mod, kc = dlg.get_captured_combo()
            # Update in-memory config override
            self._config.keymap_overrides[action_id] = (mod, kc)
            # Rebuild keymap and update row display
            self._rebuild_keymap_row(action_id)
        dlg.Destroy()

    def _on_restablecer(self, action_id: str) -> None:
        """Remove the override for ``action_id``, reverting to default."""
        self._config.keymap_overrides.pop(action_id, None)
        self._rebuild_keymap_row(action_id)

    def _rebuild_keymap_row(self, action_id: str) -> None:
        """Rebuild the resolved keymap and update the row for ``action_id``."""
        self._keymap = Keymap(DEFAULT_KEYMAP,
                              overrides=self._config.keymap_overrides)
        row = self._keymap_rows.get(action_id)
        if row is None:
            return
        resolved = self._keymap.actions.get(action_id)
        binding_text = (
            _format_combo(resolved.modifiers, resolved.keycode)
            if resolved else ""
        )
        row["binding"].SetLabel(binding_text)

    # ── Event Handlers ─────────────────────────────────────────────────────

    def _on_add_folder(self, event: wx.CommandEvent) -> None:
        """Open DirDialog to add a model folder path."""
        dlg = wx.DirDialog(
            self, message="Seleccione una carpeta de modelos",
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.extra_folders_list.Append(dlg.GetPath())
        dlg.Destroy()

    def _on_remove_folder(self, event: wx.CommandEvent) -> None:
        """Remove the selected folder from the extra_folders_list."""
        sel = self.extra_folders_list.GetSelection()
        if sel != wx.NOT_FOUND:
            self.extra_folders_list.Delete(sel)

    def _on_slider_change(self, event: wx.CommandEvent) -> None:
        """Handle slider value change: update label and speak."""
        slider = event.GetEventObject()
        label = None
        fmt_value = ""

        if slider == self.pref_temp_slider:
            label = self.pref_temp_label
            fmt_value = f"{slider.GetValue() / 100.0:.2f}"
        elif slider == self.pref_min_p_slider:
            label = self.pref_min_p_label
            fmt_value = f"{slider.GetValue() / 100.0:.2f}"
        elif slider == self.pref_top_p_slider:
            label = self.pref_top_p_label
            fmt_value = f"{slider.GetValue() / 100.0:.2f}"
        elif slider == self.pref_repeat_slider:
            label = self.pref_repeat_label
            fmt_value = f"{slider.GetValue() / 100.0:.2f}"

        if label is not None:
            label.SetLabel(fmt_value)
            if self._speech is not None:
                self._speech.speak(fmt_value, interrupt=False)

    def _on_ok(self, event: wx.CommandEvent) -> None:
        """Apply config changes and close with wx.ID_OK."""
        self._apply_config()
        self.EndModal(wx.ID_OK)

    def _apply_config(self) -> None:
        """Read all user-editable controls into self._config.

        BellbirdConfig.last_model is intentionally NOT exposed here —
        it is set by the model-load flow (MainWindow._on_start_server_done).
        """
        self._config.system_prompt = self.pref_system_prompt.GetValue()
        self._config.temperature = self.pref_temp_slider.GetValue() / 100.0
        self._config.max_tokens = self.pref_max_tokens_spin.GetValue()
        self._config.min_p = self.pref_min_p_slider.GetValue() / 100.0
        self._config.top_p = self.pref_top_p_slider.GetValue() / 100.0
        self._config.top_k = self.pref_top_k_spin.GetValue()
        self._config.repeat_penalty = (
            self.pref_repeat_slider.GetValue() / 100.0
        )
        self._config.seed = self.pref_seed_spin.GetValue()
        self._config.stop = _parse_stop_text(self.pref_stop_text.GetValue())
        self._config.extra_model_folders = list(
            self.extra_folders_list.GetItems()
        )
        self._config.confirm_new_conversation = (
            self.pref_confirm_new_conv.GetValue()
        )
        self._config.tools_enabled = self.pref_tools_checkbox.GetValue()
        self._config.ctx_size = self.pref_ctx_size_spin.GetValue()
        self._config.n_gpu_layers = self.pref_gpu_layers_spin.GetValue()
        self._config.port = self.pref_port_spin.GetValue()

    def get_config(self) -> BellbirdConfig:
        """Return the (possibly edited) config copy.

        Call only after ShowModal() returns wx.ID_OK.
        """
        return self._config

    def _focus_first_control(self) -> None:
        """Focus the first interactive control of the first tab."""
        self.extra_folders_list.SetFocus()
