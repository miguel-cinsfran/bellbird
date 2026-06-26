"""Static (AST) tests for personas_dialog.py — runs in WSL without wx."""

import ast
import pathlib


def _src() -> str:
    return (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "bellbird" / "ui" / "personas_dialog.py"
    ).read_text(encoding="utf-8")


def test_imports_wx_at_module_level():
    """personas_dialog.py is a wx UI file and must import wx at module scope."""
    tree = ast.parse(_src())
    wx_imported = any(
        isinstance(node, ast.Import)
        and any(a.name == "wx" for a in node.names)
        for node in ast.walk(tree)
    )
    assert wx_imported, "personas_dialog.py must import wx at module level"


def test_listbox_present():
    assert "wx.ListBox" in _src()


def test_buttons_use_wx_button():
    src = _src()
    assert "wx.Button" in src


def test_statictext_before_listbox():
    src = _src()
    lbl_pos = src.find("lbl_list = wx.StaticText")
    lb_pos = src.find("self._listbox = wx.ListBox")
    assert lbl_pos < lb_pos, "StaticText label must appear before ListBox (UIA z-order)"


def test_statictext_before_nombre():
    src = _src()
    lbl_pos = src.find("lbl_nombre = wx.StaticText")
    ctrl_pos = src.find("self._txt_nombre = wx.TextCtrl")
    assert lbl_pos < ctrl_pos


def test_statictext_before_prompt():
    src = _src()
    lbl_pos = src.find("lbl_prompt = wx.StaticText")
    ctrl_pos = src.find("self._txt_prompt = wx.TextCtrl")
    assert lbl_pos < ctrl_pos


def test_apply_persona_imported():
    assert "apply_persona" in _src()


def test_wx_id_cancel_used_for_close():
    assert "wx.ID_CANCEL" in _src()
