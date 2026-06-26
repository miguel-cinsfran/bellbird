"""VoiceDialog — voice and rate selection dialog for SAPI system voice.

Small wx.Dialog with a voice Choice, a rate Slider, and OK/Cancel buttons.
Returns selected (voice_name, rate) on OK. All controls have name= and
preceding wx.StaticText per AGENTS.md accessibility rules.
"""

import wx


class VoiceDialog(wx.Dialog):
    """Voice + rate selection dialog.

    Args:
        parent: Parent wx window.
        voices: List of available SAPI voice names.
        current_voice: Currently selected voice name (selected in Choice).
        current_rate: Current rate value (-10..+10).
    """

    def __init__(
        self,
        parent: wx.Window,
        voices: list[str],
        current_voice: str = "",
        current_rate: int = 0,
    ) -> None:
        super().__init__(
            parent, title="Seleccionar voz", name="voice_dialog",
        )
        self._voice_choice: wx.Choice | None = None
        self._rate_slider: wx.Slider | None = None
        self._rate_label: wx.StaticText | None = None

        root = wx.BoxSizer(wx.VERTICAL)

        # ── Voice selection ────────────────────────────────────────────
        root.Add(
            wx.StaticText(self, label="Voz:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self._voice_choice = wx.Choice(
            self, choices=voices, name="voice_choice",
        )
        if current_voice in voices:
            self._voice_choice.SetStringSelection(current_voice)
        elif voices:
            self._voice_choice.SetSelection(0)
        root.Add(
            self._voice_choice,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8,
        )

        # ── Rate slider ────────────────────────────────────────────────
        root.Add(
            wx.StaticText(self, label="Velocidad:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        rate_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._rate_slider = wx.Slider(
            self, minValue=-10, maxValue=10,
            value=current_rate,
            name="rate_slider", style=wx.SL_HORIZONTAL,
        )
        self._rate_label = wx.StaticText(
            self, label=str(current_rate), name="rate_value_label",
        )
        rate_sizer.Add(self._rate_slider, proportion=1, flag=wx.EXPAND)
        rate_sizer.Add(self._rate_label, flag=wx.LEFT, border=4)
        root.Add(rate_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)
        self._rate_slider.Bind(wx.EVT_SLIDER, self._on_rate_change)

        # ── Buttons ────────────────────────────────────────────────────
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.ok_btn = wx.Button(
            self, label="Aceptar", name="voice_dialog_ok_button",
        )
        self.ok_btn.Bind(
            wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK),
        )
        btn_sizer.Add(self.ok_btn, flag=wx.RIGHT, border=4)

        self.cancel_btn = wx.Button(
            self, label="Cancelar", name="voice_dialog_cancel_button",
        )
        self.cancel_btn.Bind(
            wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL),
        )
        btn_sizer.Add(self.cancel_btn)

        root.Add(btn_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=8)

        self.SetSizer(root)
        self.SetEscapeId(wx.ID_CANCEL)
        self.Fit()
        self.SetInitialSize()
        self.ok_btn.SetFocus()

    # ── Event handlers ────────────────────────────────────────────────

    def _on_rate_change(self, event: wx.CommandEvent) -> None:
        """Update the rate label as the slider moves."""
        if self._rate_label is not None and self._rate_slider is not None:
            self._rate_label.SetLabel(str(self._rate_slider.GetValue()))

    # ── Accessors (call after ShowModal returns wx.ID_OK) ─────────────

    def get_voice(self) -> str:
        """Return the selected voice name."""
        if self._voice_choice is None:
            return ""
        return self._voice_choice.GetStringSelection()

    def get_rate(self) -> int:
        """Return the selected rate value."""
        if self._rate_slider is None:
            return 0
        return self._rate_slider.GetValue()
