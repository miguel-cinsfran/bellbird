# Chat Capability Specification

## Purpose

Defines the conversation panel widget that lets a blind user compose messages to
a local Ollama model, attach files (images or text), and read both their own
input and the assistant's streamed reply. The panel is the only place a user
hears the model's voice (via `speech.announce_token_chunk`) and the only place
they trigger send, stop, attach, and clear. All widgets are named and labeled
so MSAA exposes them to NVDA/JAWS in a predictable reading order.

## Requirements

### Requirement: Read-only Conversation Display

The chat panel SHALL provide a read-only multiline text control named
`conversation_display` that displays the full transcript of the current
conversation (both user and assistant turns, prefixed with `[Usuario]` and
`[Asistente]` respectively). The control MUST be created with style flags
`TE_MULTILINE | TE_READONLY | TE_RICH2` so NVDA can navigate it line by line.

#### Scenario: Append a user message

- GIVEN a `ChatPanel` with an empty `conversation_display`
- WHEN the panel calls `_append_message("Hola", role="user")`
- THEN the display's last line ends with the text `[Usuario] Hola`
- AND the display value contains the prefix `[Usuario]` exactly once

#### Scenario: Append an assistant token

- GIVEN a `ChatPanel` with display already containing `[Usuario] Hola\n`
- WHEN the panel receives a streamed token `"Hola "` via `on_token("Hola ")`
- THEN the display value is `[Usuario] Hola\n[Asistente] Hola `
- AND the appended text starts with the `[Asistente]` prefix only once (at the
  beginning of the assistant turn, not on each token)

#### Scenario: Display control is read-only [windows-only]

- GIVEN the chat panel is constructed on Windows
- WHEN a user attempts to type into `conversation_display` via keyboard
- THEN the widget does NOT accept the keystrokes (style is `TE_READONLY`)

### Requirement: Multiline Message Input

The chat panel SHALL provide an editable multiline text control named
`message_input` created with `TE_MULTILINE | TE_PROCESS_ENTER` so the user can
type multi-line prompts and trigger the send action with the Enter key. The
control MUST be paired with a preceding `wx.StaticText` label "Mensaje:" so
screen readers announce the field purpose before focus.

#### Scenario: Read user input

- GIVEN the user has typed `"¿Qué es Python?"` into `message_input`
- WHEN the panel calls `get_input_text()`
- THEN the returned string is exactly `"¿Qué es Python?"`
- AND the string preserves accented characters (UTF-8 preserved)

#### Scenario: Clear input after send

- GIVEN `message_input` contains `"Hola"`
- WHEN a send action is triggered
- THEN the panel calls `_clear_input()`
- AND `get_input_text()` returns the empty string

### Requirement: Horizontal Action Button Row

The chat panel SHALL display four buttons in a horizontal `wx.BoxSizer`, in this
order from left to right: Enviar, Detener, Adjuntar, Limpiar. Each button MUST
have a `name=` argument (`send_button`, `stop_button`, `attach_button`,
`clear_button`) and MUST be preceded in the sizer by a `wx.StaticText` label
(or the buttons are grouped under a single "Acciones" label) so MSAA exposes
them as a labeled group.

#### Scenario: Buttons disabled while generating

- GIVEN the panel is idle and no generation is in progress
- WHEN `start_generation()` is called
- THEN `send_button` and `attach_button` are disabled (`Enable(False)`)
- AND `stop_button` is enabled
- AND `clear_button` is enabled

#### Scenario: Buttons re-enabled after generation finishes

- GIVEN `start_generation()` was called and `stop_button` is enabled
- WHEN the `on_done` callback fires
- THEN `send_button`, `attach_button`, and `clear_button` are all enabled
- AND `stop_button` is disabled (no active generation to stop)

#### Scenario: Clear button wipes transcript

- GIVEN `conversation_display` contains `[Usuario] Hola\n[Asistente] Hola, ¿en qué te ayudo?`
- WHEN the user activates `clear_button`
- THEN the panel calls `conversation.clear()` and the display is empty
- AND `get_input_text()` returns the empty string

### Requirement: Attachment File Dialog and Payload Routing

The chat panel SHALL open a `wx.FileDialog` when `attach_button` is activated
and route the chosen file by extension: `jpg`, `jpeg`, `png`, `bmp`, `gif`
MUST be base64-encoded and added to the next user message under the `images`
key; any other extension MUST be read as UTF-8 text and appended to the
message body. The original filename MUST be announced via `speech.speak`.

#### Scenario: Attach a PNG image

- GIVEN the user clicks `attach_button` and selects `cat.png`
- WHEN `attach_file("cat.png")` runs
- THEN `self._attached_images` contains exactly one base64 string
- AND `self._attached_text` is `None`
- AND `speech.speak("Imagen adjuntada: cat.png", interrupt=True)` is called

#### Scenario: Attach a non-image file as text

- GIVEN the user selects `notes.txt` containing `"comprar leche"`
- WHEN `attach_file("notes.txt")` runs
- THEN `self._attached_text == "comprar leche"`
- AND `self._attached_images` is empty
- AND `speech.speak("Archivo de texto adjuntado: notes.txt", interrupt=True)` is called

#### Scenario: Re-attaching replaces previous attachment

- GIVEN `self._attached_images` already has one image from `cat.png`
- WHEN the user selects `dog.jpg`
- THEN `self._attached_images` contains exactly one base64 string
- AND the previous cat.png base64 is no longer present

### Requirement: Attachment Label Visibility

The chat panel SHALL display a `wx.StaticText` named `attachment_label` (with
a preceding "Adjunto:" label) showing the currently attached filename, or the
text "(ninguno)" when no file is attached. The label MUST update immediately
on attach and on clear.

#### Scenario: Initial label state

- GIVEN a fresh `ChatPanel`
- WHEN the panel is constructed
- THEN `attachment_label.GetLabel() == "(ninguno)"`

#### Scenario: Label updates on attach

- GIVEN `attachment_label` shows "(ninguno)"
- WHEN the user attaches `report.txt`
- THEN `attachment_label.GetLabel() == "report.txt"` within the same tick

### Requirement: Keyboard Handling for Input

The chat panel SHALL bind `message_input` so that pressing `Enter` triggers
the send action and pressing `Shift+Enter` inserts a newline (since
`TE_PROCESS_ENTER` swallows plain Enter). Pressing `Escape` while a generation
is in progress MUST abort the in-flight `OllamaClient.chat_stream` call.

#### Scenario: Enter sends a message [windows-only]

- GIVEN `message_input` contains `"Hola"` and the input has focus
- WHEN the user presses Enter (no Shift)
- THEN the panel triggers the send action exactly once
- AND the input is cleared

#### Scenario: Shift+Enter inserts newline [windows-only]

- GIVEN `message_input` has focus and contains `"line1"`
- WHEN the user presses Shift+Enter
- THEN the input value becomes `"line1\n"`
- AND the send action is NOT triggered

#### Scenario: Escape aborts generation [windows-only]

- GIVEN `chat_stream` is running and `stop_button` is enabled
- WHEN the user presses Escape
- THEN `OllamaClient.abort()` is invoked (sets the stop event)
- AND `on_done` fires with an `aborted=True` signal so the UI re-enables controls
