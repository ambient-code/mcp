# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Project**: MCP Server for Ambient Code Platform (ACP) management
**Repository**: https://github.com/ambient-code/mcp

---

## Self-Review Protocol (Mandatory)

Before presenting ANY work containing code, analysis, or recommendations:

1. **Pause and re-read your work**
2. **Ask yourself:**
   - "What would a senior engineer critique?"
   - "What edge case am I missing?"
   - "Is this actually correct?"
   - "Are there security issues?" (injection, validation, secrets)
   - "Is the reasoning complete?"
3. **Fix issues before responding**
4. **Note significant fixes**: "Self-review: [what you caught]"

### What to Check

**For code-related work:**
- Edge cases handled?
- Input validation present?
- Error handling complete?
- Security issues (OWASP Top 10)?
- Tests cover the changes?

**For analysis/planning work:**
- Reasoning complete?
- Assumptions stated?
- Alternatives considered?
- Risks identified?

---

## Development Commands

### Linting and Testing (Pre-Commit)

```bash
# One-time setup (if .venv doesn't exist)
uv venv
uv pip install -e ".[dev]"

# Install pre-commit hooks (recommended - runs automatically before each commit)
pre-commit install

# Complete pre-commit workflow (manual)
uv run ruff format . && uv run ruff check . && uv run pytest tests/

# Individual commands
uv run ruff format .                       # Format code
uv run ruff check .                        # Lint code
uv run ruff check . --fix                  # Auto-fix linting issues
uv run pytest tests/                       # Run all tests
uv run pytest tests/test_client.py::TestClass -v  # Run specific test class

# Run all pre-commit hooks manually (without committing)
pre-commit run --all-files
```

### Building and Installing

```bash
# Install in development mode with dev dependencies
uv pip install -e ".[dev]"

# Build wheel
uvx --from build pyproject-build --installer uv

# Run MCP server locally
uv run python -m mcp_acp.server
```

---

## Architecture Overview

### Three-Layer Design

**1. MCP Server Layer (`server.py`)**
- Exposes 26 MCP tools via stdio protocol
- Inline JSON Schema definitions per tool
- if/elif dispatch in `call_tool()` maps tool names to handlers
- Server-layer confirmation enforcement for destructive bulk operations

**2. Client Layer (`client.py`)**
- `ACPClient` communicates with the public-api gateway via `httpx`
- All interactions happen via HTTP REST calls with Bearer token auth
- Input validation (DNS-1123), bulk safety limits
- Async I/O throughout (all operations are `async def`)

**3. Formatting Layer (`formatters.py`)**
- Converts raw API responses to user-friendly text
- Handles dry-run output, error states, bulk results
- Format functions: `format_result()`, `format_bulk_result()`, `format_sessions_list()`, `format_session_created()`, `format_logs()`, `format_transcript()`, `format_metrics()`, `format_labels()`, `format_login()`, etc.

### Data Flow

```
MCP Client (Claude Desktop/CLI)
    ↓ MCP stdio protocol
MCP Server (list_tools, call_tool)
    ↓ if/elif dispatch
ACPClient method (e.g., delete_session)
    ↓ httpx REST call with Bearer token
Public API Gateway
    ↓ Kubernetes API
ACP AgenticSession Resource
```

---

## Key Architectural Patterns

### Confirmation Enforcement (Server Layer)

Destructive bulk operations require `confirm=true`:

```python
# In call_tool():
if not arguments.get("dry_run") and not arguments.get("confirm"):
    raise ValueError("Bulk delete requires confirm=true. Use dry_run=true to preview first.")
```

### Bulk Operation Safety (Client Layer)

All bulk operations enforce 3-item max:

```python
def _validate_bulk_operation(self, items: list[str], operation_name: str):
    if len(items) > self.MAX_BULK_ITEMS:  # MAX_BULK_ITEMS = 3
        raise ValueError(f"Bulk {operation_name} limited to 3 items for safety.")
```

### HTTP Request Pattern

All API calls go through `_request()`:

```python
async def _request(self, method, path, project, cluster_name=None, json_data=None, params=None):
    """Make an HTTP request to the public API."""
    cluster_config = self._get_cluster_config(cluster_name)
    token = self._get_token(cluster_config)
    url = f"{cluster_config['server']}{path}"
    headers = {"Authorization": f"Bearer {token}", "X-Ambient-Project": project}
    # ... httpx request with error handling
```

---

## Security Architecture

### Input Validation

**Kubernetes naming (DNS-1123):**
```python
def _validate_input(self, value: str, field_name: str):
    if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', value):
        raise ValueError(f"{field_name} contains invalid characters")
```

### HTTP Client Security

- All API calls use Bearer token authentication
- TLS required (server URLs must start with `https://` or `http://`)
- Direct Kubernetes API URLs (port 6443) are rejected at config validation
- Tokens sourced from `clusters.yaml` or `ACP_TOKEN` environment variable
- Sensitive data (tokens, passwords) filtered from logs

### Gateway URL Enforcement

```python
@field_validator("server")
def validate_server_url(cls, v: str) -> str:
    if not v.startswith(("https://", "http://")):
        raise ValueError("Server URL must start with https:// or http://")
    if ":6443" in v:
        raise ValueError("Direct Kubernetes API URLs (port 6443) are not supported.")
    return v.rstrip("/")
```

---

## Testing Standards

### Simple, Focused Unit Tests

**Pattern: One Test Class Per Feature**

```python
class TestBulkSafety:
    """Tests for bulk operation safety limits."""

    def test_validate_bulk_operation_exceeds_limit(self, client):
        """Should raise ValueError with >3 items."""
        with pytest.raises(ValueError, match="limited to 3 items"):
            client._validate_bulk_operation(["s1", "s2", "s3", "s4"], "delete")

class TestHTTPRequests:
    """Tests for HTTP request handling."""

    @pytest.mark.asyncio
    async def test_list_sessions(self, client):
        """Should list sessions via HTTP."""
        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client
            result = await client.list_sessions("test-project")
            assert result["total"] == 1
```

### What to Test

**DO test:**
- Happy path (basic success case)
- Critical validation (input validation, safety limits)
- Error conditions users will hit
- Bulk operation limits

**DON'T test:**
- Every possible edge case
- Implementation details
- Kubernetes API behavior
- Third-party libraries

### Mocking Strategy

```python
# GOOD: Mock the HTTP client
with patch.object(client, "_get_http_client") as mock_get_client:
    mock_http_client = AsyncMock()
    mock_http_client.request = AsyncMock(return_value=mock_response)
    mock_get_client.return_value = mock_http_client
    result = await client.some_method()

# BAD: Don't mock the method you're testing
with patch.object(client, "some_method"):
    result = await client.some_method()
```

---

## Configuration

### Cluster Configuration

`~/.config/acp/clusters.yaml`:

```yaml
clusters:
  vteam-stage:
    server: https://public-api-ambient.apps.vteam-stage.example.com
    token: your-bearer-token-here
    description: "V-Team Staging Environment"
    default_project: my-workspace

default_cluster: vteam-stage
```

### Settings Management (`settings.py`)

Uses Pydantic Settings for configuration:

```python
class Settings(BaseSettings):
    config_path: Path = Path.home() / ".config" / "acp" / "clusters.yaml"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="MCP_ACP_",
        case_sensitive=False,
    )
```

---

## Code Organization

```
src/mcp_acp/
├── __init__.py           # Package initialization
├── settings.py           # Pydantic settings and config loading
├── client.py             # ACPClient - httpx REST client
├── server.py             # MCP server - tool definitions and dispatch
└── formatters.py         # Output formatting functions

tests/
├── test_client.py        # Client unit tests
├── test_server.py        # Server integration tests
└── test_formatters.py    # Formatter tests

utils/
└── pylogger.py           # Structured logging (structlog)
```

---

## Common Development Tasks

### Adding a New MCP Tool

1. **Add client method** in `client.py`:
```python
async def new_operation(self, project: str, param: str) -> dict[str, Any]:
    """Docstring."""
    self._validate_input(param, "param")
    return await self._request("GET", f"/v1/resource/{param}", project)
```

2. **Add tool definition** in `list_tools()` in `server.py`:
```python
Tool(
    name="acp_new_operation",
    description="Description of what it does",
    inputSchema={
        "type": "object",
        "properties": {
            "project": {"type": "string", "description": "Project/namespace"},
            "param": {"type": "string", "description": "Parameter"},
        },
        "required": ["param"],
    },
)
```

3. **Add dispatch branch** in `call_tool()` in `server.py`:
```python
elif name == "acp_new_operation":
    result = await client.new_operation(
        project=arguments.get("project", ""),
        param=arguments["param"],
    )
    text = format_result(result)
```

4. **Write unit tests** in `tests/test_client.py`:
```python
class TestNewOperation:
    @pytest.mark.asyncio
    async def test_success(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.request = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client
            result = await client.new_operation("test-project", "param-value")
            assert result["result"] == "ok"
```

---

## Debugging Tips

### Enable Verbose Logging

```bash
export MCP_ACP_LOG_LEVEL=DEBUG
python -m mcp_acp.server
```

### Inspect MCP Tool Schemas

```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | python -m mcp_acp.server
```

---

## Important Constants

From `client.py`:

```python
MAX_BULK_ITEMS = 3
DEFAULT_TIMEOUT = 30.0  # seconds (httpx request timeout)

LABEL_VALUE_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$")

SESSION_TEMPLATES = {
    "triage": {"workflow": "triage", "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.7}},
    "bugfix": {"workflow": "bugfix", "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.3}},
    "feature": {"workflow": "feature-development", "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.5}},
    "exploration": {"workflow": "codebase-exploration", "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.8}},
}
```

---

## Dependencies

**Core:**
- `mcp>=1.0.0` - MCP protocol SDK
- `pydantic>=2.0.0` - Settings and validation
- `pydantic-settings>=2.0.0` - Environment-based settings
- `structlog>=25.0.0` - Structured logging
- `httpx>=0.27.0` - HTTP client for public-api gateway
- `pyyaml>=6.0` - Config file parsing

**Development:**
- `pytest>=7.0.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-cov>=4.0.0` - Coverage reporting
- `ruff>=0.12.0` - Code formatting and linting
- `mypy>=1.0.0` - Type checking

**Runtime Requirement:**
- Bearer token configured in `clusters.yaml` or `ACP_TOKEN` environment variable
- Network access to the public-api gateway

---

## Documentation

- **[README.md](README.md)** - Project overview, quick start, and usage guide
- **[API_REFERENCE.md](API_REFERENCE.md)** - Complete tool specifications (26 tools)
- **[SECURITY.md](SECURITY.md)** - Security features and threat model

---

## Notes for Future Claude Instances

### When Modifying Bulk Operations

- Always enforce `MAX_BULK_ITEMS = 3` limit
- Add server-layer confirmation check in `call_tool()`
- Support `dry_run` parameter
- Write focused unit tests

### When Working with Async Code

- All client methods are async (`async def`)
- Use `await` when calling client methods
- Mock httpx with `AsyncMock` for async functions
- Use `@pytest.mark.asyncio` for async tests

### When Adding New Tools

- See issues [#28](https://github.com/ambient-code/mcp/issues/28) and [#29](https://github.com/ambient-code/mcp/issues/29) for the remaining planned tools
- Follow the 4-step pattern: client method -> tool definition -> dispatch branch -> tests
- All API calls go through `_request()` or `_request_text()` methods

### When Working with Label Operations

- Labels are validated via `_validate_labels()` using `LABEL_VALUE_PATTERN`
- Label keys and values: 1-63 chars, alphanumeric, dashes, dots, underscores
- Label selectors are built as `key1=value1,key2=value2` query strings
- Bulk label/unlabel operations use `_validate_bulk_operation()` for the 3-item limit
- "By label" bulk operations first resolve labels to session names via `_run_bulk_by_label()`

### Code Quality Standards

- **NO line length enforcement** (ignore E501)
- Use double quotes for strings
- One import per line
- Simple > complex (avoid over-engineering)
- Test critical paths only
