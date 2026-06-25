"""Conversation persistence for Bellbird.

Defines the Conversation class that holds the in-memory transcript of a
chat session and serializes it to/from UTF-8 JSON files.

Usage:
    conv = Conversation()
    conv.add_message("user", "Hello")
    Conversation.save(conv, Path("chat.json"))
    loaded = Conversation.load(Path("chat.json"))
"""

import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Conversation:
    """In-memory conversation transcript with JSON persistence.

    Maintains a list of message dicts, each with role, content, timestamp,
    and optionally images.

    Attributes:
        messages: List of message dicts.
    """

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def add_message(
        self,
        role: str,
        content: str,
        images: list[str] | None = None,
        tool_call_id: str | None = None,
        reasoning: str = "",
        tool_calls: list[dict] | None = None,
    ) -> None:
        """Append a message to the conversation.

        Args:
            role: Message role ("user", "assistant", "system", "tool").
            content: Message text content.
            images: Optional list of base64-encoded image strings (user role only).
            tool_call_id: Required for role="tool" — the ID returned by the
                model in its assistant tool_calls[].id field. The OpenAI-
                compatible API requires tool messages to carry the matching
                tool_call_id so the model can correlate the result with the
                call. Ignored for non-tool roles.
            reasoning: Optional reasoning/chain-of-thought text. Persisted
                locally but stripped from API payloads. Defaults to ``""``
                for backward compatibility with existing code that does not
                pass this parameter.
            tool_calls: Optional list of tool call dicts for role="assistant".
                Each dict has ``id``, ``type``, and ``function`` keys.
                Ignored for non-assistant roles.
        """
        msg: dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if images:
            msg["images"] = images
        if tool_call_id is not None and role == "tool":
            msg["tool_call_id"] = tool_call_id
        if reasoning:
            msg["reasoning"] = reasoning
        if tool_calls is not None and role == "assistant":
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def get_messages_for_api(self) -> list[dict[str, Any]]:
        """Return messages in the format required by the Ollama API.

        Strips the timestamp key and preserves images, tool_call_id,
        and tool_calls if present. For role="tool" messages, the
        tool_call_id MUST be present so the model can correlate the
        result with the assistant's tool_calls[].id (OpenAI-compatible
        API requirement).

        The ``reasoning`` key is LOCAL-ONLY — it MUST NOT appear in the
        API payload. This is a pinned invariant.

        Returns:
            List of message dicts with role, content, and optional
            images, tool_call_id, and tool_calls.
        """
        result: list[dict[str, Any]] = []
        for msg in self.messages:
            api_msg: dict[str, Any] = {
                "role": msg["role"],
                "content": msg["content"],
            }
            if "images" in msg:
                api_msg["images"] = msg["images"]
            if "tool_call_id" in msg:
                api_msg["tool_call_id"] = msg["tool_call_id"]
            if "tool_calls" in msg:
                api_msg["tool_calls"] = msg["tool_calls"]
            # timestamp is stripped (API rejects unknown fields)
            # reasoning is local-only (MUST NOT appear in API payload)
            result.append(api_msg)
        return result

    def clear(self) -> None:
        """Remove all messages from the conversation."""
        self.messages.clear()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the conversation to a plain dict.

        Returns:
            Dict with a "messages" key containing all messages.
        """
        return {"messages": self.messages}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conversation":
        """Create a Conversation from a dict.

        Args:
            data: Dict with a "messages" key.

        Returns:
            New Conversation populated with the given messages.
        """
        conv = cls()
        conv.messages = data.get("messages", [])
        return conv

    def truncate_to(self, index: int) -> None:
        """Keep messages up to and including ``index``, drop everything after.

        The message at ``index`` is kept; only messages strictly AFTER it
        are removed. System-role rows at the head (before ``index``) are
        preserved — they are never removed by this operation.

        Args:
            index: Zero-based index; all messages ``[index+1:]`` are removed.
                A value of ``-1`` or less clears all messages.
        """
        self.messages = self.messages[: index + 1]

    def pop_last(self, role: str | None = None) -> None:
        """Drop the trailing row, optionally filtered by ``role``.

        If the trailing pair is ``assistant(tool_calls=...)`` followed by
        ``tool``, BOTH are removed together (the pair drops atomically so
        the API payload never contains an orphaned ``tool`` row).

        Args:
            role: If set, only the trailing row with this role is removed.
                If the trailing row does not match ``role``, nothing is removed.
        """
        if not self.messages:
            return
        if role is not None and self.messages[-1].get("role") != role:
            return

        # Check for the assistant(tool_calls) + tool pair at the end
        if (
            len(self.messages) >= 2
            and self.messages[-2].get("role") == "assistant"
            and "tool_calls" in self.messages[-2]
            and self.messages[-1].get("role") == "tool"
        ):
            # Pop the tool row first, then the assistant row (pair)
            self.messages.pop()
            self.messages.pop()
            return

        # Standard pop: remove the trailing message
        self.messages.pop()

    def to_markdown(self, system_prompt: str = "") -> str:
        """Serialize the conversation to a human-readable Markdown string.

        Args:
            system_prompt: Optional system prompt text to include as
                ``## Mensaje del sistema``. Omitted when empty.

        Returns:
            UTF-8 Markdown string with the full transcript.
        """
        role_labels: dict[str, str] = {
            "user": "Usuario",
            "assistant": "Asistente",
            "tool": "Herramienta",
        }

        lines: list[str] = ["# Conversación", ""]

        if system_prompt:
            lines.append("## Mensaje del sistema")
            lines.append("")
            lines.append(system_prompt)
            lines.append("")

        for msg in self.messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            label = role_labels.get(role, role)

            lines.append(f"## {label}")
            lines.append("")

            if content:
                lines.append(content)

            # Emit tool_calls as a fenced JSON block under the assistant heading
            if role == "assistant" and msg.get("tool_calls"):
                if content:
                    lines.append("")
                lines.append("```json")
                lines.append(json.dumps(msg["tool_calls"], indent=2, ensure_ascii=False))
                lines.append("```")

            lines.append("")

        return "\n".join(lines)

    @classmethod
    def save(
        cls, conv: "Conversation", filepath: Path, system_prompt: str = ""
    ) -> None:
        """Save a conversation to disk with atomic write.

        Writes to a .tmp file first, then replaces the target atomically.
        The system_prompt is stored at the top level alongside messages.

        Args:
            conv: The conversation to save.
            filepath: Path to the output JSON file.
            system_prompt: Optional system prompt text to persist.
        """
        data = conv.to_dict()
        full = {"system_prompt": system_prompt, **data}
        filepath = Path(filepath)  # wx.FileDialog.GetPath() returns str, not Path
        tmp_path = filepath.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(full, f, indent=2, ensure_ascii=False)
        tmp_path.replace(filepath)

    @classmethod
    def load(cls, filepath: Path) -> tuple["Conversation", str]:
        """Load a conversation from disk.

        Args:
            filepath: Path to an existing JSON file.

        Returns:
            Tuple of (Conversation, system_prompt_string).

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        sp: str = data.get("system_prompt", "")
        body = {"messages": data.get("messages", [])}
        return cls.from_dict(body), sp


# ─── Module-level helpers ────────────────────────────────────────────────────


def _normalize(text: str) -> str:
    """Casefold and strip diacritics for accent-insensitive comparison.

    Applies NFKD normalization, removes combining marks (diacritics),
    then casefolds the result. Pure, wx-free.
    """
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def find_in_history(
    items: list[tuple[str, str]],
    query: str,
    start_index: int,
    wrap: bool = True,
) -> int:
    """Find the next match in a history list, case+accent-insensitive, with wrap.

    Args:
        items: List of ``(role, text)`` tuples (e.g. ``ChatPanel._history``).
        query: Search text. Empty query always returns ``-1``.
        start_index: 1-based position to search **strictly after**.
            Pass ``0`` to start from the first element.
        wrap: If ``True``, wraps from end to start when no match found
            after ``start_index``.

    Returns:
        1-based index of the next match, or ``-1`` if no match found.
    """
    if not query or not items:
        return -1

    query_norm = _normalize(query)
    n = len(items)

    # Search strictly after start_index (1-based) to end
    for i in range(start_index + 1, n + 1):
        _, text = items[i - 1]
        if query_norm in _normalize(text):
            return i

    # Wrap from beginning to start_index (inclusive)
    if wrap:
        for i in range(1, start_index + 1):
            _, text = items[i - 1]
            if query_norm in _normalize(text):
                return i

    return -1
