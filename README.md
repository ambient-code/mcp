# Ambient Code Platform MCP Server

Delegate work to Kubernetes-hosted Claude agents running on OpenShift.

## What It Does

Offload expensive or long-running AI tasks to the cluster. Example workflow:

1. Create session: "Analyze this 50k line codebase for security vulnerabilities"
2. Session runs on ACP (Kubernetes pod with Claude)
3. Check status periodically
4. Fetch results when done
5. Stop session to free resources

## Tools

| Tool                 | Description                                |
| -------------------- | ------------------------------------------ |
| `acp_whoami`         | Check OpenShift auth status                |
| `acp_list_projects`  | List available projects/namespaces         |
| `acp_list_sessions`  | List agentic sessions in a project         |
| `acp_get_session`    | Get session details and status             |
| `acp_get_events`     | Get session status snapshot                |
| `acp_create_session` | Create a new agentic session with a prompt |
| `acp_send_message`   | Send follow-up message to a session        |
| `acp_stop_session`   | Stop a running session                     |

## Quickstart

### 1. Clone

```bash
git clone https://github.com/ambient-code/mcp.git
cd mcp
```

### 2. Install dependencies

```bash
bun install
```

### 3. Login to OpenShift

```bash
oc login --token=<your-token> --server=<your-openshift-api-server>

# Verify
oc whoami
```

### 4. Configure your MCP client

#### OpenCode

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "ambient-code": {
      "type": "local",
      "command": ["bun", "run", "/path/to/mcp/src/index.ts"],
      "environment": {
        "ACP_BASE_URL": "https://<your-acp-route>"
      }
    }
  }
}
```

#### Claude Desktop, Claude Code CLI, OpenAI Codex CLI

These clients use the standard MCP config format. Add to:

| Client                   | Config file                                                       |
| ------------------------ | ----------------------------------------------------------------- |
| Claude Desktop (macOS)   | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json`                     |
| Claude Code CLI          | `~/.claude/settings.json`                                         |
| OpenAI Codex CLI         | `~/.codex/config.json`                                            |

```json
{
  "mcpServers": {
    "ambient-code": {
      "command": "bun",
      "args": ["run", "/path/to/mcp/src/index.ts"],
      "env": {
        "ACP_BASE_URL": "https://<your-acp-route>"
      }
    }
  }
}
```

### 5. Restart your client

The tools will be available after restart.

## Usage

Just talk to your AI assistant naturally. It will use the tools automatically.

**You say:**

> "Am I logged in to OpenShift?"

> "What projects do I have access to?"

> "Show me the running sessions in my workspace"

> "Create a new session called 'Security Audit' and have it analyze this repo for SQL injection vulnerabilities"

> "Tell that session to also check for XSS issues"

> "Stop that session when it's done"

## Testing

```bash
# Set the required environment variable
export ACP_BASE_URL="https://<your-acp-route>"

# Test tools/list
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | bun run src/index.ts

# Test whoami
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"acp_whoami","arguments":{}}}' | bun run src/index.ts

# Test list projects
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"acp_list_projects","arguments":{}}}' | bun run src/index.ts
```

## Environment Variables

| Variable       | Required | Description                                                     |
| -------------- | -------- | --------------------------------------------------------------- |
| `ACP_BASE_URL` | Yes      | Ambient Code Platform API URL (e.g., `https://acp.example.com`) |

## How Authentication Works

The MCP server uses `oc whoami -t` to get your current OpenShift token. This means:

- You must be logged in via `oc login` before using the tools
- Tokens expire - re-login if you get auth errors
- Both `Authorization: Bearer` and `X-Forwarded-Access-Token` headers are sent (ACP requirement)

## License

Apache-2.0
