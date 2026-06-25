"""Tests for LlamaClient.check_state() — ternary server health.

Strict TDD: tests written BEFORE the code they exercise.
"""

from unittest.mock import Mock

import pytest
import requests


@pytest.fixture
def mock_session():
    """Inject a fake requests.Session."""
    return Mock(spec=requests.Session)


class TestCheckState:
    """check_state() ternary: loading / dead / ready."""

    def test_200_with_status_ok_returns_ready(self, mock_session):
        """Given 200 + {'status': 'ok'}, returns 'ready'."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_session.get.return_value = mock_response

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_state() == "ready"

    def test_503_with_loading_message_returns_loading(self, mock_session):
        """Given 503 + {'error': {'message': 'Loading model...'}}, returns 'loading'."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {
            "error": {"message": "Loading model (755.44/755.44 MB)"}
        }
        mock_session.get.return_value = mock_response

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_state() == "loading"

    def test_503_with_empty_body_returns_dead(self, mock_session):
        """Given 503 with no parseable error.message, returns 'dead'."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.json.return_value = {}
        mock_session.get.return_value = mock_response

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_state() == "dead"

    def test_502_returns_dead(self, mock_session):
        """Given 502 (other 5xx), returns 'dead'."""
        mock_response = Mock()
        mock_response.status_code = 502
        mock_response.json.return_value = {}
        mock_session.get.return_value = mock_response

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_state() == "dead"

    def test_connection_error_returns_dead(self, mock_session):
        """Given ConnectionError, returns 'dead'."""
        mock_session.get.side_effect = requests.ConnectionError("refused")

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_state() == "dead"

    def test_timeout_returns_dead(self, mock_session):
        """Given requests.Timeout, returns 'dead'."""
        mock_session.get.side_effect = requests.exceptions.Timeout("timed out")

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_state() == "dead"

    def test_never_raises(self, mock_session):
        """check_state must never raise regardless of response."""
        mock_session.get.side_effect = RuntimeError("unexpected")

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        # Should not raise
        assert client.check_state() == "dead"


class TestCheckRunningRegression:
    """Regression guard: check_running() stays byte-identical."""

    def test_check_running_returns_true_on_200_ok(self, mock_session):
        """Given 200 OK with status ok, check_running returns True (unchanged)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_session.get.return_value = mock_response

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_running() is True

    def test_check_running_returns_false_on_connection_error(self, mock_session):
        """Given ConnectionError, check_running returns False (unchanged)."""
        mock_session.get.side_effect = requests.ConnectionError("refused")

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_running() is False

    def test_check_running_returns_false_on_503(self, mock_session):
        """Given 503, check_running returns False (unchanged)."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_session.get.return_value = mock_response

        from bellbird.core.llama_client import LlamaClient

        client = LlamaClient(session=mock_session)
        assert client.check_running() is False
