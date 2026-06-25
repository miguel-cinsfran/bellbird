"""Tests for preferences_dialog.py utility functions — wx-free.

_parse_stop_text is defined in bellbird/ui/preferences_dialog.py but
depends only on built-in str methods. We extract it via source parsing
to avoid importing wx on WSL.
"""

import ast
import pathlib


def _get_parse_stop_text_source() -> str:
    """Extract the _parse_stop_text function source from preferences_dialog.py."""
    ui_path = (
        pathlib.Path(__file__).resolve().parent.parent.parent
        / "bellbird" / "ui" / "preferences_dialog.py"
    )
    source = ui_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_parse_stop_text":
            source_lines = source.splitlines()
            return "\n".join(source_lines[node.lineno - 1:node.end_lineno])

    raise AssertionError("_parse_stop_text function not found in preferences_dialog.py")


def _exec_parse_stop_text(source: str) -> object:
    """Compile _parse_stop_text and return the function object."""
    compiled = compile(source, "<test_parse_stop_text>", "exec")
    ns: dict[str, object] = {}
    exec(compiled, ns)
    return ns["_parse_stop_text"]


_parse_stop_text = _exec_parse_stop_text(_get_parse_stop_text_source())


class TestParseStopText:
    """Tests for _parse_stop_text(text: str) -> list[str]."""

    def test_empty_string_returns_empty_list(self):
        """GIVEN an empty string
        WHEN _parse_stop_text is called
        THEN it returns an empty list."""
        assert _parse_stop_text("") == []

    def test_multiline_with_common_stops(self):
        """GIVEN stop strings separated by newlines
        WHEN _parse_stop_text is called
        THEN it returns a list of stripped stop strings."""
        result = _parse_stop_text("</s>\n[/INST]\nUSER:\n")
        assert result == ["</s>", "[/INST]", "USER:"]

    def test_whitespace_lines_are_skipped(self):
        """GIVEN lines with whitespace-only and empty lines
        WHEN _parse_stop_text is called
        THEN whitespace-only lines are dropped and entries are stripped."""
        result = _parse_stop_text("  </s>  \n\n   \n[/INST]\n")
        assert result == ["</s>", "[/INST]"]

    def test_handles_crlf_from_copy_paste(self):
        """GIVEN CRLF line endings (from Windows copy-paste)
        WHEN _parse_stop_text is called
        THEN \\r is stripped from entries."""
        result = _parse_stop_text("\r\n</s>\r\n[/INST]\r\n")
        assert result == ["</s>", "[/INST]"]
