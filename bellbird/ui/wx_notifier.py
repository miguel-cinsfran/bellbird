"""Thin wx adapter for Windows toast notifications.

Wraps ``wx.adv.NotificationMessage`` with a line-local ``import wx.adv``
under ``sys.platform == "win32"``. Outside win32, ``show()`` is a no-op.
"""

import sys


class WxToastSender:
    """Toast notification sender using ``wx.adv.NotificationMessage``.

    Args:
        parent: Parent wx.Window for the notification.
    """

    def __init__(self, parent: object) -> None:
        self._parent = parent

    def show(self, title: str, message: str, timeout: int = 5) -> None:
        """Show a Windows toast notification.

        No-op outside win32 or when ``wx.adv`` is not available.
        Never raises.

        Args:
            title: Notification title.
            message: Notification body text.
            timeout: Display timeout in seconds (default 5).
        """
        if sys.platform != "win32":
            return
        try:
            import wx.adv  # line-local — may not be available on all wx builds
            notification = wx.adv.NotificationMessage(
                parent=self._parent, title=title, message=message,
            )
            notification.Show(timeout=timeout)
        except Exception:
            pass
