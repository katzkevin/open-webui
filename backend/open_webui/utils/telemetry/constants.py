from opentelemetry.semconv.trace import SpanAttributes as _SpanAttributes

# Span Tags
SPAN_DB_TYPE = "mysql"
SPAN_REDIS_TYPE = "redis"
SPAN_DURATION = "duration"
SPAN_SQL_STR = "sql"
SPAN_SQL_EXPLAIN = "explain"
SPAN_ERROR_TYPE = "error"


class SpanAttributes(_SpanAttributes):
    """
    Span Attributes
    """

    DB_INSTANCE = "db.instance"
    DB_TYPE = "db.type"
    DB_IP = "db.ip"
    DB_PORT = "db.port"
    ERROR_KIND = "error.kind"
    ERROR_OBJECT = "error.object"
    ERROR_MESSAGE = "error.message"
    RESULT_CODE = "result.code"
    RESULT_MESSAGE = "result.message"
    RESULT_ERRORS = "result.errors"


class ChatSpanAttributes:
    """Chat completion specific span attributes."""

    # Identifiers
    CHAT_ID = "chat.id"
    MESSAGE_ID = "chat.message_id"
    SESSION_ID = "chat.session_id"
    USER_ID = "chat.user_id"
    MODEL_ID = "chat.model_id"
    MODEL_BACKEND = "chat.model_backend"  # "ollama", "openai", "function", "direct"

    # Streaming metrics
    IS_STREAMING = "chat.is_streaming"
    TIME_TO_FIRST_TOKEN_MS = "chat.ttft_ms"
    TOTAL_STREAMING_DURATION_MS = "chat.streaming_duration_ms"
    CHUNK_COUNT = "chat.chunk_count"

    # Feature flags
    HAS_TOOLS = "chat.has_tools"
    HAS_RAG = "chat.has_rag"
    HAS_WEB_SEARCH = "chat.has_web_search"
    HAS_MEMORY = "chat.has_memory"

    # Tool execution
    TOOL_NAME = "chat.tool.name"
    TOOL_TYPE = "chat.tool.type"  # "mcp", "openapi", "builtin"

    # Filter info
    FILTER_ID = "chat.filter.id"
    FILTER_TYPE = "chat.filter.type"  # "inlet", "outlet"

    # Error tracking
    ERROR_TYPE = "chat.error.type"
    ERROR_MESSAGE = "chat.error.message"
