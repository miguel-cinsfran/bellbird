"""Static/AST tests for VoiceDialog — accessibility compliance via source.

Tests verify: wx.Choice("voice_choice"), wx.Slider("rate_slider"),
OK/Cancel buttons with name=, preceding wx.StaticText, no GridSizer.
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


def test_voice_choice_present():
    """VoiceDialog has a wx.Choice with name='voice_choice'."""
    source_path = _get_ui_path("voice_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert 'name="voice_choice"' in source, (
        "VoiceDialog must have wx.Choice with name='voice_choice'"
    )


def test_rate_slider_present():
    """VoiceDialog has a wx.Slider with name='rate_slider'."""
    source_path = _get_ui_path("voice_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert 'name="rate_slider"' in source, (
        "VoiceDialog must have wx.Slider with name='rate_slider'"
    )


def test_ok_button_has_name():
    """OK button has name='voice_dialog_ok_button'."""
    source_path = _get_ui_path("voice_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert 'name="voice_dialog_ok_button"' in source, (
        "OK button must have name='voice_dialog_ok_button'"
    )


def test_cancel_button_has_name():
    """Cancel button has name='voice_dialog_cancel_button'."""
    source_path = _get_ui_path("voice_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    assert 'name="voice_dialog_cancel_button"' in source, (
        "Cancel button must have name='voice_dialog_cancel_button'"
    )


def test_choice_preceded_by_statictext():
    """wx.Choice('voice_choice') is preceded by a wx.StaticText('Voz:')."""
    source_path = _get_ui_path("voice_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find the Choice call inside a method
    choice_line = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _get_func_name(node)
            if func_name == "wx.Choice":
                has_voice_name = any(
                    kw.arg == "name"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value == "voice_choice"
                    for kw in node.keywords if kw.arg is not None
                )
                if has_voice_name:
                    choice_line = node.lineno
                    break

    assert choice_line is not None, (
        "wx.Choice with name='voice_choice' not found in AST"
    )

    # Check that a StaticText with 'Voz:' appears on a line before the Choice
    source_lines = source.splitlines()
    found_label = False
    for i in range(max(0, choice_line - 10), choice_line):
        line = source_lines[i]
        if "wx.StaticText" in line and "Voz:" in line:
            found_label = True
            break

    assert found_label, (
        "wx.Choice('voice_choice') must be preceded by "
        "wx.StaticText(label='Voz:') within 10 lines above"
    )


def test_slider_preceded_by_statictext():
    """wx.Slider('rate_slider') is preceded by wx.StaticText('Velocidad:')."""
    source_path = _get_ui_path("voice_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    slider_line = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _get_func_name(node)
            if func_name == "wx.Slider":
                has_rate_name = any(
                    kw.arg == "name"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value == "rate_slider"
                    for kw in node.keywords if kw.arg is not None
                )
                if has_rate_name:
                    slider_line = node.lineno
                    break

    assert slider_line is not None, (
        "wx.Slider with name='rate_slider' not found in AST"
    )

    source_lines = source.splitlines()
    found_label = False
    for i in range(max(0, slider_line - 10), slider_line):
        line = source_lines[i]
        if "wx.StaticText" in line and "Velocidad:" in line:
            found_label = True
            break

    assert found_label, (
        "wx.Slider('rate_slider') must be preceded by "
        "wx.StaticText(label='Velocidad:') within 10 lines above"
    )


def test_no_grid_sizer():
    """No GridSizer/FlexGridSizer/GridBagSizer in voice_dialog.py."""
    source_path = _get_ui_path("voice_dialog.py")
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
