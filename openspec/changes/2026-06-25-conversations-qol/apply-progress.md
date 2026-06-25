# Apply Progress: 2026-06-25-conversations-qol

## WU-1: Core + Tests ✅ COMPLETED

- **Date**: 2026-06-25
- **Strategy**: single-pr (D2)
- **Execution**: auto (A2)

### Completed Tasks

| Task | Status | Files Changed |
|------|--------|---------------|
| 1.1 BellbirdConfig: 3 new fields | ✅ | `bellbird/core/config.py`, `tests/core/test_config.py` |
| 1.2 Conversation.to_markdown() | ✅ | `bellbird/core/conversation.py`, `tests/core/test_conversation.py` |
| 1.3 find_in_history() | ✅ | `bellbird/core/conversation.py`, `tests/core/test_conversation.py` |
| 1.4 Recents helpers + should_auto_restore | ✅ | `bellbird/core/config.py`, `tests/core/test_config.py` |
| 1.5 Version bump (pyproject.toml) | ✅ | `pyproject.toml` (already 0.8.2) |
| 1.6 find_in_history keymap entry | ✅ | `bellbird/core/keymap.py`, `tests/core/test_keymap.py` |

### Files Changed

| File | Lines Added | Lines Removed |
|------|-------------|---------------|
| `bellbird/core/config.py` | 55 | 0 |
| `bellbird/core/conversation.py` | 102 | 0 |
| `bellbird/core/keymap.py` | 1 | 0 |
| `tests/core/test_config.py` | 255 | 0 |
| `tests/core/test_conversation.py` | 172 | 0 |
| `tests/core/test_keymap.py` | 6 | 2 |
| **Total** | **591** | **2** |

### Tests Executed

- `tests/core/test_config.py`: 61/61 ✅
- `tests/core/test_conversation.py`: 57/57 ✅
- `tests/core/test_keymap.py`: 37/37 ✅
- `tests/core/test_llama_client.py`: 59/59 ✅
- `tests/core/test_llama_client_state.py`: 8/8 ✅
- `tests/core/test_html_render.py`: 11/11 ✅
- `tests/core/test_html_render_static.py`: 5/5 ✅

**Total**: 238/238 passed (excluding `test_llama_runner.py` which uses subprocess polling and times out in WSL)

### Commit

```
9971619... feat(core): add to_markdown, find_in_history, recents helpers, and find_in_history keymap
```

### Notes for WU-2

- `Conversation.to_markdown()` accepts optional `system_prompt` parameter
- `find_in_history()` uses **1-based** indexing — UI must convert ListBox 0-based to 1-based for start_index, and convert returned 1-based index back to 0-based for `SetSelection(index)`
- `update_recents()` and `remove_from_recents()` return new lists (pure functions, no mutation)
- `should_auto_restore(config)` checks toggle + path non-empty + file exists
- Keymap has `find_in_history` action id with default `Ctrl+F` — no UI handler yet
