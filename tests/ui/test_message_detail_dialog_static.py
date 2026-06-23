"""Static/AST tests for MessageDetailDialog — accessibility compliance via source.

Tests verify: name= on all controls, BoxSizer only, MessageDialog ban.
"""

import ast
import pathlib


def _get_ui_path(filename: str) -> pathlib.Path:
    """Resolve the source file path for a UI module."""
    return (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "ollamachat"
        / "ui"
        / filename
    )


def _get_func_name(node: ast.Call) -> str:
    """Extract the full function name from a Call node."""
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Attribute):
            return f"{_get_attr_name(node.func.value)}.{node.func.attr}"
        elif isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}"
        return node.func.attr
    elif isinstance(node.func, ast.Name):
        return node.func.id
    return "<unknown>"


def _get_attr_name(node: ast.AST) -> str:
    """Extract the dotted name from a nested attribute node."""
    if isinstance(node, ast.Attribute):
        return f"{_get_attr_name(node.value)}.{node.attr}"
    elif isinstance(node, ast.Name):
        return node.id
    return "<unknown>"


def test_content_text_present():
    """MessageDetailDialog has a content_text TextCtrl."""
    source_path = _get_ui_path("message_detail_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert 'name="content_text"' in source or "name='content_text'" in source


def test_open_browser_button_present():
    """MessageDetailDialog has an open_browser_button Button."""
    source_path = _get_ui_path("message_detail_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert 'name="open_browser_button"' in source or "name='open_browser_button'" in source


def test_copy_button_present():
    """MessageDetailDialog has a copy_button Button."""
    source_path = _get_ui_path("message_detail_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert 'name="copy_button"' in source or "name='copy_button'" in source


def test_close_button_present():
    """MessageDetailDialog has a close_button Button."""
    source_path = _get_ui_path("message_detail_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert 'name="close_button"' in source or "name='close_button'" in source


def test_all_controls_have_name():
    """Every wx.Button and wx.TextCtrl call in the file has name=."""
    source_path = _get_ui_path("message_detail_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    widget_constructors = {"wx.Button", "wx.TextCtrl"}

    calls_without_name = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _get_func_name(node)
            if func_name in widget_constructors:
                has_name = any(
                    kw.arg == "name" for kw in node.keywords if kw.arg is not None
                )
                if not has_name:
                    calls_without_name.append(
                        f"Line {node.lineno}: {func_name} without name="
                    )

    assert not calls_without_name, (
        "Widgets missing name=:\n" + "\n".join(calls_without_name)
    )


def test_only_boxsizer_used():
    """No GridSizer/FlexGridSizer/GridBagSizer is used."""
    source_path = _get_ui_path("message_detail_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_sizers = {
        "wx.GridSizer",
        "wx.FlexGridSizer",
        "wx.GridBagSizer",
    }

    found_forbidden = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _get_func_name(node)
            if func_name in forbidden_sizers:
                found_forbidden.append(f"Line {node.lineno}: {func_name}")

    assert not found_forbidden, (
        "Forbidden sizers found:\n" + "\n".join(found_forbidden)
    )


def test_no_message_dialog():
    """MessageDetailDialog source must NOT contain MessageDialog tokens."""
    source_path = _get_ui_path("message_detail_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert "MessageDialog" not in source, (
        "MessageDetailDialog must not use wx.MessageDialog. "
        "Use wx.Dialog with native wx.Button widgets instead."
    )
