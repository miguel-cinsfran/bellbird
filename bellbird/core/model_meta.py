"""Model metadata utilities — wx-free, strict TDD.

Provides auto-detection of multimodal projector (.mmproj) files
sibling to a given model file. The module is intentionally wx-free
so it can be unit-tested in environments without wxPython (e.g. WSL).
"""

from pathlib import Path


def find_mmproj_for_model(model_path: Path) -> Path | None:
    """Auto-detect an mmproj sibling file in the same directory as *model_path*.

    Patterns are checked in priority order (first match wins):
    1. ``mmproj-*.gguf`` — highest priority prefix
    2. ``*mmproj*.gguf`` — contains "mmproj"
    3. ``*.mmproj.gguf`` — lowest priority suffix

    Within a pattern, results are sorted alphabetically and the first
    match is returned. **Pattern 1 refuses to auto-pick when there are
    multiple matches** (returns ``None``) because picking the wrong
    projector silently breaks image handling for blind users. Patterns
    2 and 3 return the first alphabetical match without the multi-match
    guard.

    Args:
        model_path: Path to the model .gguf file.

    Returns:
        Resolved absolute ``Path`` to the detected mmproj file, or
        ``None`` if no unambiguous match is found.
    """
    parent = model_path.resolve().parent if model_path.parent != model_path else None
    if parent is None or not parent.is_dir():
        return None

    model_name = model_path.resolve().name

    # Pattern 1: mmproj-*.gguf (highest priority, multi-match guard)
    pattern1 = sorted(p for p in parent.glob("mmproj-*.gguf") if p.name != model_name)
    if len(pattern1) == 1:
        return pattern1[0].resolve()
    if len(pattern1) > 1:
        return None  # Refuse to auto-pick — blind users must never get a wrong projector

    # Pattern 2: *mmproj*.gguf (contains "mmproj" anywhere)
    pattern2 = sorted(
        p for p in parent.glob("*mmproj*.gguf")
        if p.name != model_name and not p.name.startswith("mmproj-")
    )
    if len(pattern2) >= 1:
        return pattern2[0].resolve()

    # Pattern 3: *.mmproj.gguf (suffix, lowest priority)
    pattern3 = sorted(
        p for p in parent.glob("*.mmproj.gguf")
        if p.name != model_name and "mmproj" not in p.name.replace(".mmproj.gguf", "")
    )
    if len(pattern3) >= 1:
        return pattern3[0].resolve()

    return None
