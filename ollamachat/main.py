"""OllamaChat — accessible desktop chat for blind users.

Entry point for the OllamaChat application.
"""

import wx

from ollamachat.ui.main_window import MainWindow


class OllamaChatApp(wx.App):
    """Application class for OllamaChat."""

    def OnInit(self) -> bool:
        """Initialize the application and show the main window.

        Returns:
            True to continue the application event loop.
        """
        frame = MainWindow(None, title="OllamaChat")
        frame.Show()
        return True


def main() -> None:
    """Launch the OllamaChat application."""
    app = OllamaChatApp()
    app.MainLoop()


if __name__ == "__main__":
    main()
