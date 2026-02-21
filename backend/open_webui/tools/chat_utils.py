"""Pure utility functions for chat tool operations.

Extracted to allow testing without importing the full OpenWebUI app.
"""

MAX_LIMIT = 50
MAX_CONTENT_LENGTH = 4000


def paginate_messages(
    all_messages: list[dict],
    offset: int = 0,
    limit: int = 20,
) -> dict:
    """Paginate a list of messages from the end (most recent first by default).

    Args:
        all_messages: Messages in chronological order [oldest, ..., newest].
        offset: Number of messages to skip from the end (0 = most recent).
        limit: Maximum number of messages to return.

    Returns:
        Dict with paginated messages and metadata.
    """
    total = len(all_messages)

    # Clamp parameters
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, min(offset, total))

    # Paginate from the end (most recent first by default)
    # offset=0 means the last `limit` messages
    end_idx = total - offset
    start_idx = max(0, end_idx - limit)
    page_messages = all_messages[start_idx:end_idx]

    return {
        "messages": page_messages,
        "total_messages": total,
        "showing": f"{start_idx + 1}-{end_idx} of {total}",
    }


def truncate_message_content(messages: list[dict]) -> list[dict]:
    """Truncate long message content in-place.

    Args:
        messages: List of message dicts with "content" keys.

    Returns:
        The same list (mutated in-place) for convenience.
    """
    for msg in messages:
        content = msg.get("content", "")
        if len(content) > MAX_CONTENT_LENGTH:
            msg["content"] = content[:MAX_CONTENT_LENGTH] + " [truncated]"
    return messages
