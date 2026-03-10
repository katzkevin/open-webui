"""
Chat completion tracing utilities for OpenTelemetry integration.

Provides context managers, decorators, and helpers for instrumenting
the chat completion flow with minimal code changes.
"""

import time
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
from typing import Any, Callable, Optional, Dict

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode, SpanKind

from open_webui.env import ENABLE_OTEL_TRACES

# Module-level tracer - lazy initialization
_tracer: Optional[trace.Tracer] = None


def get_tracer() -> trace.Tracer:
    """Get or create the chat tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("open_webui.chat")
    return _tracer


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled."""
    return ENABLE_OTEL_TRACES


@asynccontextmanager
async def trace_chat_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: SpanKind = SpanKind.INTERNAL,
):
    """
    Async context manager for creating a traced span.

    Usage:
        async with trace_chat_span("chat.validation", {"chat.model_id": model_id}):
            # do work
    """
    if not is_tracing_enabled():
        yield None
        return

    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("chat.error.type", type(e).__name__)
            span.set_attribute("chat.error.message", str(e)[:500])
            raise


@contextmanager
def trace_chat_span_sync(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: SpanKind = SpanKind.INTERNAL,
):
    """Synchronous version of trace_chat_span."""
    if not is_tracing_enabled():
        yield None
        return

    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("chat.error.type", type(e).__name__)
            span.set_attribute("chat.error.message", str(e)[:500])
            raise


def trace_async(
    span_name: str,
    extract_attributes: Optional[Callable[..., Dict[str, Any]]] = None,
):
    """
    Decorator for async functions that creates a traced span.

    Usage:
        @trace_async("chat.filter.inlet", lambda form_data: {"chat.model_id": form_data.get("model")})
        async def process_inlet(form_data):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not is_tracing_enabled():
                return await func(*args, **kwargs)

            attributes = {}
            if extract_attributes:
                try:
                    attributes = extract_attributes(*args, **kwargs)
                except Exception:
                    pass

            async with trace_chat_span(span_name, attributes):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


class StreamingTTFTTracker:
    """
    Tracks time-to-first-token and streaming duration for chat completions.

    Usage:
        tracker = StreamingTTFTTracker()
        async for chunk in response.body_iterator:
            tracker.on_chunk(chunk)
            yield chunk
        tracker.finalize(span)
    """

    def __init__(self):
        self.start_time = time.perf_counter()
        self.first_token_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.chunk_count = 0

    def on_chunk(self, chunk: Any) -> None:
        """Called for each streaming chunk."""
        self.chunk_count += 1
        if self.first_token_time is None and self._has_content(chunk):
            self.first_token_time = time.perf_counter()

    def _has_content(self, chunk: Any) -> bool:
        """Check if chunk contains actual content (not just metadata)."""
        if isinstance(chunk, bytes):
            data = chunk.decode("utf-8", "replace")
        else:
            data = str(chunk)
        # Check for content in the delta - these indicate actual token output
        return '"content"' in data or '"delta"' in data

    def finalize(self, span: Optional[Span] = None) -> Dict[str, float]:
        """Finalize tracking and optionally set span attributes."""
        self.end_time = time.perf_counter()

        metrics = {}
        if self.first_token_time is not None:
            ttft_ms = (self.first_token_time - self.start_time) * 1000
            metrics["ttft_ms"] = ttft_ms

        total_duration_ms = (self.end_time - self.start_time) * 1000
        metrics["streaming_duration_ms"] = total_duration_ms
        metrics["chunk_count"] = self.chunk_count

        if span and is_tracing_enabled():
            if "ttft_ms" in metrics:
                span.set_attribute("chat.ttft_ms", metrics["ttft_ms"])
            span.set_attribute(
                "chat.streaming_duration_ms", metrics["streaming_duration_ms"]
            )
            span.set_attribute("chat.chunk_count", metrics["chunk_count"])

        return metrics


def get_current_span() -> Optional[Span]:
    """Get the current active span, if any."""
    if not is_tracing_enabled():
        return None
    return trace.get_current_span()


def add_chat_metadata_to_span(
    span: Optional[Span],
    metadata: Dict[str, Any],
    model_id: Optional[str] = None,
) -> None:
    """Add common chat metadata attributes to a span."""
    if not span or not is_tracing_enabled():
        return

    if metadata.get("chat_id"):
        span.set_attribute("chat.id", metadata["chat_id"])
    if metadata.get("message_id"):
        span.set_attribute("chat.message_id", metadata["message_id"])
    if metadata.get("session_id"):
        span.set_attribute("chat.session_id", metadata["session_id"])
    if metadata.get("user_id"):
        span.set_attribute("chat.user_id", metadata["user_id"])
    if model_id:
        span.set_attribute("chat.model_id", model_id)


def set_span_error(span: Optional[Span], error: Exception) -> None:
    """Set error status and attributes on a span."""
    if not span or not is_tracing_enabled():
        return

    span.set_status(Status(StatusCode.ERROR, str(error)))
    span.set_attribute("chat.error.type", type(error).__name__)
    span.set_attribute("chat.error.message", str(error)[:500])
