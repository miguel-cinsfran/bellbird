# Ollama Integration Capability Specification

## Purpose

Defines the `OllamaClient` headless module that talks to a local Ollama daemon
over HTTP. The client must (1) detect whether Ollama is running, (2) list
available models, and (3) stream chat completions token-by-token via NDJSON in
a background thread, with clean abort semantics and safe callback marshalling
to the wx main thread. This module is wx-free and therefore fully unit-tested
with stubbed HTTP responses.

## Requirements

### Requirement: Default Base URL and Construction

`OllamaClient` SHALL default its `base_url` to `"http://localhost:11434"`. The
constructor MUST accept an optional `base_url` override (string) and an
optional `requests.Session` for test injection; neither parameter is required.

#### Scenario: Default base URL

- GIVEN no constructor arguments
- WHEN `OllamaClient()` is instantiated
- THEN `client.base_url == "http://localhost:11434"`

#### Scenario: Custom base URL

- GIVEN a constructor argument `base_url="http://192.168.1.10:11434"`
- WHEN `OllamaClient(base_url="http://192.168.1.10:11434")` is instantiated
- THEN `client.base_url == "http://192.168.1.10:11434"`

### Requirement: Health Check — `check_running`

`OllamaClient.check_running()` SHALL return `True` iff a GET to
`{base_url}/api/tags` returns HTTP 200 within 5 seconds; otherwise `False`.
The method MUST NOT raise on connection errors, 4xx, or 5xx — it returns
`False` for any failure.

#### Scenario: Ollama up

- GIVEN a stubbed session whose GET to `/api/tags` returns 200 with body
  `{"models": []}`
- WHEN `client.check_running()` is called
- THEN the result is `True`

#### Scenario: Ollama down (connection refused)

- GIVEN a stubbed session whose GET to `/api/tags` raises `ConnectionError`
- WHEN `client.check_running()` is called
- THEN the result is `False`
- AND no exception propagates to the caller

#### Scenario: Ollama returns 5xx

- GIVEN a stubbed session whose GET to `/api/tags` returns 503
- WHEN `client.check_running()` is called
- THEN the result is `False`

### Requirement: Model Listing — `list_models`

`OllamaClient.list_models()` SHALL GET `{base_url}/api/tags` and return a
`list[str]` of model names parsed from the JSON response's `models[].name`
field. If the request fails or the response shape is unexpected, the method
MUST return an empty list (never raise).

#### Scenario: Two models returned

- GIVEN a stubbed session whose GET to `/api/tags` returns 200 with body
  `{"models": [{"name": "llama3:latest"}, {"name": "llava:13b"}]}`
- WHEN `client.list_models()` is called
- THEN the result is `["llama3:latest", "llava:13b"]`

#### Scenario: No models installed

- GIVEN a stubbed session returning `{"models": []}`
- WHEN `client.list_models()` is called
- THEN the result is `[]`

#### Scenario: Network error returns empty list

- GIVEN a stubbed session that raises `ConnectionError`
- WHEN `client.list_models()` is called
- THEN the result is `[]`

### Requirement: Streaming Chat — `chat_stream` Signature

`OllamaClient.chat_stream(model, messages, options, on_token, on_done, on_error)`
SHALL POST `{base_url}/api/chat` with `stream=True` and the body shape
`{"model": model, "messages": messages, "stream": True, "options": options}`.
The method MUST spawn a daemon `threading.Thread` and return immediately. The
streaming thread MUST iterate response lines one NDJSON object at a time, and
for each object that contains a non-empty `message.content` fragment, invoke
`on_token(fragment)` on the wx main thread (via `wx.CallAfter`).

#### Scenario: Two-token NDJSON stream

- GIVEN a stubbed `requests.post` whose response yields two lines:
  `{"message":{"role":"assistant","content":"Hola "},"done":false}\n`
  `{"message":{"role":"assistant","content":"mundo"},"done":true}\n`
- WHEN `chat_stream(...)` is called with a fake `wx.CallAfter` that records calls
- THEN exactly two `CallAfter` invocations to `on_token` are recorded
- AND the first receives `"Hola "`, the second receives `"mundo"`
- AND `CallAfter(on_done, ...)` is invoked exactly once after the last token

#### Scenario: on_done fires exactly once

- GIVEN any successful NDJSON stream (1+ tokens)
- WHEN the stream completes naturally
- THEN `on_done` is invoked exactly once with no arguments (or an empty dict)
- AND `on_error` is NOT invoked

#### Scenario: on_error fires on connection error

- GIVEN `requests.post` raises `ConnectionError`
- WHEN `chat_stream(...)` is called
- THEN `on_error` receives a string containing `"ConnectionError"`
- AND `on_done` is NOT invoked

### Requirement: Abort Semantics — `abort()`

`OllamaClient.abort()` SHALL set an internal `threading.Event` (`stop_event`)
that the streaming loop checks between NDJSON lines. When the event is set,
the loop MUST exit cleanly, invoke `on_done()` (not `on_error`), and not
invoke any further `on_token` callbacks.

#### Scenario: Abort stops the loop

- GIVEN a stubbed stream that yields 100 lines and the client is running
- WHEN `client.abort()` is called after 5 tokens have been received
- THEN at most 5 `on_token` callbacks fire
- AND `on_done` is invoked exactly once
- AND `on_error` is NOT invoked

#### Scenario: Abort before stream starts

- GIVEN `chat_stream` has been called but no lines have been received yet
- WHEN `client.abort()` is called
- THEN the loop exits before the first line is read
- AND `on_done` is invoked exactly once

### Requirement: Thread-safe Callback Marshalling

ALL three callbacks (`on_token`, `on_done`, `on_error`) MUST be invoked on the
wx main thread by wrapping each call in `wx.CallAfter(fn, *args)`. The
streaming thread MUST NEVER call the user's callback directly.

#### Scenario: Callbacks go through CallAfter

- GIVEN the streaming thread is producing tokens
- WHEN a token is ready
- THEN `wx.CallAfter(on_token, token)` is the call shape
- AND `on_token` is NOT invoked from the streaming thread directly

#### Scenario: Callback runs on main thread [windows-only]

- GIVEN the streaming thread emits a token
- WHEN `wx.CallAfter` dispatches the callback
- THEN `threading.current_thread() is threading.main_thread()` is `True` when
  `on_token` runs

### Requirement: Sampling Options

The `options` dict passed to `chat_stream` MUST support the keys `temperature`
(float), `num_predict` (int), `top_p` (float), `top_k` (int), and
`repeat_penalty` (float). These keys MUST be forwarded verbatim into the
`options` field of the POST body. Missing keys MUST be omitted (not sent as
`null`).

#### Scenario: Full options dict forwarded

- GIVEN `options = {"temperature": 0.7, "num_predict": 512, "top_p": 0.9,
  "top_k": 40, "repeat_penalty": 1.1}`
- WHEN `chat_stream` builds the request body
- THEN the body's `options` field equals `options` exactly
- AND the body's `model` and `messages` fields are present

#### Scenario: Partial options

- GIVEN `options = {"temperature": 0.3}` (only one key)
- WHEN `chat_stream` builds the request body
- THEN the body's `options` field equals `{"temperature": 0.3}` exactly
- AND no `null` values are sent for omitted keys

### Requirement: Vision — Images in Messages

`chat_stream` MUST forward any `images` key found on a message dict into the
POST body's `messages[].images` field. The `images` value is a `list[str]` of
base64-encoded PNG/JPEG bytes. Messages without `images` MUST be sent with no
`images` key (not `images: null`).

#### Scenario: User message with one image

- GIVEN a message `{"role": "user", "content": "¿Qué ves?",
  "images": ["iVBORw0KGgo..."]}`
- WHEN `chat_stream` builds the request body
- THEN the message in the body is
  `{"role": "user", "content": "¿Qué ves?", "images": ["iVBORw0KGgo..."]}`

#### Scenario: Message without images

- GIVEN a message `{"role": "assistant", "content": "Hola"}`
- WHEN `chat_stream` builds the request body
- THEN the message in the body has NO `images` key
- AND no `null` is sent for `images`
