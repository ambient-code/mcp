"""Tests for Langfuse tracing module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from mcp_acp.tracing import (
    _NoOpContext,
    _SpanContext,
    _TraceContext,
    flush,
    get_langfuse,
    shutdown,
    trace_http_request,
    trace_tool_call,
)


@pytest.fixture(autouse=True)
def _reset_tracing_state():
    """Reset the tracing module singleton state between tests."""
    import mcp_acp.tracing as tracing_mod

    tracing_mod._langfuse_client = None
    tracing_mod._langfuse_init_attempted = False
    yield
    tracing_mod._langfuse_client = None
    tracing_mod._langfuse_init_attempted = False


class TestIsTracingEnabled:
    """Tests for the kill switch env var."""

    def test_enabled_by_default(self) -> None:
        """Tracing is enabled when env var is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MCP_ACP_TRACING_ENABLED", None)
            from mcp_acp.tracing import _is_tracing_enabled

            assert _is_tracing_enabled() is True

    def test_disabled_when_false(self) -> None:
        """Tracing is disabled when env var is 'false'."""
        with patch.dict(os.environ, {"MCP_ACP_TRACING_ENABLED": "false"}):
            from mcp_acp.tracing import _is_tracing_enabled

            assert _is_tracing_enabled() is False

    def test_disabled_when_no(self) -> None:
        """Tracing is disabled when env var is 'no'."""
        with patch.dict(os.environ, {"MCP_ACP_TRACING_ENABLED": "no"}):
            from mcp_acp.tracing import _is_tracing_enabled

            assert _is_tracing_enabled() is False

    def test_enabled_when_true(self) -> None:
        """Tracing is enabled when env var is 'true'."""
        with patch.dict(os.environ, {"MCP_ACP_TRACING_ENABLED": "true"}):
            from mcp_acp.tracing import _is_tracing_enabled

            assert _is_tracing_enabled() is True


class TestGetLangfuse:
    """Tests for get_langfuse singleton."""

    def test_returns_none_when_disabled(self) -> None:
        """Returns None when tracing is disabled via env var."""
        with patch.dict(os.environ, {"MCP_ACP_TRACING_ENABLED": "false"}):
            assert get_langfuse() is None

    def test_returns_none_when_keys_missing(self) -> None:
        """Returns None when Langfuse credentials are not set."""
        env = {"MCP_ACP_TRACING_ENABLED": "true"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)
            assert get_langfuse() is None

    def test_returns_client_when_configured(self) -> None:
        """Returns a Langfuse client when credentials are set."""
        mock_langfuse = MagicMock()
        env = {
            "MCP_ACP_TRACING_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
            "LANGFUSE_BASE_URL": "https://langfuse.test",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("mcp_acp.tracing.Langfuse", return_value=mock_langfuse, create=True) as mock_cls,
        ):
            # Patch the import inside get_langfuse
            with patch.dict("sys.modules", {"langfuse": MagicMock(Langfuse=mock_cls)}):
                result = get_langfuse()
                assert result is mock_langfuse

    def test_returns_none_on_init_error(self) -> None:
        """Returns None when Langfuse SDK raises during init."""
        env = {
            "MCP_ACP_TRACING_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("mcp_acp.tracing.Langfuse", side_effect=RuntimeError("init failed"), create=True):
                import mcp_acp.tracing as mod

                # Directly patch the import path used inside get_langfuse
                original = mod.get_langfuse

                def patched_get():
                    mod._langfuse_init_attempted = False
                    mod._langfuse_client = None
                    return original()

                result = patched_get()
                # Should return None, not raise
                assert result is None

    def test_caches_result(self) -> None:
        """Only attempts initialization once."""
        with patch.dict(os.environ, {"MCP_ACP_TRACING_ENABLED": "false"}):
            result1 = get_langfuse()
            result2 = get_langfuse()
            assert result1 is None
            assert result2 is None


class TestTraceToolCall:
    """Tests for trace_tool_call context manager."""

    @pytest.mark.asyncio
    async def test_yields_noop_when_disabled(self) -> None:
        """Yields a no-op context when Langfuse is not available."""
        with patch("mcp_acp.tracing.get_langfuse", return_value=None):
            async with trace_tool_call("test_tool", {"key": "value"}) as ctx:
                assert isinstance(ctx, _NoOpContext)
                # Should not raise
                ctx.set_output({"status": "success"})
                ctx.set_response(200)

    @pytest.mark.asyncio
    async def test_creates_span_when_enabled(self) -> None:
        """Creates a Langfuse span with tool name and args."""
        mock_span = MagicMock()
        mock_span.id = "span-123"
        mock_lf = MagicMock()
        mock_lf.start_span.return_value = mock_span

        with patch("mcp_acp.tracing.get_langfuse", return_value=mock_lf):
            async with trace_tool_call("test_tool", {"arg": "val"}, {"project": "test"}) as ctx:
                assert isinstance(ctx, _TraceContext)

            # Verify span was created
            mock_lf.start_span.assert_called_once()
            call_kwargs = mock_lf.start_span.call_args
            assert call_kwargs.kwargs["name"] == "test_tool"
            assert call_kwargs.kwargs["input"]["tool"] == "test_tool"
            assert call_kwargs.kwargs["input"]["arguments"] == {"arg": "val"}

    @pytest.mark.asyncio
    async def test_records_explicit_output(self) -> None:
        """Records output when set_output is called explicitly."""
        mock_span = MagicMock()
        mock_span.id = "span-123"
        mock_lf = MagicMock()
        mock_lf.start_span.return_value = mock_span

        with patch("mcp_acp.tracing.get_langfuse", return_value=mock_lf):
            async with trace_tool_call("test_tool", {}) as ctx:
                ctx.set_output({"status": "validation_error", "error": "bad input"})

            # The explicit set_output should have called span.update and span.end
            update_calls = [c for c in mock_span.update.call_args_list if "level" in (c.kwargs or {})]
            assert len(update_calls) >= 1
            last_call = update_calls[-1]
            assert last_call.kwargs["level"] == "ERROR"
            mock_span.end.assert_called()

    @pytest.mark.asyncio
    async def test_records_success_when_no_explicit_output(self) -> None:
        """Auto-records success when context exits without set_output."""
        mock_span = MagicMock()
        mock_span.id = "span-123"
        mock_lf = MagicMock()
        mock_lf.start_span.return_value = mock_span

        with patch("mcp_acp.tracing.get_langfuse", return_value=mock_lf):
            async with trace_tool_call("test_tool", {}):
                pass  # No explicit set_output

            # Should auto-record success
            mock_span.update.assert_called_once()
            call_kwargs = mock_span.update.call_args
            assert call_kwargs.kwargs["output"]["status"] == "success"
            assert call_kwargs.kwargs["level"] == "DEFAULT"
            mock_span.end.assert_called_once()


class TestTraceHttpRequest:
    """Tests for trace_http_request context manager."""

    @pytest.mark.asyncio
    async def test_yields_noop_when_no_parent_span(self) -> None:
        """Yields a no-op context when there is no parent span in contextvars."""
        async with trace_http_request("GET", "/v1/sessions") as ctx:
            assert isinstance(ctx, _NoOpContext)
            ctx.set_response(200)

    @pytest.mark.asyncio
    async def test_creates_child_span_with_parent(self) -> None:
        """Creates a child span when a parent span exists in contextvars."""
        mock_child_span = MagicMock()
        mock_child_span.id = "child-456"
        mock_parent_span = MagicMock()
        mock_parent_span.id = "parent-123"
        mock_parent_span.start_span.return_value = mock_child_span
        mock_lf = MagicMock()
        mock_lf.start_span.return_value = mock_parent_span

        with patch("mcp_acp.tracing.get_langfuse", return_value=mock_lf):
            async with trace_tool_call("test_tool", {}) as _trace_ctx:
                async with trace_http_request("GET", "/v1/sessions", {"limit": "10"}) as span_ctx:
                    assert isinstance(span_ctx, _SpanContext)
                    span_ctx.set_response(200)

            # Verify child span was created on parent
            mock_parent_span.start_span.assert_called_once()
            span_kwargs = mock_parent_span.start_span.call_args.kwargs
            assert span_kwargs["name"] == "GET /v1/sessions"

    @pytest.mark.asyncio
    async def test_records_status_code(self) -> None:
        """Records HTTP status code on the span."""
        mock_child_span = MagicMock()
        mock_child_span.id = "child-456"
        mock_parent_span = MagicMock()
        mock_parent_span.id = "parent-123"
        mock_parent_span.start_span.return_value = mock_child_span
        mock_lf = MagicMock()
        mock_lf.start_span.return_value = mock_parent_span

        with patch("mcp_acp.tracing.get_langfuse", return_value=mock_lf):
            async with trace_tool_call("test_tool", {}):
                async with trace_http_request("GET", "/v1/sessions") as span_ctx:
                    span_ctx.set_response(404)

            # Verify span.update was called with WARNING level for 404
            mock_child_span.update.assert_called_once()
            update_kwargs = mock_child_span.update.call_args.kwargs
            assert update_kwargs["output"]["status_code"] == 404
            assert update_kwargs["level"] == "WARNING"
            mock_child_span.end.assert_called()

    @pytest.mark.asyncio
    async def test_records_server_error_level(self) -> None:
        """Records ERROR level for 5xx status codes."""
        mock_child_span = MagicMock()
        mock_child_span.id = "child-456"
        mock_parent_span = MagicMock()
        mock_parent_span.id = "parent-123"
        mock_parent_span.start_span.return_value = mock_child_span
        mock_lf = MagicMock()
        mock_lf.start_span.return_value = mock_parent_span

        with patch("mcp_acp.tracing.get_langfuse", return_value=mock_lf):
            async with trace_tool_call("test_tool", {}):
                async with trace_http_request("POST", "/v1/sessions") as span_ctx:
                    span_ctx.set_response(500)

            update_kwargs = mock_child_span.update.call_args.kwargs
            assert update_kwargs["level"] == "ERROR"


class TestNoOpContext:
    """Tests for _NoOpContext."""

    def test_set_output_is_noop(self) -> None:
        """set_output does nothing."""
        ctx = _NoOpContext()
        ctx.set_output({"status": "success"})

    def test_set_response_is_noop(self) -> None:
        """set_response does nothing."""
        ctx = _NoOpContext()
        ctx.set_response(200)


class TestFlushAndShutdown:
    """Tests for flush and shutdown lifecycle functions."""

    def test_flush_calls_client_flush(self) -> None:
        """flush() calls the Langfuse client's flush method."""
        import mcp_acp.tracing as mod

        mock_client = MagicMock()
        mod._langfuse_client = mock_client

        flush()
        mock_client.flush.assert_called_once()

    def test_flush_noop_when_no_client(self) -> None:
        """flush() is a no-op when no client exists."""
        flush()  # Should not raise

    def test_flush_handles_error(self) -> None:
        """flush() catches exceptions from the client."""
        import mcp_acp.tracing as mod

        mock_client = MagicMock()
        mock_client.flush.side_effect = RuntimeError("flush failed")
        mod._langfuse_client = mock_client

        flush()  # Should not raise

    def test_shutdown_calls_client_shutdown(self) -> None:
        """shutdown() calls the Langfuse client's shutdown method."""
        import mcp_acp.tracing as mod

        mock_client = MagicMock()
        mod._langfuse_client = mock_client

        shutdown()
        mock_client.shutdown.assert_called_once()
        assert mod._langfuse_client is None
        assert mod._langfuse_init_attempted is False

    def test_shutdown_noop_when_no_client(self) -> None:
        """shutdown() is a no-op when no client exists."""
        shutdown()  # Should not raise

    def test_shutdown_handles_error(self) -> None:
        """shutdown() catches exceptions and still resets state."""
        import mcp_acp.tracing as mod

        mock_client = MagicMock()
        mock_client.shutdown.side_effect = RuntimeError("shutdown failed")
        mod._langfuse_client = mock_client

        shutdown()  # Should not raise
        assert mod._langfuse_client is None
        assert mod._langfuse_init_attempted is False
