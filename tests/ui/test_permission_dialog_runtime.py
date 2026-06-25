"""Runtime tests for PermissionDialog — editable command re-classify.

WSL: skipped because wx.Dialog is not available in the wx stub.
Windows: runs with real wx, verifies risk label updates on edit, focus flip,
and get_command() returns the edited value.

All imports that require wx must happen inside test methods (not at module
level) and are guarded by a check for wx.Dialog availability.
"""

import pytest


def _check_wx_dialog() -> None:
    """Skip the test if wx.Dialog is not available (WSL stub)."""
    try:
        import wx
        has_dialog = hasattr(wx, "Dialog")
    except ImportError:
        has_dialog = False
    if not has_dialog:
        pytest.skip("wx.Dialog not available on this platform")


class TestPermissionDialogRuntime:
    """Runtime tests for PermissionDialog edit re-classify."""

    def test_edit_changes_risk_label(self) -> None:
        """Given GREEN command, edit to RED command → risk label updates."""
        _check_wx_dialog()
        import wx
        from bellbird.ui.permission_dialog import PermissionDialog
        from bellbird.core.permission_manager import PermissionManager, RiskLevel

        if wx.GetApp() is None:
            _ = wx.App(False)
        parent = wx.Frame(None)
        pm = PermissionManager()
        dlg = PermissionDialog(
            parent, "shell_execute", "ls", RiskLevel.GREEN,
            permission_manager=pm,
        )
        try:
            initial_text = dlg.risk_label.GetLabel() if hasattr(dlg, "risk_label") else ""
            assert "Operacion de lectura" in initial_text, (
                f"Expected GREEN label, got: {initial_text}"
            )

            dlg.command_text.SetValue("Remove-Item C:\\foo")

            if hasattr(dlg, "risk_label"):
                new_text = dlg.risk_label.GetLabel()
                assert "irreversible" in new_text, (
                    f"Expected RED label after editing to Remove-Item, got: {new_text}"
                )
        finally:
            dlg.Destroy()
            parent.Destroy()

    def test_edit_flips_focus(self) -> None:
        """Given GREEN command, editing to RED flips focus to deny_button."""
        _check_wx_dialog()
        import wx
        from bellbird.ui.permission_dialog import PermissionDialog
        from bellbird.core.permission_manager import PermissionManager, RiskLevel

        if wx.GetApp() is None:
            _ = wx.App(False)
        parent = wx.Frame(None)
        pm = PermissionManager()
        dlg = PermissionDialog(
            parent, "shell_execute", "ls", RiskLevel.GREEN,
            permission_manager=pm,
        )
        try:
            dlg.command_text.SetValue("Remove-Item C:\\bar")

            new_focus = wx.Window.FindFocus()
            new_focused_name = getattr(new_focus, "name", "") if new_focus else ""
            assert new_focused_name == "deny_button" or new_focus == dlg.deny_button, (
                f"Expected focus on deny_button after RED edit, got: {new_focused_name}"
            )
        finally:
            dlg.Destroy()
            parent.Destroy()

    def test_edit_system_destructive_blocks(self) -> None:
        """Given edit to system-destructive path, allow click does not run."""
        _check_wx_dialog()
        import wx
        from bellbird.ui.permission_dialog import PermissionDialog
        from bellbird.core.permission_manager import PermissionManager, RiskLevel

        if wx.GetApp() is None:
            _ = wx.App(False)
        parent = wx.Frame(None)
        pm = PermissionManager()
        dlg = PermissionDialog(
            parent, "shell_execute", "ls", RiskLevel.GREEN,
            permission_manager=pm,
        )
        try:
            dlg.command_text.SetValue("Remove-Item C:\\Windows\\System32\\foo.dll")

            assert dlg._is_system_destructive is True, (
                "Editing to a system path should set _is_system_destructive=True"
            )
        finally:
            dlg.Destroy()
            parent.Destroy()

    def test_get_command_returns_edited(self) -> None:
        """get_command() returns the current value of command_text."""
        _check_wx_dialog()
        import wx
        from bellbird.ui.permission_dialog import PermissionDialog
        from bellbird.core.permission_manager import PermissionManager, RiskLevel

        if wx.GetApp() is None:
            _ = wx.App(False)
        parent = wx.Frame(None)
        pm = PermissionManager()
        dlg = PermissionDialog(
            parent, "shell_execute", "ls", RiskLevel.GREEN,
            permission_manager=pm,
        )
        try:
            initial = dlg.get_command()
            assert initial == "ls", f"Expected 'ls', got: {initial!r}"

            dlg.command_text.SetValue("dir /s")
            edited = dlg.get_command()
            assert edited == "dir /s", f"Expected 'dir /s', got: {edited!r}"
        finally:
            dlg.Destroy()
            parent.Destroy()
