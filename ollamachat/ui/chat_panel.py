"""ChatPanel — conversation display and message input.

Provides the main chat interface: read-only conversation display (TE_RICH2),
multiline message input with Enter/Shift+Enter handling, and action buttons
(send, stop, attach, clear). Supports file attachment (images → base64,
text → message body).
"""

import base64
from pathlib import Path

import wx


class ChatPanel(wx.Panel):
    """Panel for conversation display, input, and action buttons.

    Args:
        parent: Parent wx window.
        speech: Speech instance for token announcements.
    """

    def __init__(self, parent: wx.Window, speech, on_send: callable | None = None) -> None:
        super().__init__(parent)
        self._speech = speech
        self._on_send_callback = on_send
        self._attached_images: list[str] = []
        self._attached_text: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the chat panel layout."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # ── Conversation Display ────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Conversación:"),
            flag=wx.LEFT | wx.TOP, border=8,
        )
        self.conversation_display = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="conversation_display",
        )
        sizer.Add(self.conversation_display, proportion=1, flag=wx.EXPAND | wx.ALL, border=8)

        # ── Attachment Label ────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Adjunto:"),
            flag=wx.LEFT | wx.RIGHT, border=8,
        )
        self.attachment_label = wx.StaticText(
            self, label="(ninguno)", name="attachment_label"
        )
        sizer.Add(self.attachment_label, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)

        # ── Message Input ───────────────────────────────────────────────────
        sizer.Add(
            wx.StaticText(self, label="Mensaje:"),
            flag=wx.LEFT | wx.RIGHT, border=8,
        )
        self.message_input = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER,
            name="message_input",
        )
        self.message_input.Bind(wx.EVT_TEXT_ENTER, self._on_input_enter)
        sizer.Add(self.message_input, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=8)

        # ── Action Buttons ──────────────────────────────────────────────────
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(
            wx.StaticText(self, label="Acciones:"),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4,
        )

        self.send_button = wx.Button(self, label="Enviar", name="send_button")
        self.send_button.Bind(
            wx.EVT_BUTTON, lambda evt: self._on_send_callback() if self._on_send_callback else None
        )
        btn_sizer.Add(self.send_button, flag=wx.RIGHT, border=4)

        self.stop_button = wx.Button(self, label="Detener", name="stop_button")
        self.stop_button.Disable()
        # Stop button is bound externally by MainWindow
        btn_sizer.Add(self.stop_button, flag=wx.RIGHT, border=4)

        self.attach_button = wx.Button(self, label="Adjuntar", name="attach_button")
        self.attach_button.Bind(wx.EVT_BUTTON, lambda evt: self._on_attach())
        btn_sizer.Add(self.attach_button, flag=wx.RIGHT, border=4)

        self.clear_button = wx.Button(self, label="Limpiar", name="clear_button")
        self.clear_button.Bind(wx.EVT_BUTTON, lambda evt: self._on_clear())
        btn_sizer.Add(self.clear_button, flag=wx.RIGHT, border=4)

        sizer.Add(btn_sizer, flag=wx.ALL, border=8)

        self.SetSizer(sizer)

    def _on_input_enter(self, event: wx.CommandEvent) -> None:
        """Handle Enter key in message input.

        Enter (without Shift) sends the message.
        Shift+Enter inserts a newline.
        """
        if event.ShiftDown():
            # Shift+Enter: insert newline and let the event propagate
            event.Skip()
        else:
            # Enter: send message
            if self._on_send_callback:
                self._on_send_callback()

    def _on_attach(self) -> None:
        """Open file dialog and handle attachment."""
        wildcard = (
            "Todos los archivos (*.*)|*.*"
        )
        dialog = wx.FileDialog(
            self,
            message="Adjuntar archivo",
            defaultDir="",
            defaultFile="",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dialog.ShowModal() == wx.ID_OK:
            filepath = dialog.GetPath()
            self.attach_file(filepath)
        dialog.Destroy()

    def _on_clear(self) -> None:
        """Clear the conversation and attachment."""
        self.clear()

    def get_input_text(self) -> str:
        """Get the current message input text.

        Returns:
            Current text in the message input field.
        """
        return self.message_input.GetValue()

    def _clear_input(self) -> None:
        """Clear the message input field."""
        self.message_input.Clear()

    def append_user_message(self, text: str) -> None:
        """Append a user message to the conversation display.

        Args:
            text: User message text.
        """
        self.conversation_display.AppendText(f"[Usuario] {text}\n")

    def append_assistant_prefix(self) -> None:
        """Append the assistant prefix before streaming tokens."""
        self.conversation_display.AppendText("[Asistente] ")

    def append_assistant_chunk(self, token: str) -> None:
        """Append a token fragment to the assistant's response.

        Args:
            token: Token text from the LLM stream.
        """
        self.conversation_display.AppendText(token)

    def start_generation(self) -> None:
        """Disable send and attach buttons during generation."""
        self.send_button.Disable()
        self.attach_button.Disable()
        self.stop_button.Enable()

    def end_generation(self) -> None:
        """Re-enable buttons after generation completes."""
        self.send_button.Enable()
        self.attach_button.Enable()
        self.stop_button.Disable()

    def attach_file(self, filepath: str) -> None:
        """Attach a file to the next message.

        Image files (jpg, jpeg, png, bmp, gif) are base64-encoded and
        stored in _attached_images. Other files are read as UTF-8 text.

        Args:
            filepath: Path to the file to attach.
        """
        path = Path(filepath)
        ext = path.suffix.lower().lstrip(".")

        if ext in ("jpg", "jpeg", "png", "bmp", "gif"):
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            self._attached_images = [encoded]
            self._attached_text = None
            self.attachment_label.SetLabel(path.name)
            self._speech.speak(f"Imagen adjuntada: {path.name}", interrupt=True)
        else:
            try:
                text_content = path.read_text(encoding="utf-8")
                self._attached_text = text_content
                self._attached_images = []
                self.attachment_label.SetLabel(path.name)
                self._speech.speak(
                    f"Archivo de texto adjuntado: {path.name}", interrupt=True
                )
            except Exception:
                self._speech.speak(
                    f"No se pudo adjuntar: {path.name}", interrupt=True
                )

    def get_attached_images(self) -> list[str]:
        """Get the list of base64-encoded attached images.

        Returns:
            List of base64 image strings.
        """
        return self._attached_images

    def get_attached_text(self) -> str | None:
        """Get the attached text file content, if any.

        Returns:
            Text content string, or None.
        """
        return self._attached_text

    def clear_attachment(self) -> None:
        """Clear the current attachment."""
        self._attached_images = []
        self._attached_text = None
        self.attachment_label.SetLabel("(ninguno)")

    def clear(self) -> None:
        """Clear the conversation display, input, and attachments."""
        self.conversation_display.Clear()
        self._clear_input()
        self.clear_attachment()
