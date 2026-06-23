"""Static/AST tests for Windows High Contrast Mode compatibility (v0.5.1).

Many NVDA users activate High Contrast Mode in Windows (black on white
or white on black). If the app assigns colors explicitly via
SetBackgroundColour / SetForegroundColour / wx.Colour, those colors
override the OS theme and become illegible in High Contrast.

The rule is: NEVER assign colors explicitly. Let the OS control the
theme. wx.SystemSettings.GetColour(wx.SYS_COLOUR_*) is allowed because
it follows the active theme; hardcoded RGB/hex/named colours are not.

These tests are a regression guard: they fail the build if any UI file
re-introduces hardcoded colors, uses TE_RICH2 (Windows RichEdit, which
has inconsistent NVDA behaviour and adds nothing for plain text), or
applies a color override to PermissionDialog's risk_label.
"""

import ast
import pathlib


# ── Paths ──────────────────────────────────────────────────────────────────


def _ui_dir() -> pathlib.Path:
    """Resolve the bellbird/ui/ directory."""
    return (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "bellbird"
        / "ui"
    )


def _get_ui_path(filename: str) -> pathlib.Path:
    """Resolve the source file path for a UI module."""
    return _ui_dir() / filename


# ── AST helpers ────────────────────────────────────────────────────────────


def _get_attr_name(node: ast.AST) -> str:
    """Extract the dotted name from a nested attribute node."""
    if isinstance(node, ast.Attribute):
        return f"{_get_attr_name(node.value)}.{node.attr}"
    elif isinstance(node, ast.Name):
        return node.id
    return "<unknown>"


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


# ── Tests ──────────────────────────────────────────────────────────────────


def test_no_hardcoded_colours():
    """No .py under bellbird/ui/ uses SetBackgroundColour / SetForegroundColour
    with an argument that is NOT wx.NullColour or wx.SystemSettings.

    Hardcoded colors (RGB, hex, named) override the OS theme and break
    High Contrast Mode. The only acceptable argument to those setters
    is wx.NullColour (clear the override) or a colour returned by
    wx.SystemSettings.GetColour(...) (theme-aware).
    """
    forbidden_calls: list[str] = []
    ui_dir = _ui_dir()

    for py_file in sorted(ui_dir.glob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = _get_func_name(node)
            if func_name not in (
                "SetBackgroundColour",
                "SetForegroundColour",
            ):
                continue
            # We found a call. Inspect the first positional arg.
            if not node.args:
                # Keyword form like obj.SetBackgroundColour(colour=...)
                kw = next(
                    (k for k in node.keywords if k.arg == "colour"),
                    None,
                )
                if kw is None:
                    # No argument at all — not a hardcoded color, skip
                    # (e.g., the wx widgets expose a 0-arg form on some
                    # platforms; rare, but allow it)
                    continue
                arg_value = _get_attr_name(kw.value) if isinstance(
                    kw.value, ast.Attribute
                ) else None
            else:
                first = node.args[0]
                arg_value = (
                    _get_attr_name(first)
                    if isinstance(first, ast.Attribute)
                    else None
                )

            # Allow: wx.NullColour, wx.SystemSettings.GetColour(...)
            if arg_value in ("wx.NullColour",) or (
                arg_value and arg_value.startswith("wx.SystemSettings")
            ):
                continue

            # Reject everything else (RGB tuple, hex string, name, etc.)
            forbidden_calls.append(
                f"{py_file.name}:{node.lineno}: {func_name}({arg_value!r})"
            )

    assert not forbidden_calls, (
        "Hardcoded colour assignments override the OS theme and break "
        "Windows High Contrast Mode. Use wx.NullColour to clear the "
        "override, or wx.SystemSettings.GetColour(wx.SYS_COLOUR_*) to "
        "follow the active theme.\n"
        "Offending calls:\n  " + "\n  ".join(forbidden_calls)
    )


def test_stream_display_no_te_rich2():
    """chat_panel.py does NOT use wx.TE_RICH2 (v0.5.1 accessibility fix).

    wx.TE_RICH2 enables the Windows RichEdit control, which can have
    inconsistent behavior with NVDA and adds nothing here (the control
    is plain text, read-only). The change is in chat_panel.py at the
    stream_display TextCtrl constructor.
    """
    source_path = _get_ui_path("chat_panel.py")
    source = source_path.read_text(encoding="utf-8")
    assert "TE_RICH2" not in source, (
        "chat_panel.py must NOT use wx.TE_RICH2 (v0.5.1 audit) — it enables "
        "the Windows RichEdit control, which can be inconsistent with NVDA "
        "and adds nothing for a plain-text readonly display"
    )
    # Sanity: the stream_display widget must still exist with the
    # read-only style flag (so a future refactor that drops the widget
    # entirely is caught here too).
    assert 'name="Respuesta en curso"' in source, (
        "stream_display widget must still exist in chat_panel.py"
    )
    assert "TE_READONLY" in source, (
        "stream_display must still use TE_READONLY (read-only plain text)"
    )


def test_permission_dialog_no_colour_on_risk_label():
    """permission_dialog.py does NOT call SetForegroundColour or
    SetBackgroundColour inside the risk_label construction block.

    The risk classification (GREEN/YELLOW/RED) is conveyed via the
    text prefix ("Advertencia: ...") for YELLOW/RED. The GREEN level
    has no prefix and is differentiated by the absence of the warning
    word. A color override would be invisible to screen-reader users
    AND would break High Contrast Mode, so this test pins the
    constraint at the AST level.
    """
    source_path = _get_ui_path("permission_dialog.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find the StaticText call for the risk_label. The dialog builds
    # it inside _build_ui with name="risk_label".
    risk_label_node: ast.Call | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _get_func_name(node)
        if func_name not in ("wx.StaticText", "StaticText"):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "name"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value == "risk_label"
            ):
                risk_label_node = node
                break
        if risk_label_node is not None:
            break

    assert risk_label_node is not None, (
        "No wx.StaticText with name='risk_label' found in "
        "permission_dialog.py — expected one inside _build_ui"
    )

    # Walk the body of the enclosing function (_build_ui) and look for
    # colour-setter calls that follow the risk_label construction.
    # Simpler approach: ensure no SetForegroundColour/SetBackgroundColour
    # call exists anywhere in the file with a non-system argument.
    # The file is small (one dialog), so a file-wide check is cheap
    # and unambiguous.
    offending: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _get_func_name(node)
        if func_name not in (
            "SetForegroundColour",
            "SetBackgroundColour",
        ):
            continue
        if not node.args:
            continue
        first = node.args[0]
        arg_repr = (
            _get_attr_name(first)
            if isinstance(first, ast.Attribute)
            else f"<{type(first).__name__}>"
        )
        if arg_repr in ("wx.NullColour",) or arg_repr.startswith(
            "wx.SystemSettings"
        ):
            continue
        offending.append(
            f"Line {node.lineno}: {func_name}({arg_repr})"
        )

    assert not offending, (
        "permission_dialog.py must not apply colour overrides to the "
        "risk_label or any other widget — the dialog differentiates risk "
        "levels via TEXT (the 'Advertencia:' prefix on YELLOW/RED). A "
        "colour override would be invisible to screen-reader users and "
        "would break High Contrast Mode. Use a text prefix such as "
        "'¡PELIGRO!' if stronger emphasis is needed.\n"
        "Offending calls:\n  " + "\n  ".join(offending)
    )
