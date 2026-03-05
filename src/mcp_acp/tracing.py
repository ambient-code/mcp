"""Langfuse tracing integration for mcp-acp.

Provides async context managers for tracing MCP tool calls and HTTP requests.
When Langfuse credentials are not configured or tracing is disabled via the
MCP_ACP_TRACING_ENABLED env var, all operations silently no-op.

Uses Langfuse SDK v3 API (start_span / start_as_current_span).
"""

import os
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

from utils.pylogger import get_python_logger

logger = get_python_logger()

# Contextvar holds the parent span so child spans can nest under it
_current_span: ContextVar[Any] = ContextVar("_current_span", default=None)

_langfuse_client = None
_langfuse_init_attempted = False


def _is_tracing_enabled() -> bool:
    """Check if tracing is enabled via env var (default: true)."""
    return os.getenv("MCP_ACP_TRACING_ENABLED", "true").lower() in ("true", "1", "yes")


def get_langfuse():
    """Get or create a Langfuse client singleton.

    Returns None if tracing is disabled or credentials are not configured.
    """
    global _langfuse_client, _langfuse_init_attempted

    if _langfuse_init_attempted:
        return _langfuse_client

    _langfuse_init_attempted = True

    if not _is_tracing_enabled():
        logger.info("tracing_disabled", reason="MCP_ACP_TRACING_ENABLED is not set to true")
        return None

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        logger.info("tracing_disabled", reason="LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set")
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse()
        logger.info("tracing_initialized", host=os.getenv("LANGFUSE_BASE_URL", "default"))
        return _langfuse_client
    except Exception as e:
        logger.warning("tracing_init_failed", error=str(e))
        return None


class _NoOpContext:
    """No-op context returned when tracing is disabled."""

    def set_output(self, output: dict[str, Any]) -> None:
        pass

    def set_response(self, status_code: int) -> None:
        pass


@asynccontextmanager
async def trace_tool_call(tool_name: str, safe_args: dict[str, Any], metadata: dict[str, Any] | None = None):
    """Trace an MCP tool call as a Langfuse span.

    Creates a top-level Langfuse span for the tool invocation and stores it
    in a contextvar so child HTTP spans can nest under it.

    Yields a context object with set_output() for recording results.
    """
    lf = get_langfuse()
    if lf is None:
        yield _NoOpContext()
        return

    trace_input = {"tool": tool_name, "arguments": safe_args}
    if metadata:
        trace_input["metadata"] = metadata

    start = time.time()
    span = None
    token = None

    try:
        span = lf.start_span(name=tool_name, input=trace_input, metadata=metadata or {})
        token = _current_span.set(span)

        ctx = _TraceContext(span, start)
        yield ctx
    except Exception:
        if span:
            elapsed = time.time() - start
            span.update(
                output={"status": "error", "duration_ms": round(elapsed * 1000)},
                level="ERROR",
            )
            span.end()
        raise
    else:
        if span and not ctx._output_set:
            elapsed = time.time() - start
            span.update(
                output={"status": "success", "duration_ms": round(elapsed * 1000)},
                level="DEFAULT",
            )
            span.end()
    finally:
        if token is not None:
            _current_span.reset(token)


class _TraceContext:
    """Context object for an active Langfuse trace span."""

    def __init__(self, span, start_time: float):
        self._span = span
        self._start_time = start_time
        self._output_set = False

    def set_output(self, output: dict[str, Any]) -> None:
        """Record output and status on the span."""
        self._output_set = True
        elapsed = time.time() - self._start_time
        output["duration_ms"] = round(elapsed * 1000)

        status = output.get("status", "")
        if "error" in status:
            level = "ERROR"
        elif "warning" in status:
            level = "WARNING"
        else:
            level = "DEFAULT"

        self._span.update(output=output, level=level)
        self._span.end()

    def set_response(self, status_code: int) -> None:
        pass


@asynccontextmanager
async def trace_http_request(method: str, path: str, params: dict[str, Any] | None = None):
    """Trace an HTTP request as a child span nested under the current tool span.

    Reads the contextvar to find the parent span and creates a child.
    Yields a context object with set_response() for recording the HTTP status code.
    """
    parent_span = _current_span.get()

    if parent_span is None:
        yield _NoOpContext()
        return

    span_input = {"method": method, "path": path}
    if params:
        span_input["params"] = params

    start = time.time()
    span = None
    token = None

    try:
        span = parent_span.start_span(name=f"{method} {path}", input=span_input)
        token = _current_span.set(span)

        ctx = _SpanContext(span, start)
        yield ctx
    except Exception:
        if span and not ctx._ended:
            elapsed = time.time() - start
            span.update(
                output={"status": "error", "duration_ms": round(elapsed * 1000)},
                level="ERROR",
            )
            span.end()
            ctx._ended = True
        raise
    else:
        if span and not ctx._ended:
            elapsed = time.time() - start
            span.update(
                output={"status": "success", "duration_ms": round(elapsed * 1000)},
                level="DEFAULT",
            )
            span.end()
            ctx._ended = True
    finally:
        if token is not None:
            _current_span.reset(token)


class _SpanContext:
    """Context object for an active Langfuse child span."""

    def __init__(self, span, start_time: float):
        self._span = span
        self._start_time = start_time
        self._ended = False

    @property
    def _response_set(self) -> bool:
        return self._ended

    def set_output(self, output: dict[str, Any]) -> None:
        pass

    def set_response(self, status_code: int) -> None:
        """Record HTTP status code on the span."""
        if self._ended:
            return
        self._ended = True
        elapsed = time.time() - self._start_time

        if status_code >= 500:
            level = "ERROR"
        elif status_code >= 400:
            level = "WARNING"
        else:
            level = "DEFAULT"

        self._span.update(
            output={"status_code": status_code, "duration_ms": round(elapsed * 1000)},
            level=level,
        )
        self._span.end()


def flush() -> None:
    """Flush pending traces to Langfuse."""
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
        except Exception as e:
            logger.warning("tracing_flush_failed", error=str(e))


def shutdown() -> None:
    """Shut down the Langfuse client, flushing any pending data."""
    global _langfuse_client, _langfuse_init_attempted
    if _langfuse_client is not None:
        try:
            _langfuse_client.shutdown()
        except Exception as e:
            logger.warning("tracing_shutdown_failed", error=str(e))
        finally:
            _langfuse_client = None
            _langfuse_init_attempted = False
