# MCP ACP Server - Quick Start Guide

Get up and running with MCP ACP Server in 10 minutes.

---

## Prerequisites

- **Python 3.10 or higher**
- **OpenShift CLI (`oc`)** - Will be installed automatically if missing
- **Access to an OpenShift cluster** with ACP (Ambient Code Platform)
- **Claude Desktop** or another MCP-compatible client

---

## Installation

### macOS

```bash
# Run the installation script
chmod +x install-macos.sh
./install-macos.sh

# Restart your shell
exec $SHELL
```

### Linux

```bash
# Run the installation script
chmod +x install-linux.sh
./install-linux.sh

# Restart your shell
exec $SHELL
```

### Manual Installation

```bash
# Install from PyPI (when published)
pip install mcp-acp

# Or install from wheel
pip install dist/mcp_acp-*.whl

# Or install from source
pip install .
```

---

## Configuration

### 1. Create Cluster Configuration

Edit `~/.config/acp/clusters.yaml` with your actual cluster details:

```yaml
clusters:
  my-cluster:
    server: https://api.your-cluster.example.com:6443
    description: "My OpenShift Cluster"
    default_project: my-workspace

default_cluster: my-cluster
```

**Important**: Replace with your actual:

- Cluster API server URL
- Default project/namespace name

### 2. Authenticate to OpenShift

```bash
# Option 1: Token authentication (recommended)
oc login --server=https://api.your-cluster.example.com:6443 \
  --token=YOUR_TOKEN_HERE

# Option 2: Username/password
oc login --server=https://api.your-cluster.example.com:6443 \
  --username=your-username

# Option 3: Web authentication
oc login --web
```

> **Note**: Direct OpenShift CLI authentication is required for testing until the frontend API is available (tracked in PR #558).

**Get your token**: In OpenShift web console → Click your username → Copy login command → Show token

### 3. Verify Authentication

```bash
# Check you're logged in
oc whoami

# Verify you can access your project
oc project your-project-name

# Check if ACP sessions exist
oc get agenticsession -n your-project-name
```

---

## Claude Desktop Integration

### macOS Configuration

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "acp": {
      "command": "mcp-acp"
    }
  }
}
```

### Linux Configuration

Edit: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "acp": {
      "command": "mcp-acp"
    }
  }
}
```

### Restart Claude Desktop

After editing the config, **completely quit and restart Claude Desktop** (not just close the window).

---

## First Commands

Try these in Claude Desktop to verify everything works:

### Check Authentication

```
Use acp_whoami to check my authentication status
```

**Expected Output:**

```
Current Authentication Status:

Authenticated: Yes
User: your-username
Server: https://api.your-cluster.example.com:6443
Project: your-project-name
Token Valid: Yes
```

### List Sessions

```
List all sessions in my-workspace project
```

### Filter Sessions

```
List only running sessions in my-workspace
```

```
Show me sessions older than 7 days in my-workspace
```

### Delete with Dry-Run (Safe!)

```
Delete old-session from my-workspace in dry-run mode
```

This shows what would be deleted without actually deleting it.

### Get Session Logs

```
Get logs from debug-session in my-workspace
```

---

## Common Usage Patterns

### Find Old Sessions to Clean Up

```
List stopped sessions older than 7 days in my-workspace
```

Then bulk delete them (with dry-run first):

```
Delete these sessions: session-1, session-2, session-3 from my-workspace (dry-run first)
```

### Debug a Failed Session

```
List failed sessions in my-workspace
```

Then get logs:

```
Get logs from failed-session in my-workspace, last 200 lines
```

### Restart Stopped Sessions

```
List stopped sessions in my-workspace
```

Then restart:

```
Restart my-session in my-workspace
```

---

## Troubleshooting

### "oc: command not found"

The installation script should have installed it. If not:

**macOS**:

```bash
brew install openshift-cli
```

**Linux**:

```bash
curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz | \
  tar -xz -C /tmp && \
  sudo mv /tmp/oc /usr/local/bin/
```

### "mcp-acp: command not found"

Add Python user bin to PATH:

**macOS**:

```bash
export PATH="$HOME/Library/Python/3.*/bin:$PATH"
```

**Linux**:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then restart your shell.

### "error: You must be logged in to the server"

Your token expired. Re-authenticate:

```bash
oc login --server=https://your-cluster:6443
```

### "error: the server doesn't have a resource type 'agenticsession'"

Either:

1. Your cluster doesn't have ACP installed
2. You're in the wrong project/namespace

Check available projects:

```bash
oc projects
```

### MCP Tools Not Showing in Claude

1. Check Claude Desktop logs: Help → View Logs
2. Verify config file syntax is valid JSON
3. Make sure `mcp-acp` is in PATH
4. Restart Claude Desktop completely (quit, not just close)

### "Permission denied" on clusters.yaml

Fix permissions:

```bash
chmod 600 ~/.config/acp/clusters.yaml
chmod 700 ~/.config/acp
```

---

## Available Tools (19 Total)

### Core Session Management

- `acp_list_sessions` - List/filter sessions
- `acp_delete_session` - Delete with dry-run
- `acp_restart_session` - Restart stopped sessions

### Bulk Operations

- `acp_bulk_delete_sessions` - Delete multiple
- `acp_bulk_stop_sessions` - Stop multiple

### Debugging

- `acp_get_session_logs` - Get container logs
- `acp_get_session_transcript` - Get conversation history
- `acp_get_session_metrics` - Usage statistics

### Advanced Features

- `acp_clone_session` - Clone configurations
- `acp_update_session` - Update metadata
- `acp_export_session` - Export session data
- `acp_create_session_from_template` - Create from template

### Cluster Management

- `acp_list_clusters` - List configured clusters
- `acp_whoami` - Check authentication
- `acp_login` - Web authentication
- `acp_switch_cluster` - Switch contexts
- `acp_add_cluster` - Add new cluster

### Workflows

- `acp_list_workflows` - Discover workflows

---

## Security Notes

- ✅ All 13 security tests passing
- ✅ Input validation on all parameters
- ✅ Command injection prevention
- ✅ Resource limits enforced
- ✅ Dry-run mode on all destructive operations
- ✅ Secure temporary file handling

**Always use dry-run first** before destructive operations!

---

## Getting Help

### Documentation

- **Full Usage Guide**: See `USAGE_GUIDE.md` for 40+ examples
- **API Reference**: See `API_REFERENCE.md` for all tool specs
- **Security**: See `SECURITY.md` for security features
- **Architecture**: See `ARCHITECTURE.md` for system design
- **Development**: See `DEVELOPMENT.md` for contributing

### Common Questions

**Q: Can I use this with multiple clusters?**
A: Yes! Add multiple clusters to `~/.config/acp/clusters.yaml` and use `acp_switch_cluster` to change between them.

**Q: Is it safe to delete sessions?**
A: Always use dry-run mode first (`dry_run=True`) to preview what will be deleted.

**Q: Can I use this outside of Claude Desktop?**
A: Yes! Any MCP-compatible client can use it. It communicates via stdio using the MCP protocol.

**Q: Where are logs stored?**
A: Server logs go to stderr. Configure your MCP client to capture them.

**Q: Can I run this in CI/CD?**
A: Yes! The Python API can be used programmatically. See `USAGE_GUIDE.md` for examples.

---

## Next Steps

### Learn More

1. **Explore Filtering**: Try different filter combinations with `acp_list_sessions`
2. **Bulk Operations**: Clean up old sessions efficiently
3. **Workflows**: Discover available workflows with `acp_list_workflows`
4. **Metrics**: Track usage with `acp_get_session_metrics`

### Advanced Usage

- Read the full **USAGE_GUIDE.md** for all 40+ examples
- Check **API_REFERENCE.md** for complete tool specifications
- Review **SECURITY.md** for security best practices

### Contributing

See **DEVELOPMENT.md** for:

- Development setup
- Testing guidelines
- Code quality standards
- Contribution process

---

## Quick Reference Card

| Task | Command Pattern |
|------|----------------|
| Check auth | `Use acp_whoami` |
| List all | `List sessions in PROJECT` |
| Filter status | `List running sessions in PROJECT` |
| Filter age | `List sessions older than 7d in PROJECT` |
| Delete (dry) | `Delete SESSION in PROJECT (dry-run)` |
| Delete (real) | `Delete SESSION in PROJECT` |
| Bulk delete | `Delete session-1, session-2 in PROJECT` |
| Restart | `Restart SESSION in PROJECT` |
| Get logs | `Get logs from SESSION in PROJECT` |
| List clusters | `Use acp_list_clusters` |

---

## Summary

You now have:

- ✅ MCP ACP Server installed
- ✅ OpenShift CLI configured
- ✅ Cluster authentication set up
- ✅ Claude Desktop integrated
- ✅ Ready to manage ACP sessions!

**Start managing your sessions with natural language through Claude!** 🚀

For detailed documentation, see the other guides in this package.

---

## Alternative: Using with uvx (Recommended)

**uvx** provides the fastest and easiest way to run MCP ACP Server without installation.

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Configure Claude Desktop

**macOS**: Edit `~/Library/Application Support/Claude/claude_desktop_config.json`

**Linux**: Edit `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "acp": {
      "command": "uvx",
      "args": ["mcp-acp"]
    }
  }
}
```

For local wheel (before PyPI publish):

```json
{
  "mcpServers": {
    "acp": {
      "command": "uvx",
      "args": [
        "--from",
        "/full/path/to/dist/mcp_acp-*.whl",
        "mcp-acp"
      ]
    }
  }
}
```

### Benefits of uvx

- ⚡ **10-100x faster** than pip
- 🔒 **Isolated** - no global Python pollution
- 🎯 **No installation** - runs directly
- 🚀 **Auto-caching** - subsequent runs are instant

See `UVX_USAGE.md` for complete uvx documentation.
