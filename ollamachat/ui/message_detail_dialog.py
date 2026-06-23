"""MessageDetailDialog — popup for viewing a single message's full text.

Provides a read-only TextCtrl with markdown-stripped content, plus
three action buttons: Open in browser, Copy to clipboard, Close.
Uses wx.Dialog with native wx.Button widgets to maintain MSAA
compatibility with NVDA.
"""

import wx

from ollamachat.core.text_utils import strip_markdown


class MessageDetailDialog(wx.Dialog):
    """Modal dialog showing full message content with action buttons.

    Args:
        parent: Parent wx window.
        role: Message role ('user' or 'assistant'), used for the title.
        text: Full message text (markdown, will be stripped for display).
    """

    def __init__(
        self, parent: wx.Window, role: str, text: str
    ) -> None:
        title = "Mensaje de Tú" if role == "user" else "Mensaje de IA"
        super().__init__(parent, title=title, name="message_detail_dialog")

        sizer = wx.BoxSizer(wx.VERTICAL)

        # ── Content ──────────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Contenido:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.content_text = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            name="content_text",
            value=strip_markdown(text),
        )
        sizer.Add(self.content_text, proportion=1,
                  flag=wx.EXPAND | wx.ALL, border=8)

        # ── Actions ──────────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Acciones:"),
            flag=wx.LEFT | wx.RIGHT, border=8,
        )
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.open_browser_button = wx.Button(
            self, label="Abrir en navegador", name="open_browser_button"
        )
        self.open_browser_button.Bind(
            wx.EVT_BUTTON, lambda evt: self._on_open_browser()
        )
        btn_sizer.Add(self.open_browser_button, flag=wx.RIGHT, border=4)

        self.copy_button = wx.Button(
            self, label="Copiar al portapapeles", name="copy_button"
        )
        self.copy_button.Bind(
            wx.EVT_BUTTON, lambda evt: self._on_copy()
        )
        btn_sizer.Add(self.copy_button, flag=wx.RIGHT, border=4)

        self.close_button = wx.Button(
            self, label="Cerrar", name="close_button"
        )
        self.close_button.Bind(
            wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CANCEL)
        )
        btn_sizer.Add(self.close_button, flag=wx.RIGHT, border=4)

        sizer.Add(btn_sizer, flag=wx.ALL, border=8)

        self.SetSizer(sizer)
        self.SetSize((600, 500))

        # Focus on content text so NVDA announces it immediately
        self.content_text.SetFocus()

        # Escape closes the dialog
        self.SetEscapeId(wx.ID_CANCEL)

    def _on_open_browser(self) -> None:
        """Open message content in the default web browser.

        The actual webbrowser.open call is handled by MainWindow,
        which connects to this button's event. This placeholder
        copies to clipboard as a safe fallback.
        """
        self._copy_to_clipboard()

    def _on_copy(self) -> None:
        """Copy message content to clipboard."""
        self._copy_to_clipboard()

    def _copy_to_clipboard(self) -> None:
        """Internal helper: copy content_text value to wx.Clipboard."""
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(
                wx.TextDataObject(self.content_text.GetValue())
            )
            wx.TheClipboard.Close()
