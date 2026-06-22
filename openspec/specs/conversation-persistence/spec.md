# Conversation Persistence Capability Specification

## Purpose

Defines the `Conversation` data class that holds the in-memory transcript of a
chat session and serializes it to/from UTF-8 JSON files in `data/`. Persistence
is the user's only way to come back to a previous conversation, so the
on-disk format MUST be stable across runs and MUST round-trip identically
(including base64 image payloads). The module is headless (no wx) and fully
testable.

## Requirements

### Requirement: Message Shape and Storage

`Conversation` SHALL maintain an internal `list[dict]` of messages where each
message has at least the keys `role` (str), `content` (str), and `timestamp`
(ISO 8601 UTC string). Messages MAY additionally carry an `images` key whose
value is a `list[str]` of base64-encoded image payloads.

#### Scenario: Add a user message

- GIVEN a fresh `Conversation`
- WHEN `conv.add_message("user", "Hola")` is called
- THEN `len(conv.messages) == 1`
- AND `conv.messages[0]["role"] == "user"`
- AND `conv.messages[0]["content"] == "Hola"`
- AND `conv.messages[0]["timestamp"]` matches the regex
  `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}`

#### Scenario: Add a user message with an image

- GIVEN a fresh `Conversation`
- WHEN `conv.add_message("user", "¿Qué ves?",
  images=["iVBORw0KGgoAAAANSUhEUg..."])` is called
- THEN `conv.messages[0]["images"] == ["iVBORw0KGgoAAAANSUhEUg..."]`

#### Scenario: Assistant message without images

- GIVEN a fresh `Conversation`
- WHEN `conv.add_message("assistant", "Hola, ¿en qué te ayudo?")` is called
- THEN `"images" not in conv.messages[0]`

### Requirement: API-shaped Message Extraction

`Conversation.get_messages_for_api()` SHALL return a `list[dict]` containing
only the keys Ollama needs: `role`, `content`, and (if present) `images`. The
`timestamp` key MUST be stripped because Ollama's API rejects unknown fields.

#### Scenario: Mixed messages

- GIVEN a `Conversation` with messages:
  1. `{"role": "system", "content": "Eres útil.", "timestamp": "..."}`
  2. `{"role": "user", "content": "Hola", "timestamp": "..."}`
  3. `{"role": "assistant", "content": "¿En qué te ayudo?",
     "timestamp": "..."}`
- WHEN `conv.get_messages_for_api()` is called
- THEN the result is
  `[{"role": "system", "content": "Eres útil."},
    {"role": "user", "content": "Hola"},
    {"role": "assistant", "content": "¿En qué te ayudo?"}]`
- AND no `timestamp` key is present in any returned dict

#### Scenario: API payload preserves images

- GIVEN a message `{"role": "user", "content": "ver imagen",
  "images": ["AAAA"], "timestamp": "..."}`
- WHEN the conversation is queried via `get_messages_for_api()`
- THEN the returned message has key `images == ["AAAA"]`
- AND no `timestamp` key

### Requirement: In-memory Serialization — `to_dict` / `from_dict`

`Conversation.to_dict()` SHALL return a plain `dict` suitable for
`json.dumps`. `Conversation.from_dict(d)` SHALL be a `@classmethod` that
returns a new `Conversation` populated from `d`. Round-trip MUST be lossless
for all keys including `images`.

#### Scenario: Round-trip without images

- GIVEN a `Conversation` with two messages, no images
- WHEN `d = conv.to_dict()` then `conv2 = Conversation.from_dict(d)`
- THEN `conv2.messages == conv.messages`
- AND `len(conv2.messages) == 2`

#### Scenario: Round-trip with images

- GIVEN a `Conversation` with a user message carrying
  `images=["iVBORw0..."]`
- WHEN `d = conv.to_dict()` then `conv2 = Conversation.from_dict(d)`
- THEN `conv2.messages[0]["images"] == ["iVBORw0..."]`

### Requirement: Disk Persistence — `save` / `load`

`Conversation.save(filepath)` SHALL be a `@classmethod` that writes
`json.dumps(conv.to_dict(), indent=2, ensure_ascii=False)` to `filepath` with
`encoding="utf-8"`. `Conversation.load(filepath)` SHALL be a `@classmethod`
that reads the file, parses JSON, and returns a new `Conversation` via
`from_dict`. Missing file MUST raise `FileNotFoundError`.

#### Scenario: Save to disk

- GIVEN a `Conversation` with three messages including an image
- WHEN `Conversation.save(conv, tmp_path / "chat.json")` is called
- THEN `tmp_path / "chat.json"` exists
- AND the file contents parse as JSON equal to `conv.to_dict()`
- AND the file is encoded as UTF-8 (non-ASCII chars are NOT escaped — the JSON
  contains literal `"¿"` not `"\u00bf"`)

#### Scenario: Load from disk

- GIVEN a previously saved file at `tmp_path / "chat.json"`
- WHEN `conv2 = Conversation.load(tmp_path / "chat.json")` is called
- THEN `len(conv2.messages) == 3`
- AND `conv2.messages[0]["content"]` is identical to the original

#### Scenario: Load missing file raises

- GIVEN no file at `tmp_path / "missing.json"`
- WHEN `Conversation.load(tmp_path / "missing.json")` is called
- THEN `FileNotFoundError` is raised
- AND the error message contains the path string

### Requirement: Clear Conversation

`Conversation.clear()` SHALL empty the message list in place. The method MUST
return `None`. After `clear()`, `get_messages_for_api()` returns `[]`.

#### Scenario: Clear empties messages

- GIVEN a `Conversation` with two messages
- WHEN `conv.clear()` is called
- THEN `conv.messages == []`
- AND `conv.get_messages_for_api() == []`

#### Scenario: Clear allows re-use

- GIVEN a cleared `Conversation`
- WHEN `conv.add_message("user", "de nuevo")` is called
- THEN `len(conv.messages) == 1`
- AND `conv.messages[0]["content"] == "de nuevo"`
