"""AST/static tests for scripts/build_windows.sh.

All tests run in WSL without wxPython. They parse the shell script's
embedded heredocs and verify correctness of the generated artifacts
(bellbird.spec, build.bat, LEEME.txt) without executing PyInstaller.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_windows.sh"
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_HIDDEN_IMPORTS = [
    "wx",
    "wx.adv",
    "accessible_output2",
    "accessible_output2.outputs.auto",
    "requests",
    "markdown",
    "platformdirs",
    "gguf",
    "html.parser",
    "unicodedata",
]

NEW_HIDDEN_IMPORTS = [
    "wx.adv",
    "markdown",
    "platformdirs",
    "gguf",
    "html.parser",
    "unicodedata",
]


def _read_script() -> str:
    """Return the full text of the build script."""
    return SCRIPT.read_text(encoding="utf-8")


def _extract_heredoc(script_text: str, marker: str) -> str:
    """Return the body of the heredoc whose EOF marker is *marker*.

    Handles both quoted ``<<'MARKER'`` and unquoted ``<<MARKER`` forms.
    """
    pattern = rf"<<'?{re.escape(marker)}'?\n(.*?){re.escape(marker)}"
    match = re.search(pattern, script_text, re.DOTALL)
    if not match:
        pytest.fail(f"heredoc with marker {marker!r} not found")
    return match.group(1)


def _extract_spec(script_text: str) -> str:
    """Return the embedded bellbird.spec heredoc body."""
    return _extract_heredoc(script_text, "SPEC_EOF")


def _extract_bat(script_text: str) -> str:
    """Return the embedded build.bat heredoc body."""
    return _extract_heredoc(script_text, "BAT_EOF")


# ---------------------------------------------------------------------------
# REQ-BUILD-1: Kit generation — bash syntax
# ---------------------------------------------------------------------------


class TestBashSyntax:
    """REQ-BUILD-1: bash -n must pass."""

    def test_bash_syntax(self):
        """The script has valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"bash -n failed:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# REQ-BUILD-2: build.bat cleanup, error handling, uv preference
# ---------------------------------------------------------------------------


class TestBuildBat:
    """REQ-BUILD-2: build.bat contract."""

    def test_build_bat_has_cleanup_build(self):
        """build.bat removes build/ before PyInstaller."""
        bat = _extract_bat(_read_script())
        assert "rmdir /s /q build" in bat

    def test_build_bat_has_cleanup_dist(self):
        """build.bat removes dist/ before PyInstaller."""
        bat = _extract_bat(_read_script())
        assert "rmdir /s /q dist" in bat

    def test_build_bat_has_pycache_cleanup(self):
        """build.bat removes __pycache__ before PyInstaller."""
        bat = _extract_bat(_read_script())
        assert "rmdir /s /q __pycache__" in bat

    def test_cleanup_before_pyinstaller(self):
        """All cleanup commands appear before the pyinstaller call."""
        bat = _extract_bat(_read_script())
        pyinstaller_pos = bat.index("pyinstaller")
        assert "rmdir /s /q build" in bat[:pyinstaller_pos]
        assert "rmdir /s /q dist" in bat[:pyinstaller_pos]
        assert "rmdir /s /q __pycache__" in bat[:pyinstaller_pos]

    def test_build_bat_exits_nonzero_on_failure(self):
        """build.bat exits with /b 1 on error."""
        bat = _extract_bat(_read_script())
        assert "exit /b 1" in bat

    def test_build_bat_has_error_label(self):
        """build.bat has a :error label for failure control flow."""
        bat = _extract_bat(_read_script())
        assert ":error" in bat

    def test_build_bat_prefers_uv(self):
        """build.bat checks for uv and uses uv run pyinstaller."""
        bat = _extract_bat(_read_script())
        assert "where uv" in bat
        assert "uv run pyinstaller" in bat

    def test_build_bat_fallback_pip(self):
        """build.bat has a pip-based fallback for systems without uv."""
        bat = _extract_bat(_read_script())
        assert "pip install pyinstaller" in bat

    def test_build_bat_uses_bellbird_spec(self):
        """build.bat references bellbird.spec, not ollamachat.spec."""
        bat = _extract_bat(_read_script())
        assert "bellbird.spec" in bat
        assert "ollamachat.spec" not in bat


# ---------------------------------------------------------------------------
# REQ-BUILD-3: bellbird.spec declares windowed onedir with correct entry
# ---------------------------------------------------------------------------


class TestBellbirdSpec:
    """REQ-BUILD-3: spec configuration."""

    def test_spec_name_is_bellbird(self):
        """spec declares name='Bellbird'."""
        spec = _extract_spec(_read_script())
        assert "name='Bellbird'" in spec

    def test_spec_is_onedir(self):
        """spec produces a one-folder distribution (COLLECT block)."""
        spec = _extract_spec(_read_script())
        assert "COLLECT(" in spec

    def test_spec_console_false(self):
        """spec sets console=False (windowed app)."""
        spec = _extract_spec(_read_script())
        assert "console=False" in spec

    def test_spec_upx_false(self):
        """spec disables UPX compression."""
        spec = _extract_spec(_read_script())
        assert "upx=False" in spec

    def test_spec_entry_is_bellbird_main(self):
        """spec entry point is bellbird/main.py."""
        spec = _extract_spec(_read_script())
        assert "bellbird/main.py" in spec

    def test_spec_no_ollamachat_reference(self):
        """No mention of the old branding in the spec."""
        spec = _extract_spec(_read_script())
        assert "ollamachat" not in spec.lower()


# ---------------------------------------------------------------------------
# REQ-BUILD-4: hidden imports, datas, excludes
# ---------------------------------------------------------------------------


class TestSpecHiddenImports:
    """REQ-BUILD-4: hiddenimports completeness."""

    def test_spec_hiddenimports_all_present(self):
        """All required hidden imports are present."""
        spec = _extract_spec(_read_script())
        hide_start = spec.index("hiddenimports=[")
        hide_end = spec.index("]", hide_start)
        block = spec[hide_start:hide_end + 1]
        for imp in REQUIRED_HIDDEN_IMPORTS:
            assert imp in block, (
                f"missing hidden import: {imp!r}"
            )

    def test_spec_new_hidden_imports_present(self):
        """The 6 new hidden imports (added in v0.11.0) are present."""
        spec = _extract_spec(_read_script())
        for imp in NEW_HIDDEN_IMPORTS:
            assert imp in spec, (
                f"missing new hidden import: {imp!r}"
            )


class TestSpecDatas:
    """REQ-BUILD-4: datas bundles sound assets."""

    def test_spec_datas_bundles_sounds(self):
        """spec datas includes the WAV glob pattern and the correct
        destination. The destination MUST be ``bellbird/data/sounds/default``
        (with the ``bellbird/`` prefix) because ``core/sound_player.py``
        resolves sounds via ``Path(__file__).parent.parent / "data" / "sounds"``
        and ``__file__`` is the sound_player module under the package.

        Under a frozen PyInstaller build, the package layout is preserved
        (bellbird/core/sound_player.pyc is at Bellbird/bellbird/core/), so
        the bundled datas must land at Bellbird/bellbird/data/sounds/default/.
        A destination of just ``data/sounds/default`` would land them at
        Bellbird/data/sounds/default/ and ``Path.is_file()`` would silently
        return False, breaking notification sounds with no error."""
        spec = _extract_spec(_read_script())
        assert "bellbird/data/sounds/default/*.wav" in spec
        assert "'bellbird/data/sounds/default'" in spec, (
            "datas destination must include the 'bellbird/' prefix; "
            "see sound_player.py path resolution"
        )

    def test_spec_datas_non_empty(self):
        """spec datas list is not empty."""
        spec = _extract_spec(_read_script())
        datas_start = spec.index("datas=[")
        datas_end = spec.index("]", datas_start)
        block = spec[datas_start:datas_end + 1]
        assert block != "datas=[]", "datas list must not be empty"


class TestSpecExcludes:
    """REQ-BUILD-4: excludes baseline."""

    def test_spec_excludes_baseline(self):
        """spec excludes the four standard modules."""
        spec = _extract_spec(_read_script())
        excludes_start = spec.index("excludes=[")
        excludes_end = spec.index("]", excludes_start)
        block = spec[excludes_start:excludes_end + 1]
        for mod in ("tkinter", "unittest", "pydoc", "doctest"):
            assert mod in block, (
                f"missing exclude: {mod!r}"
            )


# ---------------------------------------------------------------------------
# REQ-BUILD-5: pyproject.toml declares pyinstaller in dev with marker
# ---------------------------------------------------------------------------


class TestPyproject:
    """REQ-BUILD-5: pyproject.toml contract."""

    @pytest.fixture
    def data(self):
        with open(PYPROJECT, "rb") as fh:
            return tomllib.load(fh)

    def test_pyinstaller_in_dev_with_marker(self, data):
        """pyinstaller is declared in dev group with sys_platform marker."""
        dev_deps = data.get("dependency-groups", {}).get("dev", [])
        found = [d for d in dev_deps if d.startswith("pyinstaller")]
        assert len(found) == 1, (
            f"expected exactly 1 pyinstaller entry, got {len(found)}: {found}"
        )
        entry = found[0]
        assert "; sys_platform == 'win32'" in entry

    def test_no_pyinstaller_in_runtime_deps(self, data):
        """pyinstaller is NOT in production dependencies."""
        runtime_deps = data.get("project", {}).get("dependencies", [])
        pyinst = [d for d in runtime_deps if d.startswith("pyinstaller")]
        assert len(pyinst) == 0, (
            f"pyinstaller found in [project].dependencies: {pyinst}"
        )

    def test_version_unchanged(self, data):
        """pyproject.toml version stays at 0.11.0."""
        version = data.get("project", {}).get("version")
        assert version == "0.11.0", (
            f"expected version 0.11.0, got {version!r}"
        )

    def test_pyproject_parses_ok(self, data):
        """pyproject.toml is valid TOML (parsing already succeeded)."""
        assert data is not None


# ---------------------------------------------------------------------------
# REQ-BUILD-6: README documents the build workflow
# ---------------------------------------------------------------------------


class TestReadme:
    """REQ-BUILD-6: README build section."""

    def test_readme_has_build_section(self):
        """README.md contains a 'Build' section header."""
        text = README.read_text(encoding="utf-8")
        assert "## Build" in text

    def test_readme_refers_to_build_script(self):
        """README references scripts/build_windows.sh."""
        text = README.read_text(encoding="utf-8")
        assert "scripts/build_windows.sh" in text

    def test_readme_mentions_bellbird_exe(self):
        """README mentions the final executable artifact."""
        text = README.read_text(encoding="utf-8")
        assert "Bellbird.exe" in text


# ---------------------------------------------------------------------------
# Global script-level assertions
# ---------------------------------------------------------------------------


class TestGlobalAssertions:
    """Cross-cutting checks on the script."""

    def test_script_no_ollamachat_reference(self):
        """The script no longer references ollamachat."""
        script = _read_script().lower()
        # The LEEME heredoc still has 'ollama' (the server), that's fine.
        # But 'ollamachat' as a product name must be gone.
        assert "ollamachat" not in script, (
            "script still contains 'ollamachat' branding"
        )

    def test_leeme_no_ollama_operational_instructions(self):
        """The LEEME.txt heredoc does not instruct the user to install
        or start ``Ollama`` — Bellbird uses ``llama-server`` from
        llama.cpp, not Ollama. Telling the user to ``ollama pull
        llama3.2`` or to click an "Iniciar Ollama" button that does
        not exist would lead them to install the wrong software and
        fail at runtime."""
        script = _read_script()
        leeme_start = script.index("BELLBIRD v${VERSION}")
        leeme_end = script.index("ATENCION", leeme_start) if "ATENCION" in script[leeme_start:] else len(script)
        leeme = script[leeme_start:leeme_end]
        # "ollama" the lowercase server command must not appear in
        # operational instructions. Bellbird's name contains the
        # substring "ollama" — but only in a few legitimate places
        # (the project name "Bellbird" itself doesn't, so a literal
        # "ollama pull" or "Iniciar Ollama" should be gone).
        assert "ollama pull" not in leeme.lower(), (
            "LEEME.txt still instructs the user to run 'ollama pull' — "
            "Bellbird uses llama-server, not Ollama"
        )
        assert "iniciar ollama" not in leeme.lower(), (
            "LEEME.txt still references an 'Iniciar Ollama' button — "
            "Bellbird uses 'Iniciar servidor' (F7) with llama-server"
        )

    def test_script_zip_name_is_bellbird(self):
        """The zip filename uses bellbird prefix."""
        script = _read_script()
        assert "bellbird_v${VERSION}" in script

    def test_script_build_dir_is_bellbird(self):
        """The build directory uses bellbird prefix."""
        script = _read_script()
        assert "bellbird_v${VERSION}" in script

    def test_script_header_refers_to_bellbird(self):
        """The script header docstring mentions Bellbird."""
        script = _read_script()
        # Shebang + first few comment lines (~3 lines) = ~90 chars
        assert "Bellbird" in script[:200]
