"""Static/AST tests for the _aborted abort flag in MainWindow.

Covers Task 4 (attribute declaration).

All tests parse bellbird/ui/main_window.py and verify structure via AST,
without importing wx at module level.
"""

import ast
from pathlib import Path


def _get_source() -> str:
    """Read main_window.py source."""
    return (
        Path(__file__).resolve().parent.parent.parent
        / "bellbird"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")


def test_aborted_attr_declared_in_init() -> None:
    """MainWindow.__init__ declares self._aborted = False."""
    src = _get_source()
    tree = ast.parse(src)

    init_method = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            init_method = node
            break

    assert init_method is not None, "__init__ not found"

    found = False
    for stmt in ast.walk(init_method):
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if (isinstance(target, ast.Attribute)
                        and target.attr == "_aborted"
                        and isinstance(stmt.value, ast.Constant)
                        and stmt.value.value is False):
                    found = True
                    break

    assert found, (
        "self._aborted = False must be declared in MainWindow.__init__"
    )
