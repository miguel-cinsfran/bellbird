"""ParamsPanel — model selection and sampling parameter controls.

Left-hand panel (280px) of MainWindow with model selector, system prompt,
and LLM sampling controls. Every widget is named and preceded by a
StaticText label for screen reader compatibility.
"""

import wx


class ParamsPanel(wx.Panel):
    """Panel for model selection and sampling parameters.

    Args:
        parent: Parent wx window.
        speech: Speech instance for slider value announcements.
    """

    def __init__(self, parent: wx.Window, speech) -> None:
        super().__init__(parent, size=(280, -1))
        self._speech = speech
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the parameter controls layout."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # ── Model Selector ──────────────────────────────────────────────
        sizer.Add(wx.StaticText(self, label="Modelo:"), flag=wx.LEFT | wx.TOP, border=8)
        model_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.model_selector = wx.Choice(
            self, name="model_selector"
        )
        model_sizer.Add(self.model_selector, proportion=1, flag=wx.EXPAND)

        self.refresh_models_button = wx.Button(
            self, label="Actualizar modelos", name="refresh_models_button"
        )
        model_sizer.Add(
            self.refresh_models_button, flag=wx.LEFT, border=4
        )
        sizer.Add(model_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        # ── System Prompt ───────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Prompt de sistema:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.system_prompt = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE,
            size=(-1, 80),
            name="system_prompt",
        )
        sizer.Add(self.system_prompt, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        # ── Temperature Slider ──────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Temperatura:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        temp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.temperature_slider = wx.Slider(
            self,
            minValue=0,
            maxValue=200,
            value=70,
            name="temperature_slider",
            style=wx.SL_HORIZONTAL,
        )
        self.temperature_label = wx.StaticText(
            self, label="0.70", name="temperature_label"
        )
        temp_sizer.Add(self.temperature_slider, proportion=1, flag=wx.EXPAND)
        temp_sizer.Add(self.temperature_label, flag=wx.LEFT, border=4)
        sizer.Add(temp_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        self.temperature_slider.Bind(
            wx.EVT_SLIDER, self._on_slider_change, self.temperature_slider
        )

        # ── Max Tokens Spin ─────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Máximo de tokens:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.max_tokens_spin = wx.SpinCtrl(
            self,
            min=64,
            max=8192,
            initial=512,
            name="max_tokens_spin",
        )
        sizer.Add(self.max_tokens_spin, flag=wx.LEFT | wx.RIGHT, border=8)

        # ── Top-p Slider ────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Top-p:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        top_p_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.top_p_slider = wx.Slider(
            self,
            minValue=0,
            maxValue=100,
            value=90,
            name="top_p_slider",
            style=wx.SL_HORIZONTAL,
        )
        self.top_p_label = wx.StaticText(
            self, label="0.90", name="top_p_label"
        )
        top_p_sizer.Add(self.top_p_slider, proportion=1, flag=wx.EXPAND)
        top_p_sizer.Add(self.top_p_label, flag=wx.LEFT, border=4)
        sizer.Add(top_p_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        self.top_p_slider.Bind(
            wx.EVT_SLIDER, self._on_slider_change, self.top_p_slider
        )

        # ── Top-k Spin ──────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Top-k:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.top_k_spin = wx.SpinCtrl(
            self,
            min=1,
            max=200,
            initial=40,
            name="top_k_spin",
        )
        sizer.Add(self.top_k_spin, flag=wx.LEFT | wx.RIGHT, border=8)

        # ── Repeat Penalty Slider ───────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Penalización de repetición:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        rp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.repeat_penalty_slider = wx.Slider(
            self,
            minValue=100,
            maxValue=200,
            value=110,
            name="repeat_penalty_slider",
            style=wx.SL_HORIZONTAL,
        )
        self.repeat_penalty_label = wx.StaticText(
            self, label="1.10", name="repeat_penalty_label"
        )
        rp_sizer.Add(self.repeat_penalty_slider, proportion=1, flag=wx.EXPAND)
        rp_sizer.Add(self.repeat_penalty_label, flag=wx.LEFT, border=4)
        sizer.Add(rp_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        self.repeat_penalty_slider.Bind(
            wx.EVT_SLIDER, self._on_slider_change, self.repeat_penalty_slider
        )

        # Add stretch space at the end
        sizer.AddStretchSpacer()

        self.SetSizer(sizer)

    def set_models(self, models: list[str]) -> None:
        """Populate the model selector with model names.

        Args:
            models: List of model name strings.
        """
        self.model_selector.Clear()
        for model_name in models:
            self.model_selector.Append(model_name)
        if models:
            self.model_selector.SetSelection(0)

    def get_model(self) -> str:
        """Get the currently selected model name.

        Returns:
            Model name string, or "" if none selected.
        """
        sel = self.model_selector.GetSelection()
        if sel == wx.NOT_FOUND:
            return ""
        return self.model_selector.GetString(sel)

    def get_system_prompt(self) -> str:
        """Get the current system prompt text.

        Returns:
            System prompt string (may be empty).
        """
        return self.system_prompt.GetValue()

    def set_system_prompt(self, text: str) -> None:
        """Set the system prompt text.

        Args:
            text: New system prompt text.
        """
        self.system_prompt.SetValue(text)

    def get_params(self) -> dict:
        """Get the current sampling parameters as a dict.

        Returns:
            Dict with keys: temperature, num_predict, top_p, top_k,
            repeat_penalty.
        """
        return {
            "temperature": self.temperature_slider.GetValue() / 100.0,
            "num_predict": self.max_tokens_spin.GetValue(),
            "top_p": self.top_p_slider.GetValue() / 100.0,
            "top_k": self.top_k_spin.GetValue(),
            "repeat_penalty": self.repeat_penalty_slider.GetValue() / 100.0,
        }

    def _on_slider_change(self, event: wx.CommandEvent) -> None:
        """Handle slider value change.

        Updates the associated label and speaks the new value.
        """
        slider = event.GetEventObject()
        label = None
        fmt_value = ""

        if slider == self.temperature_slider:
            label = self.temperature_label
            fmt_value = f"{slider.GetValue() / 100.0:.2f}"
        elif slider == self.top_p_slider:
            label = self.top_p_label
            fmt_value = f"{slider.GetValue() / 100.0:.2f}"
        elif slider == self.repeat_penalty_slider:
            label = self.repeat_penalty_label
            fmt_value = f"{slider.GetValue() / 100.0:.2f}"

        if label is not None:
            label.SetLabel(fmt_value)
            self._speech.speak(fmt_value, interrupt=False)
