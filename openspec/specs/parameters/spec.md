# Parameters Capability Specification

## Purpose

Defines `ParamsPanel`, the left-hand side panel of `MainWindow` that exposes
the model selector, system prompt, and sampling parameters. Every control MUST
be labeled, named, and laid out in a vertical `wx.BoxSizer` so MSAA exposes
them to screen readers in a predictable top-to-bottom reading order. Sliders
must update their numeric label in real time and announce the new value via
`speech.speak(..., interrupt=False)` so the user hears the parameter as they
move it.

## Requirements

### Requirement: Panel Width and Layout

`ParamsPanel` SHALL be 280 pixels wide and SHALL use only `wx.BoxSizer`
(vertical for the panel root, horizontal for any grouped rows). No
`wx.GridSizer`, `wx.FlexGridSizer`, or `wx.GridBagSizer` is permitted
(see `accessibility-guidelines`).

#### Scenario: Panel construction [windows-only]

- GIVEN a `MainWindow` with a `SplitterWindow`
- WHEN `ParamsPanel(parent=split_window)` is constructed
- THEN `params_panel.GetMinWidth() == 280`
- AND `params_panel.GetSizer()` is a `wx.BoxSizer` with `wx.VERTICAL` orientation

### Requirement: Model Selector and Refresh

The panel SHALL provide a model `wx.Choice` named `model_selector` and a
button named `refresh_models_button` with the label "Actualizar modelos".
Both MUST be preceded in the sizer by `wx.StaticText("Modelo:")`.

#### Scenario: Initial model selector

- GIVEN a fresh `ParamsPanel`
- WHEN the panel is constructed
- THEN `model_selector.GetCount() == 0` (empty until `set_models` is called)
- AND `refresh_models_button.GetLabel() == "Actualizar modelos"`

#### Scenario: set_models repopulates and selects first

- GIVEN `model_selector` is empty
- WHEN `params.set_models(["llama3:latest", "llava:13b"])` is called
- THEN `model_selector.GetCount() == 2`
- AND `model_selector.GetString(0) == "llama3:latest"`
- AND `model_selector.GetString(1) == "llava:13b"`
- AND `model_selector.GetSelection() == 0`

#### Scenario: Refresh button emits event [windows-only]

- GIVEN `refresh_models_button` has focus
- WHEN the user activates it (Enter or Space)
- THEN the panel emits a `EVT_BUTTON` event with `event.GetId() ==
  refresh_models_button.GetId()`
- AND `MainWindow`'s handler calls `OllamaClient.list_models()` and feeds
  the result back via `set_models`

### Requirement: System Prompt Input

The panel SHALL provide a multiline `wx.TextCtrl` named `system_prompt`,
80 pixels tall, with `TE_MULTILINE` style, preceded by the `wx.StaticText`
label "Prompt de sistema:".

#### Scenario: Read and set system prompt

- GIVEN a fresh `ParamsPanel`
- WHEN `params.set_system_prompt("Eres un asistente en español.")`
- THEN `params.get_system_prompt() == "Eres un asistente en español."`
- AND `system_prompt.GetSize().height == 80`

### Requirement: Temperature Slider with Real-time Label and Speech

The panel SHALL provide a `wx.Slider` named `temperature_slider` with range
`0`–`200` (integer), default `70`, preceded by `wx.StaticText("Temperatura:")`
and followed by a `wx.StaticText` label named `temperature_label` showing the
formatted value (e.g. `"0.70"`). On every value change the panel MUST update
`temperature_label` and call `self._speech.speak(new_value_text,
interrupt=False)`.

#### Scenario: Slider value to label

- GIVEN `temperature_slider` is at 70
- WHEN the user drags it to 150
- THEN `temperature_label.GetLabel() == "1.50"`
- AND `self._speech.speak("1.50", interrupt=False)` was called once

#### Scenario: Default temperature

- GIVEN a fresh `ParamsPanel`
- WHEN the panel is constructed
- THEN `temperature_slider.GetValue() == 70`
- AND `temperature_label.GetLabel() == "0.70"`

#### Scenario: Slider integer-to-float mapping

- GIVEN `temperature_slider.GetValue() == 0`
- WHEN the formatted text is read
- THEN it equals `"0.00"` (slider value divided by 100, two decimals)

### Requirement: Max Tokens Spin Control

The panel SHALL provide a `wx.SpinCtrl` named `max_tokens_spin` with range
`64`–`8192`, default `512`, preceded by `wx.StaticText("Máximo de tokens:")`.

#### Scenario: Default max tokens

- GIVEN a fresh `ParamsPanel`
- WHEN the panel is constructed
- THEN `max_tokens_spin.GetValue() == 512`
- AND `max_tokens_spin.GetMin() == 64`
- AND `max_tokens_spin.GetMax() == 8192`

### Requirement: Top-p Slider with Real-time Label and Speech

The panel SHALL provide a `wx.Slider` named `top_p_slider` with range
`0`–`100`, default `90`, preceded by `wx.StaticText("Top-p:")` and followed
by a label `top_p_label` (e.g. `"0.90"`). Changes MUST call
`self._speech.speak(new_value_text, interrupt=False)`.

#### Scenario: Top-p value mapping

- GIVEN `top_p_slider` is at 90
- WHEN read
- THEN `top_p_label.GetLabel() == "0.90"`
- AND `get_params()["top_p"] == 0.9`

### Requirement: Top-k Spin Control

The panel SHALL provide a `wx.SpinCtrl` named `top_k_spin` with range
`1`–`200`, default `40`, preceded by `wx.StaticText("Top-k:")`.

#### Scenario: Default top-k

- GIVEN a fresh `ParamsPanel`
- WHEN the panel is constructed
- THEN `top_k_spin.GetValue() == 40`
- AND `top_k_spin.GetMin() == 1`
- AND `top_k_spin.GetMax() == 200`

### Requirement: Repeat Penalty Slider with Real-time Label and Speech

The panel SHALL provide a `wx.Slider` named `repeat_penalty_slider` with
range `100`–`200`, default `110`, preceded by
`wx.StaticText("Penalización de repetición:")` and followed by label
`repeat_penalty_label` (e.g. `"1.10"`). Changes MUST call
`self._speech.speak(new_value_text, interrupt=False)`.

#### Scenario: Repeat penalty value mapping

- GIVEN `repeat_penalty_slider` is at 110
- WHEN read
- THEN `repeat_penalty_label.GetLabel() == "1.10"`
- AND `get_params()["repeat_penalty"] == 1.1`

### Requirement: `get_params` Returns Typed Sampling Dict

`params.get_params()` SHALL return a `dict` with exactly the keys
`temperature` (float), `num_predict` (int), `top_p` (float), `top_k` (int),
and `repeat_penalty` (float), mapping current widget values. The method MUST
be callable from any thread (no wx dependencies in the return value).

#### Scenario: Default get_params

- GIVEN a fresh `ParamsPanel` (all defaults)
- WHEN `params.get_params()` is called
- THEN the result equals
  `{"temperature": 0.7, "num_predict": 512, "top_p": 0.9, "top_k": 40,
  "repeat_penalty": 1.1}`

#### Scenario: Types are correct

- GIVEN the user has changed temperature slider to 130
- WHEN `params.get_params()` is called
- THEN `isinstance(result["temperature"], float)` is `True`
- AND `isinstance(result["num_predict"], int)` is `True`
- AND `isinstance(result["top_k"], int)` is `True`
- AND `result["temperature"] == 1.3`

### Requirement: `get_model` and `get_system_prompt` Accessors

`params.get_model()` SHALL return the currently selected model name (string)
or `""` if none is selected. `params.get_system_prompt()` SHALL return the
current `system_prompt` text (string, may be empty).

#### Scenario: Selected model

- GIVEN `set_models(["llama3:latest", "llava:13b"])` was called and the user
  selected "llava:13b"
- WHEN `params.get_model()` is called
- THEN the result is `"llava:13b"`

#### Scenario: Empty system prompt

- GIVEN a fresh `ParamsPanel`
- WHEN `params.get_system_prompt()` is called
- THEN the result is `""`
