"""Configuration persistence — wx-free, strict TDD."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "data" / "config.json"


@dataclass
class BellbirdConfig:
    """User preferences persisted to data/config.json."""

    temperature: float = 0.70
    max_tokens: int = 4096
    top_p: float = 0.90
    top_k: int = 40
    repeat_penalty: float = 1.10
    system_prompt: str = ""
    last_model: str = ""
    extra_model_folders: list[str] = field(default_factory=list)
    ctx_size: int = 4096
    n_gpu_layers: int = 99
    port: int = 8080
    confirm_new_conversation: bool = True
    tools_enabled: bool = False


_MIGRATIONS: dict[str, object] = {
    # max_tokens was 512 before v0.5.1 reasoning-model support. Any saved
    # config with the old default is silently bumped so reasoning models
    # can finish their thinking phase before producing output.
    "max_tokens": (512, 4096),
}


def load_config() -> BellbirdConfig:
    """Load config from CONFIG_PATH. Returns BellbirdConfig() on missing/
    corrupt file. Unknown JSON keys filtered by __dataclass_fields__.
    Applies one-time migrations for fields whose old default is known.
    """
    if not CONFIG_PATH.is_file():
        return BellbirdConfig()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        known = {f.name for f in BellbirdConfig.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        for field_name, (old_val, new_val) in _MIGRATIONS.items():
            if filtered.get(field_name) == old_val:
                filtered[field_name] = new_val
        return BellbirdConfig(**filtered)
    except (json.JSONDecodeError, OSError):
        return BellbirdConfig()


def save_config(config: BellbirdConfig, path: Path | None = None) -> None:
    """Atomic write of config to `path` (or CONFIG_PATH if None).

    Writes `.tmp` first, then `Path.replace` to target. Creates parent dir
    if missing. The `path` parameter exists for testability with `tmp_path`;
    the production call site uses the default (CONFIG_PATH).
    """
    target = path if path is not None else CONFIG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2, ensure_ascii=False)
    tmp.replace(target)
