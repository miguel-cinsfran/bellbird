"""Tests for OllamaClient module — strict TDD, RED first, then GREEN."""

import json
import sys
import threading
import time
import types
from unittest.mock import Mock, patch

import pytest
import requests


# ─── Wx module stub ──────────────────────────────────────────────────────────


def _ensure_wx_module():
    """Ensure wx module exists in sys.modules for patching wx.CallAfter."""
    if "wx" not in sys.modules:
        wx_mod = types.ModuleType("wx")

        def call_after(fn, *args):
            fn(*args)

        wx_mod.CallAfter = call_after
        sys.modules["wx"] = wx_mod


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def ensure_wx():
    """Ensure wx module is available for all tests."""
    _ensure_wx_module()
    yield


@pytest.fixture
def mock_session():
    """Inject a fake requests.Session."""
    return Mock(spec=requests.Session)


@pytest.fixture
def mock_call_after():
    """Capture wx.CallAfter calls for assertion."""
    calls = []

    def fake_call_after(fn, *args):
        calls.append((fn, args))
        # Invoke immediately so tests can assert on effects
        fn(*args)

    with patch("wx.CallAfter", side_effect=fake_call_after):
        yield calls


# ─── Constructor ──────────────────────────────────────────────────────────────


def test_default_base_url():
    """Given no constructor arguments, base_url defaults."""
    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient()
    assert client.base_url == "http://localhost:11434"


def test_custom_base_url():
    """Given a custom base_url, it's stored."""
    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(base_url="http://192.168.1.10:11434")
    assert client.base_url == "http://192.168.1.10:11434"


# ─── check_running ────────────────────────────────────────────────────────────


def test_check_running_ok(mock_session):
    """Given 200 OK, check_running returns True."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_session.get.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    assert client.check_running() is True


def test_check_running_connection_error(mock_session):
    """Given ConnectionError, check_running returns False."""
    mock_session.get.side_effect = requests.ConnectionError("refused")

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    assert client.check_running() is False


def test_check_running_5xx(mock_session):
    """Given 503, check_running returns False."""
    mock_response = Mock()
    mock_response.status_code = 503
    mock_session.get.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    assert client.check_running() is False


# ─── list_models ──────────────────────────────────────────────────────────────


def test_list_models_two(mock_session):
    """Given two models, list_models returns their names."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [{"name": "llama3:latest"}, {"name": "llava:13b"}]
    }
    mock_session.get.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    result = client.list_models()
    assert result == ["llama3:latest", "llava:13b"]


def test_list_models_empty(mock_session):
    """Given no models, list_models returns []."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"models": []}
    mock_session.get.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    assert client.list_models() == []


def test_list_models_network_error(mock_session):
    """Given ConnectionError, list_models returns []."""
    mock_session.get.side_effect = requests.ConnectionError("refused")

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    assert client.list_models() == []


# ─── chat_stream — NDJSON dispatch ────────────────────────────────────────────


def test_chat_stream_two_tokens(mock_session, mock_call_after):
    """Given a two-line NDJSON stream, on_token fires twice via CallAfter."""
    lines = [
        b'{"message":{"role":"assistant","content":"Hola "},"done":false}\n',
        b'{"message":{"role":"assistant","content":"mundo"},"done":true}\n',
    ]
    mock_response = Mock()
    mock_response.iter_lines.return_value = lines
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    on_token = Mock()
    on_done = Mock()
    on_error = Mock()

    client.chat_stream("model", [], {}, on_token, on_done, on_error)
    time.sleep(0.1)  # let thread finish

    assert on_token.call_count == 2
    assert on_token.call_args_list[0][0][0] == "Hola "
    assert on_token.call_args_list[1][0][0] == "mundo"

    # wx.CallAfter invocations for tokens + on_done
    callafter_token_calls = [
        c for c in mock_call_after if c[0] is on_token
    ]
    assert len(callafter_token_calls) == 2

    callafter_done_calls = [c for c in mock_call_after if c[0] is on_done]
    assert len(callafter_done_calls) == 1


def test_on_done_fires_once(mock_session, mock_call_after):
    """Given a successful stream, on_done fires and on_error does not."""
    lines = [
        b'{"message":{"role":"assistant","content":"token"},"done":true}\n',
    ]
    mock_response = Mock()
    mock_response.iter_lines.return_value = lines
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    on_done = Mock()
    on_error = Mock()

    client.chat_stream("model", [], {}, Mock(), on_done, on_error)
    time.sleep(0.1)

    assert on_done.call_count == 1
    assert on_error.call_count == 0


def test_on_error_on_connection_error(mock_session, mock_call_after):
    """Given ConnectionError in post, on_error fires with error text."""
    mock_session.post.side_effect = requests.ConnectionError("Connection refused")

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    on_done = Mock()
    on_error = Mock()

    client.chat_stream("model", [], {}, Mock(), on_done, on_error)
    time.sleep(0.1)

    assert on_error.call_count == 1
    assert "ConnectionError" in on_error.call_args[0][0]
    assert on_done.call_count == 0


# ─── abort semantics ──────────────────────────────────────────────────────────


def test_abort_stops_stream(mock_session, mock_call_after):
    """Given abort mid-stream, fewer than 100 tokens fire and on_done fires."""
    lines = 100

    def slow_iter_lines():
        for i in range(lines):
            yield json.dumps(
                {"message": {"content": f"token{i}"}, "done": False}
            ).encode()
            time.sleep(0.005)

    mock_response = Mock()
    mock_response.iter_lines.return_value = slow_iter_lines()
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    on_token = Mock()
    on_done = Mock()
    on_error = Mock()

    client.chat_stream("model", [], {}, on_token, on_done, on_error)
    time.sleep(0.03)  # let a few tokens through
    client.abort()
    time.sleep(0.1)  # let thread exit

    assert on_token.call_count < 100
    assert on_done.call_count == 1
    assert on_error.call_count == 0


def test_abort_before_stream_starts(mock_session, mock_call_after):
    """Given abort before any lines, loop exits cleanly and on_done fires."""
    block_event = threading.Event()

    def blocking_iter_lines():
        block_event.wait()  # block until test releases
        yield b'{"message": {"content": "token"}, "done": false}'

    mock_response = Mock()
    mock_response.iter_lines.return_value = blocking_iter_lines()
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    on_token = Mock()
    on_done = Mock()
    on_error = Mock()

    client.chat_stream("model", [], {}, on_token, on_done, on_error)
    client.abort()  # set stop_event before thread reads first line
    block_event.set()  # release the thread
    time.sleep(0.1)

    assert on_token.call_count == 0
    assert on_done.call_count == 1
    assert on_error.call_count == 0


# ─── options forwarding ────────────────────────────────────────────────────────


def test_full_options_forwarded(mock_session, mock_call_after):
    """Given full options dict, it appears in the POST body."""
    options = {
        "temperature": 0.7,
        "num_predict": 512,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
    }
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        b'{"message":{"role":"assistant","content":"ok"},"done":true}\n',
    ]
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    client.chat_stream("model", [], options, Mock(), Mock(), Mock())
    time.sleep(0.1)

    _, kwargs = mock_session.post.call_args
    body = kwargs["json"]
    assert body["options"] == options
    assert body["model"] == "model"
    assert body["messages"] == []


def test_partial_options(mock_session, mock_call_after):
    """Given partial options, only provided keys are sent, no nulls."""
    options = {"temperature": 0.3}
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        b'{"message":{"role":"assistant","content":"ok"},"done":true}\n',
    ]
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    client.chat_stream("model", [], options, Mock(), Mock(), Mock())
    time.sleep(0.1)

    _, kwargs = mock_session.post.call_args
    body = kwargs["json"]
    assert body["options"] == {"temperature": 0.3}
    assert "num_predict" not in body["options"]


# ─── vision: images forwarding ────────────────────────────────────────────────


def test_user_message_with_image(mock_session, mock_call_after):
    """Given a message with images, images key is forwarded."""
    messages = [
        {"role": "user", "content": "¿Qué ves?", "images": ["iVBORw0KGgo..."]}
    ]
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        b'{"message":{"role":"assistant","content":"ok"},"done":true}\n',
    ]
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    client.chat_stream("model", messages, {}, Mock(), Mock(), Mock())
    time.sleep(0.1)

    _, kwargs = mock_session.post.call_args
    body = kwargs["json"]
    assert body["messages"][0]["images"] == ["iVBORw0KGgo..."]


def test_message_without_images(mock_session, mock_call_after):
    """Given a message without images, no images key in body."""
    messages = [{"role": "assistant", "content": "Hola"}]
    mock_response = Mock()
    mock_response.iter_lines.return_value = [
        b'{"message":{"role":"assistant","content":"ok"},"done":true}\n',
    ]
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    client.chat_stream("model", messages, {}, Mock(), Mock(), Mock())
    time.sleep(0.1)

    _, kwargs = mock_session.post.call_args
    body = kwargs["json"]
    assert "images" not in body["messages"][0]


# ─── CallAfter marshalling ────────────────────────────────────────────────────


def test_callbacks_go_through_callafter(mock_session, mock_call_after):
    """Given token events, calls go through wx.CallAfter, not directly."""
    lines = [
        b'{"message":{"role":"assistant","content":"A"},"done":false}\n',
        b'{"message":{"role":"assistant","content":"B"},"done":true}\n',
    ]
    mock_response = Mock()
    mock_response.iter_lines.return_value = lines
    mock_session.post.return_value = mock_response

    from ollamachat.core.ollama_client import OllamaClient

    client = OllamaClient(session=mock_session)
    on_token = Mock()
    on_done = Mock()
    on_error = Mock()

    client.chat_stream("model", [], {}, on_token, on_done, on_error)
    time.sleep(0.1)

    # Verify CallAfter was used for each callback
    assert any(c[0] is on_token and c[1][0] == "A" for c in mock_call_after)
    assert any(c[0] is on_token and c[1][0] == "B" for c in mock_call_after)
    assert any(c[0] is on_done for c in mock_call_after)

    # Verify on_token was NOT called directly by the thread (it was called
    # via CallAfter which we invoke immediately in the fixture for assertions)
    assert on_token.call_count == 2
    assert on_done.call_count == 1
    assert on_error.call_count == 0
