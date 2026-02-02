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
# Complete pre-commit workflow
black . && isort . && flake8 . --ignore=E501,E203,W503 && pytest tests/

# Individual commands
black .                                     # Format code
isort .                                     # Sort imports
flake8 . --ignore=E501,E203,W503           # Lint (no line length enforcement)
pytest tests/                              # Run all tests
pytest tests/test_client.py::TestClass -v  # Run specific test class
```

### Building and Installing

```bash
# Install in development mode
uv pip install -e .

# Build wheel
python -m build

# Run MCP server locally
python -m mcp_acp.server
```

---

## Architecture Overview

### Three-Layer Design

**1. MCP Server Layer (`server.py`)**
- Exposes 27 MCP tools via stdio protocol
- Schema-driven tool definitions using `SCHEMA_FRAGMENTS`
- Dispatch table maps tool names to (handler, formatter) pairs
- Server-layer confirmation enforcement for destructive bulk operations

**2. Client Layer (`client.py`)**
- `ACPClient` wraps OpenShift CLI (`oc`) operations
- All interactions with Kubernetes happen via subprocess execution
- Input validation, bulk safety limits, label management
- Async I/O throughout (all operations are `async def`)

**3. Formatting Layer (`formatters.py`)**
- Converts raw responses to user-friendly text
- Handles dry-run output, error states, bulk results
- Format functions: `format_result()`, `format_bulk_result()`, `format_sessions_list()`, etc.

### Data Flow

```
MCP Client (Claude Desktop/CLI)
    ↓ MCP stdio protocol
MCP Server (list_tools, call_tool)
    ↓ Dispatch table lookup
ACPClient method (e.g., delete_session)
    ↓ Input validation + safety checks
OpenShift CLI (oc delete agenticsession ...)
    ↓ Kubernetes API
ACP AgenticSession Resource
```

---

## Key Architectural Patterns

### Schema Fragment Reuse

Tools share common parameter schemas via `SCHEMA_FRAGMENTS` in `server.py`:

```python
SCHEMA_FRAGMENTS = {
    "project": {...},
    "session": {...},
    "dry_run": {...},
    "labels_dict": {...},
    # ... etc
}

# Build tool schema
Tool(
    name="acp_label_resource",
    inputSchema=create_tool_schema(
        properties={"resource_type": "resource_type", "labels": "labels_dict"},
        required=["resource_type", "labels"]
    )
)
```

### Dispatch Table Pattern

`create_dispatch_table()` maps tool names to handler/formatter pairs:

```python
{
    "acp_delete_session": (
        client.delete_session,      # Handler
        format_result,              # Formatter
    ),
    "acp_bulk_delete_sessions": (
        lambda **args: _check_confirmation_then_execute(...),  # Wrapper for safety
        lambda r: format_bulk_result(r, "delete"),
    ),
}
```

### Confirmation Enforcement (Server Layer)

Destructive bulk operations require `confirm=true`:

```python
async def _check_confirmation_then_execute(fn, args, operation):
    """Enforce confirmation at server layer."""
    if not args.get('dry_run') and not args.get('confirm'):
        raise ValueError(f"Bulk {operation} requires explicit confirmation.")
    return await fn(**args)
```

### Bulk Operation Safety (Client Layer)

All bulk operations enforce 3-item max:

```python
def _validate_bulk_operation(self, items: List[str], operation_name: str):
    if len(items) > self.MAX_BULK_ITEMS:  # MAX_BULK_ITEMS = 3
        raise ValueError(f"Bulk {operation_name} limited to 3 items for safety.")
```

---

## Label Management System

### Label Format

All user labels are prefixed: `acp.ambient-code.ai/label-{key}={value}`

### Label Operations

```python
# Individual operations
await client.label_resource("agenticsession", "session-1", "project", {"env": "dev"})
await client.unlabel_resource("agenticsession", "session-1", "project", ["env"])

# Bulk operations (max 3 items)
await client.bulk_label_resources("agenticsession", ["s1", "s2"], "project", {"team": "api"})

# List by label
await client.list_sessions_by_user_labels("project", labels={"env": "dev"})

# Bulk operations by label (max 3 matched sessions)
await client.bulk_delete_sessions_by_label("project", labels={"cleanup": "true"})
```

### Early Validation Pattern

Label-based bulk operations validate count BEFORE processing:

```python
session_names = [s["metadata"]["name"] for s in sessions]
if len(session_names) > self.MAX_BULK_ITEMS:
    raise ValueError(
        f"Label selector matches {len(session_names)} sessions. "
        f"Max {self.MAX_BULK_ITEMS} allowed. Refine your labels."
    )
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

**Label selector validation:**
```python
if selector and not re.match(r"^[a-zA-Z0-9=,_.\-/]+$", selector):
    raise ValueError(f"Invalid label selector format: {selector}")
```

### Command Injection Prevention

```python
# Always use asyncio.create_subprocess_exec (NOT shell=True)
process = await asyncio.create_subprocess_exec(
    "oc", "delete", "agenticsession", name, "-n", project,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)

# Validate arguments before execution
for arg in args:
    if any(char in arg for char in [';', '|', '&', '$', '`', '\n', '\r']):
        raise ValueError(f"Argument contains suspicious characters: {arg}")
```

### Resource Type Whitelist

```python
ALLOWED_RESOURCE_TYPES = {"agenticsession", "pods", "event"}

if resource_type not in self.ALLOWED_RESOURCE_TYPES:
    raise ValueError(f"Resource type '{resource_type}' not allowed")
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

class TestLabelOperations:
    """Tests for label operations."""

    @pytest.mark.asyncio
    async def test_label_resource_success(self, client):
        """Should label resource successfully."""
        with patch.object(client, "_run_oc_command", return_value=MagicMock(returncode=0)):
            result = await client.label_resource(...)
            assert result["labeled"] is True
```

### What to Test

✅ **DO test:**
- Happy path (basic success case)
- Critical validation (input validation, safety limits)
- Error conditions users will hit
- Bulk operation limits

❌ **DON'T test:**
- Every possible edge case
- Implementation details
- Kubernetes API behavior
- Third-party libraries

### Mocking Strategy

```python
# ✅ GOOD: Mock external dependencies
with patch.object(client, "_run_oc_command", return_value=mock_response):
    result = await client.some_method()

# ❌ BAD: Don't mock the method you're testing
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
    server: https://api.vteam-stage.example.com:443
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
    max_sessions: int = 100

    class Config:
        env_prefix = "ACP_"  # Environment variables: ACP_LOG_LEVEL, etc.
```

---

## Code Organization

```
src/mcp_acp/
├── __init__.py           # Package initialization
├── settings.py           # Pydantic settings and config loading
├── client.py             # ACPClient - OpenShift CLI wrapper (600+ lines)
├── server.py             # MCP server - tool definitions and dispatch (800+ lines)
└── formatters.py         # Output formatting functions (400+ lines)

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
async def new_operation(self, project: str, param: str) -> Dict[str, Any]:
    """Docstring."""
    # Validation
    self._validate_input(param, "param")
    # Execute
    result = await self._run_oc_command([...])
    return {"success": True, ...}
```

2. **Add schema fragment** in `server.py` (if needed):
```python
SCHEMA_FRAGMENTS["new_param"] = {
    "type": "string",
    "description": "New parameter description",
}
```

3. **Add tool definition** in `list_tools()`:
```python
Tool(
    name="acp_new_operation",
    description="Description of what it does",
    inputSchema=create_tool_schema(
        properties={"project": "project", "param": "new_param"},
        required=["param"]
    ),
)
```

4. **Add dispatch entry** in `create_dispatch_table()`:
```python
"acp_new_operation": (
    client.new_operation,
    format_result,
),
```

5. **Write unit tests** in `tests/test_client.py`:
```python
class TestNewOperation:
    @pytest.mark.asyncio
    async def test_success(self, client):
        with patch.object(client, "_run_oc_command", ...):
            result = await client.new_operation(...)
            assert result["success"] is True
```

### Adding Bulk Safety to New Operations

1. Call `_validate_bulk_operation()` early:
```python
async def bulk_new_operation(self, items: List[str], ...):
    self._validate_bulk_operation(items, "operation_name")
    # ... rest of implementation
```

2. Add confirmation wrapper in dispatch table:
```python
"acp_bulk_new_operation": (
    lambda **args: _check_confirmation_then_execute(
        client.bulk_new_operation, args, "operation_name"
    ),
    format_bulk_result,
),
```

---

## Debugging Tips

### Enable Verbose Logging

```bash
# Set log level via environment variable
export ACP_LOG_LEVEL=DEBUG
python -m mcp_acp.server
```

### Test Individual Client Methods

```python
from mcp_acp.client import ACPClient

client = ACPClient()
result = await client.list_sessions(project="my-workspace")
print(result)
```

### Inspect MCP Tool Schemas

```bash
# List available tools
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | python -m mcp_acp.server
```

---

## Important Constants

From `client.py`:

```python
ALLOWED_RESOURCE_TYPES = {"agenticsession", "pods", "event"}
MAX_BULK_ITEMS = 3
LABEL_PREFIX = "acp.ambient-code.ai/label-"
MAX_COMMAND_TIMEOUT = 120  # seconds
MAX_LOG_LINES = 10000
```

---

## Dependencies

**Core:**
- `mcp>=1.0.0` - MCP protocol SDK
- `pydantic>=2.0.0` - Settings and validation
- `structlog>=25.0.0` - Structured logging
- `pyyaml>=6.0` - Config file parsing

**Development:**
- `pytest>=7.0.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-cov>=4.0.0` - Coverage reporting
- `black` - Code formatting
- `isort` - Import sorting
- `flake8` - Linting (ignore E501, E203, W503)

**Runtime Requirement:**
- OpenShift CLI (`oc`) must be installed and in PATH
- Authenticated session via `oc login`

---

## Documentation

- **[README.md](README.md)** - Project overview and quick start
- **[API_REFERENCE.md](API_REFERENCE.md)** - Complete tool specifications
- **[SECURITY.md](SECURITY.md)** - Security features and threat model
- **[QUICKSTART.md](QUICKSTART.md)** - Usage examples and workflows

---

## Notes for Future Claude Instances

### When Modifying Bulk Operations

- Always enforce `MAX_BULK_ITEMS = 3` limit
- Add server-layer confirmation via `_check_confirmation_then_execute()`
- Include early validation for label-based operations
- Support `dry_run` parameter
- Write focused unit tests

### When Adding Label Support

- Use `LABEL_PREFIX` constant for all user labels
- Validate label keys/values (max 63 chars, alphanumeric + dash/underscore/dot)
- Build K8s label selectors with proper prefixes
- Test with label selector regex: `r"^[a-zA-Z0-9=,_.\-/]+$"`

### When Working with Async Code

- All client methods are async (`async def`)
- Use `await` when calling client methods
- Mock with `AsyncMock` for async functions
- Use `@pytest.mark.asyncio` for async tests

### Code Quality Standards

- **NO line length enforcement** (ignore E501)
- Use double quotes for strings
- One import per line
- Simple > complex (avoid over-engineering)
- Test critical paths only
