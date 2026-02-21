"""Unit and integration tests for view_chat pagination and truncation.

Tests the pure utility functions in chat_utils, which power the view_chat
builtin tool. Extracted to avoid importing the full OpenWebUI app stack.

Production issue: view_chat returned ALL messages with no size limit.
Three calls on long chats pushed the Bedrock prompt to 211K tokens,
exceeding the 200K maximum. Fix: paginate from the end, truncate content.
"""

import json

import pytest

from open_webui.tools.chat_utils import (
    MAX_CONTENT_LENGTH,
    MAX_LIMIT,
    paginate_messages,
    truncate_message_content,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msgs(n: int, content_fn=None) -> list[dict]:
    """Generate n messages in chronological order."""
    if content_fn is None:
        content_fn = lambda i: f"Message {i}"
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": content_fn(i)}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Unit Tests — paginate_messages
# ---------------------------------------------------------------------------


class TestPaginateMessages:
    def test_default_returns_last_20(self):
        msgs = _msgs(30)
        result = paginate_messages(msgs)

        assert result["total_messages"] == 30
        assert len(result["messages"]) == 20
        # Should be messages 10-29 (last 20)
        assert result["messages"][0]["content"] == "Message 10"
        assert result["messages"][-1]["content"] == "Message 29"
        assert result["showing"] == "11-30 of 30"

    def test_offset_pages_backward(self):
        msgs = _msgs(30)
        result = paginate_messages(msgs, offset=20, limit=10)

        assert len(result["messages"]) == 10
        # offset=20 from end, limit=10 → messages 0-9
        assert result["messages"][0]["content"] == "Message 0"
        assert result["messages"][-1]["content"] == "Message 9"
        assert result["showing"] == "1-10 of 30"

    def test_custom_limit(self):
        msgs = _msgs(30)
        result = paginate_messages(msgs, limit=5)

        assert len(result["messages"]) == 5
        # Last 5 messages: 25-29
        assert result["messages"][0]["content"] == "Message 25"
        assert result["messages"][-1]["content"] == "Message 29"

    def test_limit_capped_at_max(self):
        msgs = _msgs(30)
        result = paginate_messages(msgs, limit=100)

        # limit capped to MAX_LIMIT (50), but only 30 msgs exist
        assert len(result["messages"]) == 30

    def test_offset_beyond_total_returns_empty(self):
        msgs = _msgs(30)
        result = paginate_messages(msgs, offset=100, limit=10)

        # offset clamped to total (30), end_idx=0, empty page
        assert len(result["messages"]) == 0
        assert result["total_messages"] == 30

    def test_empty_messages(self):
        result = paginate_messages([])

        assert result["messages"] == []
        assert result["total_messages"] == 0
        assert result["showing"] == "1-0 of 0"

    def test_fewer_messages_than_limit(self):
        msgs = _msgs(5)
        result = paginate_messages(msgs, limit=20)

        assert len(result["messages"]) == 5
        assert result["total_messages"] == 5

    def test_negative_offset_clamped_to_zero(self):
        msgs = _msgs(5)
        result = paginate_messages(msgs, offset=-5)

        # Clamped to 0 → last 5 messages
        assert len(result["messages"]) == 5
        assert result["messages"][0]["content"] == "Message 0"

    def test_negative_limit_clamped_to_one(self):
        msgs = _msgs(5)
        result = paginate_messages(msgs, limit=-1)

        # Clamped to 1 → last 1 message
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Message 4"

    def test_offset_equals_total_returns_empty(self):
        msgs = _msgs(10)
        result = paginate_messages(msgs, offset=10, limit=5)

        assert len(result["messages"]) == 0

    def test_middle_page(self):
        msgs = _msgs(50)
        result = paginate_messages(msgs, offset=10, limit=10)

        # offset=10 from end → end_idx=40, start_idx=30
        assert len(result["messages"]) == 10
        assert result["messages"][0]["content"] == "Message 30"
        assert result["messages"][-1]["content"] == "Message 39"
        assert result["showing"] == "31-40 of 50"


# ---------------------------------------------------------------------------
# Unit Tests — truncate_message_content
# ---------------------------------------------------------------------------


class TestTruncateMessageContent:
    def test_long_content_truncated(self):
        msgs = [{"role": "user", "content": "x" * 10000}]
        truncate_message_content(msgs)

        assert msgs[0]["content"].endswith(" [truncated]")
        assert len(msgs[0]["content"]) == MAX_CONTENT_LENGTH + len(" [truncated]")

    def test_short_content_unchanged(self):
        msgs = [{"role": "user", "content": "Hello world"}]
        truncate_message_content(msgs)

        assert msgs[0]["content"] == "Hello world"

    def test_exactly_at_limit_not_truncated(self):
        content = "x" * MAX_CONTENT_LENGTH
        msgs = [{"role": "user", "content": content}]
        truncate_message_content(msgs)

        assert msgs[0]["content"] == content
        assert "[truncated]" not in msgs[0]["content"]

    def test_one_over_limit_truncated(self):
        content = "x" * (MAX_CONTENT_LENGTH + 1)
        msgs = [{"role": "user", "content": content}]
        truncate_message_content(msgs)

        assert msgs[0]["content"].endswith(" [truncated]")

    def test_empty_content_unchanged(self):
        msgs = [{"role": "user", "content": ""}]
        truncate_message_content(msgs)

        assert msgs[0]["content"] == ""

    def test_multiple_messages_selective_truncation(self):
        msgs = [
            {"role": "user", "content": "short"},
            {"role": "assistant", "content": "y" * 10000},
            {"role": "user", "content": "also short"},
        ]
        truncate_message_content(msgs)

        assert msgs[0]["content"] == "short"
        assert msgs[1]["content"].endswith(" [truncated]")
        assert msgs[2]["content"] == "also short"

    def test_mutates_in_place(self):
        msgs = [{"role": "user", "content": "z" * 10000}]
        returned = truncate_message_content(msgs)

        assert returned is msgs


# ---------------------------------------------------------------------------
# Integration Tests — realistic scenarios
# ---------------------------------------------------------------------------


class TestViewChatIntegration:
    def test_large_chat_stays_within_token_budget(self):
        """Simulate production issue: 150 messages with long content.
        Pagination + truncation should keep the result bounded."""
        msgs = _msgs(
            150,
            content_fn=lambda i: f"Message {i}: " + "lorem ipsum dolor sit amet " * 200,
        )

        result = paginate_messages(msgs)
        truncate_message_content(result["messages"])

        # Only 20 messages returned
        assert len(result["messages"]) == 20
        assert result["total_messages"] == 150

        # Each message truncated
        for msg in result["messages"]:
            assert len(msg["content"]) <= MAX_CONTENT_LENGTH + len(" [truncated]")

        # Total JSON size should be well under 200K chars
        result_str = json.dumps(result)
        assert len(result_str) < 200_000

    def test_paginate_through_entire_chat_no_gaps(self):
        """Verify we can paginate through all messages without gaps or overlaps."""
        msgs = _msgs(47)

        all_retrieved = []
        offset = 0
        page_size = 10

        while True:
            result = paginate_messages(msgs, offset=offset, limit=page_size)
            page = result["messages"]
            if not page:
                break
            all_retrieved = page + all_retrieved  # prepend older pages
            offset += page_size

        # All 47 messages retrieved, in order, no duplicates
        assert len(all_retrieved) == 47
        for i, msg in enumerate(all_retrieved):
            assert msg["content"] == f"Message {i}"

    def test_chat_with_transcript_message(self):
        """Chat containing a pasted meeting transcript (~25K chars)."""
        transcript = "Speaker A: " + "blah " * 5000
        msgs = [
            {"role": "user", "content": "Can you summarize this meeting?"},
            {"role": "user", "content": transcript},
            {"role": "assistant", "content": "Here's a summary of the key points..."},
        ]

        result = paginate_messages(msgs)
        truncate_message_content(result["messages"])

        # Transcript message truncated
        assert result["messages"][1]["content"].endswith(" [truncated]")
        assert len(result["messages"][1]["content"]) <= MAX_CONTENT_LENGTH + len(
            " [truncated]"
        )

        # Other messages intact
        assert result["messages"][0]["content"] == "Can you summarize this meeting?"
        assert (
            result["messages"][2]["content"]
            == "Here's a summary of the key points..."
        )

    def test_three_view_chat_calls_stay_under_200k(self):
        """Simulate the exact prod failure: 3 separate view_chat calls.
        Total combined output must stay well under 200K tokens (~800K chars)."""
        results = []
        for _ in range(3):
            msgs = _msgs(
                100,
                content_fn=lambda i: f"Msg {i}: " + "word " * 1000,
            )
            result = paginate_messages(msgs)
            truncate_message_content(result["messages"])
            results.append(json.dumps(result))

        combined_size = sum(len(r) for r in results)
        # 200K tokens ≈ 800K chars; we should be well under
        assert combined_size < 400_000, f"Combined size {combined_size} too large"
