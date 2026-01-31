# MCP ACP Project Instructions

**Project**: MCP Server for Ambient Code Platform (ACP) management
**Repository**: https://github.com/jeremyeder/mcp (private fork)
**Last Updated**: 2026-01-31

---

## Testing Standards

**Core Principle: Keep It Simple. Always write unit tests.**

### Required: Unit Tests for All New Features

**Every new feature MUST have unit tests.**

#### Test What Matters

✅ **DO test:**
- Happy path (basic success case)
- Critical validation (e.g., input validation)
- Error conditions users will hit
- Safety limits (e.g., 3-item max in bulk operations)

❌ **DON'T test:**
- Every possible edge case
- Implementation details
- Third-party library behavior

---

### Simple Test Structure

**Pattern: One Test Class Per Feature**

```python
class TestFeatureName:
    """Tests for feature description."""

    @pytest.mark.asyncio
    async def test_basic_success(self, client):
        """Should work in the happy path."""
        with patch.object(client, "method", return_value=mock_value):
            result = await client.feature_method()
            assert result["success"] is True

    def test_validation_fails(self, client):
        """Should reject invalid input."""
        with pytest.raises(ValueError, match="expected error"):
            client.feature_method(bad_input)
```

**Keep tests focused:**
- One behavior per test
- Clear test names (describe what should happen)
- Simple assertions (check key outcomes only)

---

### Mocking Strategy

**Mock at the right level:**

```python
# ✅ GOOD: Mock external dependencies
with patch.object(client, "_run_oc_command", return_value=mock_response):
    result = await client.some_method()

# ❌ BAD: Don't mock the method you're testing
with patch.object(client, "some_method"):  # Testing nothing!
    result = await client.some_method()
```

**Use simple mock data:**

```python
# ✅ GOOD: Minimal mock data
mock_response = {"items": [{"metadata": {"name": "session-1"}}]}

# ❌ BAD: Overly detailed mock data (don't do this)
```

---

### Test Organization

**Directory structure:**
```
tests/
├── test_client.py          # Client method tests
├── test_server.py          # MCP server tests
└── test_formatters.py      # Formatter tests
```

**Group related tests in classes:**

```python
class TestBulkSafety:
    """Tests for bulk operation safety limits."""

class TestLabelOperations:
    """Tests for label operations."""
```

---

### Running Tests

**Quick workflow:**

```bash
# Run specific test class
pytest tests/test_client.py::TestLabelOperations -v

# Run all tests
pytest tests/ -v
```

**Pre-commit checklist:**

1. Run linting: `black . && isort . && flake8 . --ignore=E501,E203,W503`
2. Run tests: `pytest tests/`
3. Verify all pass

**NEVER commit if tests fail.**

---

### Common Patterns

**Async method testing:**
```python
@pytest.mark.asyncio
async def test_async_method(self, client):
    result = await client.async_method()
    assert result["success"]
```

**Mock multiple calls:**
```python
mock_cmd.side_effect = [
    MagicMock(returncode=0, stdout=json.dumps(data1).encode()),
    MagicMock(returncode=0, stderr=b""),
]
```

**Test count enforcement:**
```python
with pytest.raises(ValueError, match="Max 3 allowed"):
    await client.bulk_operation_by_label(labels={"cleanup": "true"})
```

---

### What NOT to Test

❌ **Don't test:**
- Kubernetes API behavior
- OpenShift CLI output format
- Python standard library
- External dependencies

✅ **DO test:**
- YOUR code behavior
- YOUR validation logic
- YOUR error handling
- YOUR safety limits

---

### Summary

**Simple rules:**

1. ✅ Always write unit tests for new features
2. ✅ Keep tests simple - test behavior, not implementation
3. ✅ Mock external calls - don't hit real APIs
4. ✅ Test critical paths - happy path + key validations
5. ✅ Run tests before commit - never commit failing tests
6. ❌ Don't overcomplicate - simple is better

**Remember: A simple test that runs is worth more than a comprehensive test that doesn't exist.**

---

## Development Workflow

### Linting (MANDATORY before commit)

```bash
black . && isort . && flake8 . --ignore=E501,E203,W503 && pytest tests/
```

### Branch Strategy

- Work in feature branches: `feature/description`
- Never push directly to main
- Check branch: `git branch --show-current`

### Commit Standards

```bash
git commit -m "$(cat <<'EOF'
type: Brief description

Detailed explanation of changes.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```

**Types**: feat, fix, test, refactor, docs, chore

---

## Architecture Notes

### Label Management

**Label format:**
```
acp.ambient-code.ai/label-{key}={value}
```

**Bulk operation safety:**
- Max 3 items per operation (enforced at client layer)
- Confirmation required for destructive ops (enforced at server layer)
- Early validation prevents processing when count > 3

### MCP Server Structure

- `client.py`: ACPClient with all operations
- `server.py`: MCP tool definitions and dispatch
- `formatters.py`: Output formatting for MCP responses
- `settings.py`: Configuration management

---

## Security

**Input validation:**
- Always validate Kubernetes resource names
- Restrict resource types to whitelist
- Validate label selectors (regex pattern)
- Never allow shell metacharacters in inputs

**Safety mechanisms:**
- 3-item max on all bulk operations
- Confirmation required for destructive bulk ops
- Dry-run mode for all destructive operations
