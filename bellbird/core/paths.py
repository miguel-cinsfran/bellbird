"""OS user-data directory helper — wx-free, strict TDD.

Single source of truth for runtime file persistence: config, logs,
and any future data live under the OS user-data directory via
``platformdirs``.
"""

from pathlib import Path

import platformdirs


def user_data_dir() -> Path:
    """Return the Bellbird user-data directory, creating it if missing.

    On Windows this resolves to ``%LOCALAPPDATA%\\Bellbird`` (no author
    segment). On Linux: ``~/.local/share/Bellbird``. The directory is
    created atomically (``mkdir(parents=True, exist_ok=True)``).
    """
    d = Path(platformdirs.user_data_dir("Bellbird", appauthor=False))
    d.mkdir(parents=True, exist_ok=True)
    return d
