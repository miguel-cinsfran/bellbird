"""Static/AST tests for WxToastSender — line-local wx.adv import.

Tests verify: ``import wx.adv`` is line-local (inside a function body),
the module defines a class named ``WxToastSender`` with a ``show()``
method, and no ``import wx`` at module scope.
"""

import ast
import pathlib


def _get_ui_path(filename: str) -> pathlib.Path:
    """Resolve the source file path for a UI module."""
    return (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "bellbird"
        / "ui"
        / filename
    )


def test_wx_notifier_class_exists():
    """wx_notifier.py defines a WxToastSender class."""
    source_path = _get_ui_path("wx_notifier.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "WxToastSender":
            found = True
            break

    assert found, "WxToastSender class not found in wx_notifier.py"


def test_show_method_exists():
    """WxToastSender has a show(self, title, message, timeout) method."""
    source_path = _get_ui_path("wx_notifier.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    found_show = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "WxToastSender":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "show":
                    params = [a.arg for a in item.args.args]
                    assert "self" in params
                    assert "title" in params
                    assert "message" in params
                    assert "timeout" in params
                    found_show = True
                    break

    assert found_show, (
        "WxToastSender must have a show(self, title, message, timeout) method"
    )


def test_wx_adv_not_at_module_scope():
    """No ``import wx.adv`` at module scope — must be line-local."""
    source_path = _get_ui_path("wx_notifier.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Only check top-level statements (module body), not those inside functions
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "wx.adv" not in alias.name, (
                    f"wx.adv import found at module scope (line {node.lineno})"
                )
        if isinstance(node, ast.ImportFrom):
            if node.module and "wx.adv" in node.module:
                assert False, (
                    f"wx.adv import found at module scope (line {node.lineno})"
                )


def test_wx_adv_imported_inside_show():
    """wx.adv is imported inside the show() method body under try/except."""
    source_path = _get_ui_path("wx_notifier.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    show_body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "WxToastSender":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "show":
                    show_body = item
                    break

    assert show_body is not None, "show() method not found"

    # Walk the show() body for import wx.adv
    import_found = False
    try_block_found = False
    for node in ast.walk(show_body):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "wx.adv" in alias.name:
                    import_found = True
        if isinstance(node, ast.Try):
            try_block_found = True

    assert import_found, (
        "wx.adv must be imported inside the show() method body"
    )
    # The import must be under try/except — the try block should be present
    assert try_block_found, (
        "show() must wrap wx.adv usage in a try/except block"
    )


def test_no_wx_import_at_module_level():
    """No ``import wx`` at module scope (only sys)."""
    source_path = _get_ui_path("wx_notifier.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "wx", (
                    f"wx imported at module scope (line {node.lineno})"
                )
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("wx"):
                # Allow 'import sys' but disallow 'from wx import ...'
                assert node.module != "wx", (
                    f"'from wx import' at module scope (line {node.lineno})"
                )
