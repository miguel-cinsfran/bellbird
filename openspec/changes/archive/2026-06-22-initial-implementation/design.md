# Design: Initial Implementation of OllamaChat

## 1. Architecture Overview

### High-Level Module Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              main.py                                        │
│                         wx.App entry point                                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ creates
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ui/main_window.py                                   │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  wx.Frame 1100x700                                                   │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │  wx.SplitterWindow (horizontal)                                │  │  │
│  │  │  ┌──────────────────────┐  ┌──────────────────────────────┐   │  │  │
│  │  │  │  ui/params_panel.py  │  │  ui/chat_panel.py            │   │  │  │
│  │  │  │  (280px left)        │  │  (rest, right)               │   │  │  │
│  │  │  └──────────────────────┘  └──────────────────────────────┘   │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │  MenuBar (Archivo, Ayuda) | StatusBar (3 fields) | AcceleratorTable │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ owns & calls
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              core/                                          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────┐  │
│  │ ollama_client.py   │  │ conversation.py    │  │ speech.py            │  │
│  │ (wx-free)          │  │ (wx-free)          │  │ (wx-free)            │  │
│  │                    │  │                    │  │                      │  │
│  │ check_running()    │  │ add_message()      │  │ speak()              │  │
│  │ list_models()      │  │ get_messages_for_  │  │ announce_token_      │  │
│  │ chat_stream()      │  │   api()            │  │   chunk()            │  │
│  │ abort()            │  │ save() / load()    │  │ flush_token_buffer() │  │
│  └────────────────────┘  └────────────────────┘  └──────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ persists to
                                   ▼
                          ┌──────────────────┐
                          │ data/            │
                          │ conversations/   │
                          │   *.json         │
                          └──────────────────┘
```

### Layering Rules

| Layer | wx dependency | Testable in WSL | Notes |
|-------|---------------|-----------------|-------|
| `core/` | NO | YES | All 3 modules import nothing from wx |
| `ui/` | YES | NO | Windows-only; manual verification |
| `main.py` | YES | NO | Thin entry point |
| `data/` | NO | YES | Runtime directory, gitignored |

### Dependency Direction

```
main.py → ui/main_window.py → ui/chat_panel.py
                            → ui/params_panel.py
                            → core/ollama_client.py
                            → core/conversation.py
                            → core/speech.py
```

No circular dependencies. `ui/*` depends on `core/*`, never the reverse.

---

## 2. Module-by-Module Design

### 2.1 `ollamachat/main.py`

```python
import wx
from ollamachat.ui.main_window import MainWindow

class OllamaChatApp(wx.App):
    def OnInit(self) -> bool:
        frame = MainWindow(None, title="OllamaChat")
        frame.Show()
        return True

def main() -> None:
    app = OllamaChatApp()
    app.MainLoop()

if __name__ == "__main__":
    main()
```

**State**: None. Pure bootstrap.

### 2.2 `ollamachat/core/speech.py`

```python
class Speech:
    def __init__(self) -> None:
        self._output: Any = None
        self.is_silent: bool = True
        self._buffer: str = ""
        try:
            from accessible_output2.outputs.auto import Auto
            self._output = Auto()
            self.is_silent = False
        except Exception:
            self._output = None
            self.is_silent = True

    def speak(self, text: str, interrupt: bool = True) -> None: ...
    def output(self, text: str) -> None: ...
    def stop(self) -> None: ...
    def announce_token_chunk(self, token: str) -> None: ...
    def flush_token_buffer(self) -> None: ...
```

**Internal state**:
- `_output`: the `Auto()` instance or `None`
- `is_silent`: `True` if `_output is None`
- `_buffer`: accumulated token fragments awaiting flush

**Invariants**:
- Every public method catches all exceptions and returns `None`
- `announce_token_chunk` flushes on sentence terminators (`.`, `?`, `!`, `\n`) OR when `len(buffer) > 80`
- `flush_token_buffer` speaks buffer if non-empty, then clears

**Never-crash contract**: All methods wrapped in `try/except Exception: return None`.

### 2.3 `ollamachat/core/ollama_client.py`

```python
import threading
from typing import Callable, Any
import requests

class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        session: requests.Session | None = None
    ) -> None:
        self.base_url = base_url
        self._session = session or requests.Session()
        self._stop_event = threading.Event()
        self._stream_thread: threading.Thread | None = None

    def check_running(self) -> bool: ...
    def list_models(self) -> list[str]: ...
    def chat_stream(
        self,
        model: str,
        messages: list[dict],
        options: dict,
        on_token: Callable[[str], None],
        on_done: Callable[[], None],
        on_error: Callable[[str], None]
    ) -> None: ...
    def abort(self) -> None:
        self._stop_event.set()
```

**Internal state**:
- `_stop_event`: `threading.Event` for abort signaling
- `_stream_thread`: reference to the current streaming daemon thread

**Threading model**:
- `chat_stream` spawns a daemon `Thread(target=self._stream_worker, ...)`
- Worker iterates `response.iter_lines()`, checks `_stop_event.is_set()` between lines
- All callbacks wrapped in `wx.CallAfter(fn, *args)` before invocation
- Worker catches all exceptions, routes to `on_error` via `CallAfter`
- `on_done` fires exactly once on clean exit; `on_error` fires exactly once on failure; never both

**NDJSON parsing**:
```python
for line in response.iter_lines():
    if self._stop_event.is_set():
        break
    if not line:
        continue
    try:
        chunk = json.loads(line)
        content = chunk.get("message", {}).get("content", "")
        if content:
            wx.CallAfter(on_token, content)
    except json.JSONDecodeError:
        continue  # skip malformed line
```

### 2.4 `ollamachat/core/conversation.py`

```python
from datetime import datetime, timezone
import json
from pathlib import Path

class Conversation:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def add_message(
        self,
        role: str,
        content: str,
        images: list[str] | None = None
    ) -> None:
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if images:
            msg["images"] = images
        self.messages.append(msg)

    def get_messages_for_api(self) -> list[dict]:
        result = []
        for msg in self.messages:
            api_msg = {"role": msg["role"], "content": msg["content"]}
            if "images" in msg:
                api_msg["images"] = msg["images"]
            result.append(api_msg)
        return result

    def clear(self) -> None:
        self.messages.clear()

    def to_dict(self) -> dict:
        return {"messages": self.messages}

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        conv = cls()
        conv.messages = data.get("messages", [])
        return conv

    @classmethod
    def save(cls, conv: "Conversation", filepath: Path) -> None:
        tmp_path = filepath.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(conv.to_dict(), f, indent=2, ensure_ascii=False)
        tmp_path.replace(filepath)

    @classmethod
    def load(cls, filepath: Path) -> "Conversation":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
```

**Atomic write**: Write to `.tmp`, then `os.replace` via `Path.replace` (atomic on Windows NTFS).

### 2.5 `ollamachat/ui/main_window.py`

```python
import wx
from ollamachat.core.ollama_client import OllamaClient
from ollamachat.core.conversation import Conversation
from ollamachat.core.speech import Speech
from ollamachat.ui.params_panel import ParamsPanel
from ollamachat.ui.chat_panel import ChatPanel

class MainWindow(wx.Frame):
    def __init__(self, parent: wx.Window, title: str = "OllamaChat") -> None:
        super().__init__(parent, title=title, size=(1100, 700))
        self._client = OllamaClient()
        self._conversation = Conversation()
        self._speech = Speech()
        self._current_response: str = ""

        self._build_ui()
        self._build_menu()
        self._build_accelerators()
        self._create_status_bar()
        self._startup_check()

    def _build_ui(self) -> None: ...
    def _build_menu(self) -> None: ...
    def _build_accelerators(self) -> None: ...
    def _startup_check(self) -> None: ...
    def send_message(self) -> None: ...
    def _on_token(self, token: str) -> None: ...
    def _on_done(self) -> None: ...
    def _on_error(self, error_text: str) -> None: ...
    def abort_generation(self) -> None: ...
    def save_conversation(self) -> None: ...
    def load_conversation(self) -> None: ...
    def new_conversation(self) -> None: ...
```

**State**:
- `_client`: `OllamaClient` instance
- `_conversation`: current `Conversation`
- `_speech`: `Speech` instance
- `_current_response`: accumulated assistant response during streaming

**Startup flow**:
1. Call `_client.check_running()`
2. If `False`: show `MessageDialog` + `_speech.speak("No se puede conectar...", interrupt=True)`
3. If `True`: call `_client.list_models()`, pass to `params_panel.set_models()`

**Send flow**:
1. Read input from `chat_panel.get_input_text()`
2. Build API messages: system prompt (if non-empty) + `conversation.get_messages_for_api()` + new user message
3. Clear input, display user message
4. Call `_client.chat_stream(model, messages, options, on_token, on_done, on_error)`
5. Disable send/attach buttons

### 2.6 `ollamachat/ui/chat_panel.py`

```python
import wx
import base64
from pathlib import Path

class ChatPanel(wx.Panel):
    def __init__(self, parent: wx.Window, speech: "Speech") -> None:
        super().__init__(parent)
        self._speech = speech
        self._attached_images: list[str] = []
        self._attached_text: str | None = None

        self._build_ui()

    def _build_ui(self) -> None: ...
    def get_input_text(self) -> str: ...
    def _clear_input(self) -> None: ...
    def append_user_message(self, text: str) -> None: ...
    def append_assistant_prefix(self) -> None: ...
    def append_assistant_chunk(self, token: str) -> None: ...
    def start_generation(self) -> None: ...
    def end_generation(self) -> None: ...
    def attach_file(self, filepath: str) -> None: ...
    def get_attached_images(self) -> list[str]: ...
    def get_attached_text(self) -> str | None: ...
    def clear_attachment(self) -> None: ...
    def clear(self) -> None: ...
```

**State**:
- `_attached_images`: list of base64 strings (max 1 for MVP)
- `_attached_text`: optional text content from non-image file

**Attachment routing**:
- Image extensions (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`): read bytes, base64-encode, store in `_attached_images`
- Other extensions: read as UTF-8 text, store in `_attached_text`
- Re-attaching replaces previous attachment

### 2.7 `ollamachat/ui/params_panel.py`

```python
import wx

class ParamsPanel(wx.Panel):
    def __init__(self, parent: wx.Window, speech: "Speech") -> None:
        super().__init__(parent, size=(280, -1))
        self._speech = speech
        self._build_ui()

    def _build_ui(self) -> None: ...
    def set_models(self, models: list[str]) -> None: ...
    def get_model(self) -> str: ...
    def get_system_prompt(self) -> str: ...
    def set_system_prompt(self, text: str) -> None: ...
    def get_params(self) -> dict: ...
    def _on_slider_change(self, event: wx.CommandEvent) -> None: ...
```

**State**:
- Widget references: `model_selector`, `system_prompt`, `temperature_slider`, `temperature_label`, `top_p_slider`, `top_p_label`, `repeat_penalty_slider`, `repeat_penalty_label`, `max_tokens_spin`, `top_k_spin`

**Slider mapping**:
- `temperature_slider`: range 0–200, value / 100 → float (e.g., 70 → 0.70)
- `top_p_slider`: range 0–100, value / 100 → float (e.g., 90 → 0.90)
- `repeat_penalty_slider`: range 100–200, value / 100 → float (e.g., 110 → 1.10)

**`get_params()` return**:
```python
{
    "temperature": self.temperature_slider.GetValue() / 100.0,
    "num_predict": self.max_tokens_spin.GetValue(),
    "top_p": self.top_p_slider.GetValue() / 100.0,
    "top_k": self.top_k_spin.GetValue(),
    "repeat_penalty": self.repeat_penalty_slider.GetValue() / 100.0
}
```

---

## 3. Sequence Diagrams

### 3.1 Message Send Flow

```
User                ChatPanel           MainWindow          OllamaClient        Speech
 │                      │                    │                    │                │
 │  Enter key           │                    │                    │                │
 ├─────────────────────>│                    │                    │                │
 │                      │  send_message()    │                    │                │
 │                      ├───────────────────>│                    │                │
 │                      │                    │  Build API payload │                │
 │                      │                    │  (system + history │                │
 │                      │                    │   + new user msg)  │                │
 │                      │                    │                    │                │
 │                      │                    │  chat_stream(...)  │                │
 │                      │                    ├───────────────────>│                │
 │                      │                    │                    │  Spawn thread  │
 │                      │                    │                    │  POST /api/chat│
 │                      │                    │                    │                │
 │                      │                    │                    │  NDJSON line   │
 │                      │                    │                    │  parsed        │
 │                      │                    │                    │                │
 │                      │                    │  CallAfter(        │                │
 │                      │                    │   on_token, token) │                │
 │                      │  on_token(token)   │<───────────────────│                │
 │                      │<───────────────────│                    │                │
 │                      │                    │                    │                │
 │                      │  append_assistant_ │                    │                │
 │                      │  chunk(token)      │                    │                │
 │                      │                    │                    │                │
 │                      │  announce_token_   │                    │                │
 │                      │  chunk(token)      │                    │                │
 │                      ├────────────────────────────────────────────────────────>│
 │                      │                    │                    │     _buffer    │
 │                      │                    │                    │     accumulates│
 │                      │                    │                    │                │
 │                      │                    │                    │  Stream done   │
 │                      │                    │  CallAfter(        │                │
 │                      │                    │   on_done)         │                │
 │                      │  on_done()         │<───────────────────│                │
 │                      │<───────────────────│                    │                │
 │                      │                    │                    │                │
 │                      │                    │  flush_token_      │                │
 │                      │                    │  buffer()          │                │
 │                      │                    ├───────────────────────────────────>│
 │                      │                    │  speak("Respuesta  │                │
 │                      │                    │  completa",        │                │
 │                      │                    │  interrupt=True)   │                │
 │                      │                    ├───────────────────────────────────>│
 │                      │                    │                    │                │
 │                      │                    │  Save assistant    │                │
 │                      │                    │  msg to            │                │
 │                      │                    │  Conversation      │                │
 │                      │                    │                    │                │
 │                      │  end_generation()  │                    │                │
 │                      │<───────────────────│                    │                │
 │                      │  Re-enable buttons │                    │                │
```

### 3.2 Abort Flow

```
User                ChatPanel           MainWindow          OllamaClient        Stream Thread
 │                      │                    │                    │                    │
 │  Escape key          │                    │                    │                    │
 ├─────────────────────>│                    │                    │                    │
 │                      │  abort_generation()│                    │                    │
 │                      ├───────────────────>│                    │                    │
 │                      │                    │  abort()           │                    │
 │                      │                    ├───────────────────>│                    │
 │                      │                    │                    │  stop_event.set()  │
 │                      │                    │                    ├───────────────────>│
 │                      │                    │                    │                    │
 │                      │                    │                    │                    │  Check
 │                      │                    │                    │                    │  stop_event
 │                      │                    │                    │                    │  between
 │                      │                    │                    │                    │  lines
 │                      │                    │                    │                    │
 │                      │                    │                    │                    │  Event set
 │                      │                    │                    │                    │  → break
 │                      │                    │                    │                    │
 │                      │                    │                    │  CallAfter(        │
 │                      │                    │                    │   on_done)         │
 │                      │                    │  CallAfter(        │<───────────────────│
 │                      │                    │   on_done)         │                    │
 │                      │  on_done()         │<───────────────────│                    │
 │                      │<───────────────────│                    │                    │
 │                      │                    │                    │                    │
 │                      │  end_generation()  │                    │                    │
 │                      │<───────────────────│                    │                    │
 │                      │  Re-enable buttons │                    │                    │
```

**Critical**: `on_done` fires (not `on_error`) on clean abort. The stream thread exits the loop, does NOT raise an exception.

### 3.3 Startup Flow

```
MainWindow.__init__()
 │
 ├─> OllamaClient.check_running()
 │    │
 │    ├─> GET http://localhost:11434/api/tags
 │    │    │
 │    │    ├─> 200 OK → return True
 │    │    └─> Exception / non-200 → return False
 │    │
 │    └─> Result: True/False
 │
 ├─> if False:
 │    │
 │    ├─> wx.MessageDialog("No se puede conectar a Ollama...")
 │    │    └─> Show modal
 │    │
 │    └─> speech.speak("No se puede conectar...", interrupt=True)
 │
 └─> if True:
      │
      ├─> OllamaClient.list_models()
      │    │
      │    ├─> GET /api/tags
      │    │    │
      │    │    └─> Parse {"models": [{"name": "llama3:latest"}, ...]}
      │    │
      │    └─> return ["llama3:latest", "llava:13b"]
      │
      └─> params_panel.set_models(["llama3:latest", "llava:13b"])
           │
           ├─> model_selector.Clear()
           ├─> model_selector.Append("llama3:latest")
           ├─> model_selector.Append("llava:13b")
           └─> model_selector.SetSelection(0)
```

---

## 4. Threading & Concurrency Model

### Thread Lifecycle

| Thread | Purpose | Lifetime | Daemon? |
|--------|---------|----------|---------|
| Main thread | wx event loop | App lifetime | No |
| Stream thread | NDJSON parsing | Per `chat_stream` call | Yes |

### Synchronization Primitives

| Primitive | Purpose | Owner |
|-----------|---------|-------|
| `threading.Event` (`_stop_event`) | Abort signal | `OllamaClient` |
| `wx.CallAfter` | Marshal callbacks to main thread | Stream thread → Main thread |

### Callback Marshalling Rules

1. **ALL** callbacks (`on_token`, `on_done`, `on_error`) MUST be invoked via `wx.CallAfter`
2. Stream thread NEVER calls user callbacks directly
3. `wx.CallAfter` is thread-safe; it posts to the wx event queue
4. Callbacks execute on the main thread in the order they were posted

### Abort Semantics

```python
# Stream thread worker
def _stream_worker(self, ...):
    try:
        response = self._session.post(...)
        for line in response.iter_lines():
            if self._stop_event.is_set():
                break
            if not line:
                continue
            # parse NDJSON, call on_token via CallAfter
        wx.CallAfter(on_done)
    except Exception as e:
        wx.CallAfter(on_error, str(e))
```

**Key**: `stop_event` is checked BETWEEN lines, not during parsing. This avoids race conditions mid-parse.

### Single-Fire Guarantee

- `on_done` and `on_error` are mutually exclusive
- Stream thread uses a `finally` block or explicit flag to ensure only one fires
- If abort happens cleanly, `on_done` fires; if exception occurs, `on_error` fires

---

## 5. Error Handling Strategy

### Error Categories & Routing

| Error Type | Source | Handler | User Feedback |
|------------|--------|---------|---------------|
| `requests.ConnectionError` | `check_running`, `list_models`, `chat_stream` | Return `False` / `[]` / `on_error` | Status bar / dialog / speech |
| HTTP non-200 | `check_running`, `list_models`, `chat_stream` | Return `False` / `[]` / `on_error` with status code | Dialog + speech |
| NDJSON parse error | `chat_stream` line parsing | Skip line, continue | None (silent) |
| Stream interrupted | `chat_stream` mid-read | `on_error` with partial-info message | Dialog + speech |
| Speech exception | Any `Speech` method | Swallow internally | None (silent) |
| File read error | `Conversation.load` | Raise `FileNotFoundError` | Dialog + speech |
| Ollama down at startup | `check_running` returns `False` | `MessageDialog` + `speech.speak` | Modal dialog + speech |

### Never-Crash Contract

**`Speech` module**: Every public method catches all exceptions and returns `None`. The app NEVER crashes due to TTS failure.

**`OllamaClient.check_running` / `list_models`**: Catch all exceptions, return `False` / `[]`. Never raise.

**`OllamaClient.chat_stream`**: Stream thread catches all exceptions, routes to `on_error` via `CallAfter`. Main thread never sees the exception.

### Error Message Format

- Network errors: `"ConnectionError: {detail}"`
- HTTP errors: `"HTTP {status_code}: {reason}"`
- Stream errors: `"Stream interrupted after {N} tokens: {detail}"`
- File errors: `"Cannot read file: {filepath}"`

---

## 6. Persistence Model

### Directory Structure

```
ollamachat/
└── data/
    └── conversations/
        ├── 2026-06-22-chat1.json
        ├── 2026-06-22-chat2.json
        └── ...
```

**Note**: `data/` is gitignored. Users save/load via file dialogs; the directory is a default location, not a hard requirement.

### File Format

```json
{
  "messages": [
    {
      "role": "user",
      "content": "Hola",
      "timestamp": "2026-06-22T10:30:45.123456+00:00"
    },
    {
      "role": "assistant",
      "content": "Hola, ¿en qué te ayudo?",
      "timestamp": "2026-06-22T10:30:46.789012+00:00"
    },
    {
      "role": "user",
      "content": "¿Qué ves?",
      "timestamp": "2026-06-22T10:31:00.000000+00:00",
      "images": ["iVBORw0KGgoAAAANSUhEUg..."]
    }
  ]
}
```

**Keys**:
- `messages`: array of message objects
- Each message: `role` (str), `content` (str), `timestamp` (ISO 8601 UTC), optional `images` (list of base64 strings)

### Atomic Write

```python
@classmethod
def save(cls, conv: "Conversation", filepath: Path) -> None:
    tmp_path = filepath.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(conv.to_dict(), f, indent=2, ensure_ascii=False)
    tmp_path.replace(filepath)  # atomic on NTFS
```

**Why**: Prevents corruption if the app crashes mid-write. The `.tmp` file is written first; only after it's complete is it renamed to the target path.

### Encoding

- UTF-8 explicit: `encoding="utf-8"` on all `open` calls
- `ensure_ascii=False`: non-ASCII characters are written as-is (e.g., `"¿"` not `"\u00bf"`)
- `indent=2`: human-readable formatting

### Round-Trip Guarantee

`Conversation.save(conv, path)` followed by `Conversation.load(path)` MUST produce an identical `Conversation` object, including all `images` payloads.

---

## 7. Accessibility Enforcement

### Manual Review Checklist (for `ui/*.py`)

Since there is no automated lint for accessibility in the MVP, the apply agent MUST verify each of these manually:

#### Control Naming

- [ ] Every interactive widget (`wx.Button`, `wx.TextCtrl`, `wx.Slider`, `wx.SpinCtrl`, `wx.Choice`, `wx.ListBox`, `wx.CheckBox`, `wx.RadioButton`) is created with `name="widget_name"`
- [ ] Widget names are unique within the window
- [ ] Widget names are descriptive, snake_case (e.g., `send_button`, `temperature_slider`)

#### Label Precedence

- [ ] Every interactive widget is preceded in the sizer by a `wx.StaticText` label
- [ ] Labels describe the control's purpose (e.g., `"Temperatura:"`, `"Mensaje:"`)
- [ ] Labels appear immediately before the control in sizer construction order

#### Sizer Type

- [ ] Only `wx.BoxSizer` is used (horizontal and vertical)
- [ ] No `wx.GridSizer`, `wx.FlexGridSizer`, or `wx.GridBagSizer` anywhere in `ui/`
- [ ] Verified via `grep` or AST inspection

#### Slider Speech Feedback

- [ ] Every `wx.Slider` has an associated `wx.StaticText` label showing the current value
- [ ] On value change, the label is updated
- [ ] On value change, `speech.speak(value_text, interrupt=False)` is called

#### Status Bar Speech

- [ ] `MainWindow` has a `wx.StatusBar` with 3 fields
- [ ] Every status bar update triggers `speech.speak(new_text, interrupt=True)`

#### Error Dialog Speech

- [ ] Every `wx.MessageDialog` or `wx.MessageBox` is followed by `speech.speak(message, interrupt=True)`

#### No WebView

- [ ] No `import wx.html`, `import wx.webkit`, or `wx.WebView` anywhere in `ui/`
- [ ] Verified via `grep`

### Testing Strategy for Accessibility

Since `ui/` is Windows-only, accessibility tests are manual. The apply agent MUST:
1. Run the app on Windows 11 with NVDA or JAWS
2. Navigate every control using Tab / Shift+Tab
3. Verify each control is announced correctly
4. Verify slider changes are spoken
5. Verify status bar updates are spoken
6. Verify error dialogs are spoken

---

## 8. Testing Strategy

### Test Layers

| Layer | Location | wx dependency | Testable in WSL | Approach |
|-------|----------|---------------|-----------------|----------|
| Unit (core) | `tests/core/` | NO | YES | Mocked HTTP, mocked `wx.CallAfter` |
| Smoke (speech) | `tests/smoke/` | NO | YES | Mocked `accessible_output2` |
| UI (manual) | `tests/ui/` | YES | NO | Placeholder files with `# [windows-only]` |

### `tests/core/test_ollama_client.py`

**Coverage**:
- `check_running`: 200 OK → `True`, 503 → `False`, `ConnectionError` → `False`
- `list_models`: 2 models → list, empty → `[]`, error → `[]`
- `chat_stream`: NDJSON dispatch, `wx.CallAfter` wrapping, abort via `Event`, single `on_done` / `on_error`
- Options forwarding: full dict, partial dict, no `null` values
- Vision: `images` key preserved, no `images` → no key

**Mocking strategy**:
```python
import pytest
from unittest.mock import Mock, patch
import threading

@pytest.fixture
def mock_call_after():
    """Capture wx.CallAfter calls for assertion."""
    calls = []
    def fake_call_after(fn, *args):
        calls.append((fn, args))
    with patch("wx.CallAfter", side_effect=fake_call_after):
        yield calls

@pytest.fixture
def mock_session():
    """Inject a fake requests.Session."""
    return Mock(spec=requests.Session)
```

**Abort test**:
```python
def test_abort_stops_stream(mock_session, mock_call_after):
    # Mock response that yields 100 lines with a delay
    def slow_iter_lines():
        for i in range(100):
            yield json.dumps({"message": {"content": f"token{i}"}, "done": False}).encode()
            time.sleep(0.01)
    
    mock_session.post.return_value.iter_lines.return_value = slow_iter_lines()
    
    client = OllamaClient(session=mock_session)
    on_token = Mock()
    on_done = Mock()
    on_error = Mock()
    
    client.chat_stream("model", [], {}, on_token, on_done, on_error)
    time.sleep(0.05)  # let a few tokens through
    client.abort()
    time.sleep(0.1)  # let thread exit
    
    assert on_token.call_count < 100
    assert on_done.call_count == 1
    assert on_error.call_count == 0
```

### `tests/core/test_conversation.py`

**Coverage**:
- `add_message`: user, assistant, with/without images
- `get_messages_for_api`: strips `timestamp`, preserves `images`
- `to_dict` / `from_dict`: round-trip with/without images
- `save` / `load`: round-trip, UTF-8, missing file → `FileNotFoundError`
- `clear`: empties messages, allows re-use

**Test with `tmp_path`**:
```python
def test_save_load_roundtrip(tmp_path):
    conv = Conversation()
    conv.add_message("user", "Hola")
    conv.add_message("assistant", "¿En qué te ayudo?")
    
    filepath = tmp_path / "chat.json"
    Conversation.save(conv, filepath)
    
    loaded = Conversation.load(filepath)
    assert loaded.messages == conv.messages
```

### `tests/core/test_speech.py`

**Coverage**:
- Constructor: `ImportError` → silent, `OSError` → silent, success → not silent
- `speak`: with output, silent, non-string text
- `output`: with output, silent
- `stop`: with output, silent
- `announce_token_chunk`: short token (no flush), sentence terminator (flush), 80-char fallback, question mark, newline
- `flush_token_buffer`: non-empty, empty
- Never-crash: `output.speak` raises → no exception, `output.output` raises → no exception

**Mocking `accessible_output2`**:
```python
@pytest.fixture
def mock_auto():
    with patch("accessible_output2.outputs.auto.Auto") as mock:
        mock.return_value = Mock()
        yield mock

def test_speak_with_output(mock_auto):
    speech = Speech()
    speech.speak("Hola", interrupt=True)
    mock_auto.return_value.speak.assert_called_once_with("Hola", interrupt=True)
```

### `tests/smoke/test_speech_silent.py`

**Purpose**: Verify `Speech` doesn't crash when `accessible_output2` is missing.

```python
def test_speech_silent_on_import_error():
    with patch.dict("sys.modules", {"accessible_output2": None}):
        speech = Speech()
        assert speech.is_silent
        speech.speak("test")  # should not raise
        speech.announce_token_chunk("test")  # should not raise
```

### `tests/ui/` Placeholders

```python
# tests/ui/test_chat_panel.py
# [windows-only]
# Manual verification scenarios:
# - conversation_display is read-only
# - Enter sends message
# - Shift+Enter inserts newline
# - Escape aborts generation
```

### pytest Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-xvs --no-header --no-cov-on-fail"
```

---

## 9. Configuration & Dependencies

### `pyproject.toml` Structure

```toml
[project]
name = "ollamachat"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "wxpython>=4.2",
    "accessible-output2>=0.17",
    "requests>=2.31"
]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov"
]
```

### `requirements.txt` (Compatibility Shim)

```
wxpython>=4.2
accessible-output2>=0.17
requests>=2.31
```

**Note**: `requirements.txt` is a thin shim for users who don't use UV. It pins the same runtime deps. Dev deps are managed via `[dependency-groups]` in `pyproject.toml`.

### No Code Config File

- Ollama URL has a sensible default (`http://localhost:11434`)
- URL is settable via `OllamaClient(base_url=...)` constructor parameter
- No config file (e.g., `config.yaml`, `.env`) for MVP

---

## 10. Risks & Open Questions for Implementation

### Guidance for Apply Agent

#### When to Mock `wx.CallAfter` in Tests

**Rule**: Mock `wx.CallAfter` in ALL `core/` tests that involve `OllamaClient.chat_stream`. The stream thread posts callbacks via `CallAfter`; in tests, we want to capture these calls synchronously.

**Fixture**:
```python
@pytest.fixture
def mock_call_after():
    calls = []
    def fake_call_after(fn, *args):
        calls.append((fn, args))
        # Optionally invoke immediately for testing:
        # fn(*args)
    with patch("wx.CallAfter", side_effect=fake_call_after):
        yield calls
```

**Usage**:
```python
def test_chat_stream_dispatches_tokens(mock_call_after):
    # ... setup mock session ...
    client.chat_stream(...)
    # Assert on mock_call_after list
```

#### How to Test `threading.Event` Abort Deterministically

**Challenge**: The stream thread runs concurrently; timing is non-deterministic.

**Solution**: Use a mock `requests.post` that blocks on a `threading.Event` until the test releases it.

```python
def test_abort_before_stream_starts():
    block_event = threading.Event()
    
    def blocking_iter_lines():
        block_event.wait()  # block until test releases
        yield b'{"message": {"content": "token"}, "done": false}'
    
    mock_session.post.return_value.iter_lines.return_value = blocking_iter_lines()
    
    client = OllamaClient(session=mock_session)
    client.chat_stream(...)
    client.abort()  # set stop_event before thread reads first line
    block_event.set()  # release the thread
    
    # Thread should exit immediately without calling on_token
```

#### Vision: `images` List Forwarding

**Rule**: `images` list MUST preserve order. If a user attaches multiple images (future feature), they must appear in the API payload in the same order.

**Test**:
```python
def test_images_preserve_order():
    conv = Conversation()
    conv.add_message("user", "ver", images=["img1", "img2", "img3"])
    api_msgs = conv.get_messages_for_api()
    assert api_msgs[0]["images"] == ["img1", "img2", "img3"]
```

### Known Risks

| Risk | Mitigation |
|------|------------|
| WSL has no wx display | `core/` is wx-free; UI verified manually on Windows |
| `accessible-output2` behaves differently on WSL vs Windows | `Speech` swallows all exceptions; smoke test verifies silent mode |
| Vision model compatibility | Pass `images` only when attached; README notes vision model required |
| NDJSON parse error mid-stream | Skip malformed line, continue; don't crash |
| `Event` abort race with in-flight line | Checked between lines, not during parse |
| Atomic write fails on non-NTFS filesystem | `Path.replace` is atomic on NTFS; on other systems, it's best-effort |

### Open Questions

**None**. All design decisions are resolved. The apply agent has clear guidance on:
- Mocking `wx.CallAfter`
- Testing `threading.Event` abort
- Vision `images` forwarding
- Accessibility manual checks

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `ollamachat/main.py` | Create | App entry point |
| `ollamachat/core/speech.py` | Create | TTS wrapper, never-crash |
| `ollamachat/core/ollama_client.py` | Create | REST + NDJSON streaming |
| `ollamachat/core/conversation.py` | Create | JSON persistence |
| `ollamachat/ui/main_window.py` | Create | Top-level frame |
| `ollamachat/ui/chat_panel.py` | Create | Conversation display + input |
| `ollamachat/ui/params_panel.py` | Create | Model + sampling controls |
| `ollamachat/__init__.py` | Create | Package marker |
| `ollamachat/core/__init__.py` | Create | Package marker |
| `ollamachat/ui/__init__.py` | Create | Package marker |
| `tests/core/test_ollama_client.py` | Create | Unit tests |
| `tests/core/test_conversation.py` | Create | Unit tests |
| `tests/core/test_speech.py` | Create | Unit tests |
| `tests/smoke/test_speech_silent.py` | Create | Smoke test |
| `tests/ui/test_chat_panel.py` | Create | Placeholder (windows-only) |
| `tests/ui/test_params_panel.py` | Create | Placeholder (windows-only) |
| `tests/ui/test_main_window.py` | Create | Placeholder (windows-only) |
| `pyproject.toml` | Create | Project config |
| `requirements.txt` | Create | Deps shim |
| `README.md` | Create | Blind-user docs |
| `AGENTS.md` | Create | Project rules |
| `.gitignore` | Create | Exclude data/, .venv/, etc. |

**Total**: 22 new files, 0 modified, 0 deleted.

---

## Result Contract

**Status**: ✅ Design complete

**Executive Summary**:
- **Architecture**: 3-layer (main → ui → core), strict dependency direction, `core/` is wx-free and testable in WSL
- **Threading**: One daemon thread per `chat_stream`, `threading.Event` for abort, all callbacks via `wx.CallAfter`
- **Persistence**: Atomic JSON write (`.tmp` + `replace`), UTF-8, round-trip guaranteed
- **Accessibility**: Manual review checklist for `ui/`, no automated lint in MVP
- **Testing**: `core/` fully unit-tested with mocks, `ui/` is windows-only manual verification
- **Never-crash**: `Speech` and `OllamaClient.check_running` / `list_models` swallow all exceptions

**Artifacts**:
- `openspec/changes/initial-implementation/design.md` (this file)

**Next Recommended**: `sdd-tasks` (break design into implementation tasks)

**Risks**:
- WSL cannot test `ui/`; manual Windows verification required
- `accessible-output2` behavior may vary; `Speech` silent mode is the fallback
- Vision model compatibility not tested; README must document requirements

**Skill Resolution**:
- `sdd-design` skill loaded and followed
- OpenSpec convention applied
- All 7 specs reviewed and addressed
- Proposal approach mapped to concrete module design
