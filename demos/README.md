# MCP-ACP Demo Guide

> 8 terminal recordings demonstrating MCP-ACP workflows based on real Claude Code sessions

**Coverage:** 19/19 tools (100%) | **Formats:** `.sh`, `.cast`, `.gif`, `.mp4` | **Size:** ~4.2MB

**Visual Style:** Black background (`#000000`), white text (`#ffffff`), IBM Plex Mono 14pt, 108×35 terminal

---

## Table of Contents

- [Demo Gallery](#demo-gallery)
  - [Basic Workflows (Demos 1-4)](#basic-workflows-demos-1-4)
  - [Advanced Workflows (Demos 5-8)](#advanced-workflows-demos-5-8)
- [Tool Coverage (19/19)](#tool-coverage-1919)
- [Business Impact](#business-impact)
- [Recording Setup](#recording-setup)
  - [Terminal Configuration](#terminal-configuration)
  - [Recording Commands](#recording-commands)
  - [Bulk Recording](#bulk-recording)
  - [Troubleshooting](#troubleshooting)

---

## Demo Gallery

### Basic Workflows (Demos 1-4)

<table>
  <tr>
    <td width="50%">
      <h4>📋 Demo 1: Discovery (~15s)</h4>
      <img src="demo-1-discovery.png" alt="Demo 1: Discovery" width="100%">
      <video width="100%" controls>
        <source src="demo-1-discovery.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <p><strong>Tools:</strong> <code>acp_list_projects</code>, <code>acp_list_sessions</code>, <code>acp_get_events</code></p>
      <p>Daily project navigation and session monitoring.</p>
    </td>
    <td width="50%">
      <h4>🔄 Demo 2: Lifecycle (~20s)</h4>
      <img src="demo-2-lifecycle.png" alt="Demo 2: Lifecycle" width="100%">
      <video width="100%" controls>
        <source src="demo-2-lifecycle.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <p><strong>Tools:</strong> <code>acp_create_session</code>, <code>acp_get_session</code>, <code>acp_stop_session</code></p>
      <p>Create, check status, and stop sessions.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h4>🔍 Demo 3: Investigation (~18s)</h4>
      <img src="demo-3-investigation.png" alt="Demo 3: Investigation" width="100%">
      <video width="100%" controls>
        <source src="demo-3-investigation.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <p><strong>Tools:</strong> <code>acp_list_sessions</code>, <code>acp_get_events</code></p>
      <p>Monitor active sessions and retrieve event history.</p>
    </td>
    <td width="50%">
      <h4>⚠️ Demo 4: Delete Workaround (~12s)</h4>
      <img src="demo-4-missing-delete.png" alt="Demo 4: Delete Workaround" width="100%">
      <video width="100%" controls>
        <source src="demo-4-missing-delete.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <p><strong>Tools:</strong> Bash fallback (<code>oc delete</code>)</p>
      <p>Shows missing delete tool, bash fallback to <code>oc delete</code>.</p>
    </td>
  </tr>
</table>

### Advanced Workflows (Demos 5-8)

<table>
  <tr>
    <td width="50%">
      <h4>⚡ Demo 5: Session Templates (~25s)</h4>
      <img src="demo-5-session-template.png" alt="Demo 5: Session Templates" width="100%">
      <video width="100%" controls>
        <source src="demo-5-session-template.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <p><strong>Session:</strong> 391-message | "How can I connect OpenCode CLI to Ambient Code Platform?"</p>
      <p><strong>Tools:</strong> <code>acp_list_workflows</code>, <code>acp_create_session_from_template</code>, <code>acp_get_session</code></p>
      <p>Lists templates (triage, bugfix, feature, integration) → Creates session with pre-loaded repos, K8s context, docs, and workflow phases.</p>
      <p><strong>Impact:</strong> 60% time reduction (~45min saved) on multi-repo integration setup.</p>
    </td>
    <td width="50%">
      <h4>⭐ Demo 6: Crash Recovery + Bulk Operations (~45s)</h4>
      <img src="demo-6-crash-recovery.png" alt="Demo 6: Crash Recovery" width="100%">
      <video width="100%" controls>
        <source src="demo-6-crash-recovery.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <p><strong>Session:</strong> 295-message | "our last session crashed... working on agentready repo"</p>
      <p><strong>Tools:</strong> <code>acp_list_sessions(status="failed")</code>, <code>acp_get_session_transcript</code>, <code>acp_clone_session</code>, <code>acp_bulk_create_sessions</code>, <code>acp_get_session_metrics</code>, <code>acp_bulk_stop_sessions</code></p>
      <p>Session crashed after analyzing 6/13 features → List failed → Get transcript (295 msgs) → Clone → Bulk create 7 parallel sessions → Monitor metrics (73% complete) → Bulk stop.</p>
      <p><strong>Impact:</strong> 72% time reduction (3h → 50min). Shows real crash recovery, parallelization (7 concurrent sessions), and multi-agent orchestration.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h4>📊 Demo 7: Metrics & Export (~35s)</h4>
      <img src="demo-7-metrics-export.png" alt="Demo 7: Metrics & Export" width="100%">
      <video width="100%" controls>
        <source src="demo-7-metrics-export.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <p><strong>Session:</strong> 5,262-message (6h 23m) | "Search for code patterns... testing LLM-generated code"</p>
      <p><strong>Tools:</strong> <code>acp_get_session_metrics</code>, <code>acp_update_session</code>, <code>acp_get_session_logs</code>, <code>acp_export_session</code></p>
      <p>Get metrics (5,262 msgs, 1,847 tool calls, 412 files, $127.50 token cost) → Extend timeout (6h→12h) → Get logs → Export for archival.</p>
      <p><strong>Impact:</strong> Observability for monster sessions, cost tracking, team sharing, compliance trails.</p>
    </td>
    <td width="50%">
      <h4>🔀 Demo 8: Multi-Provider Comparison (~30s)</h4>
      <img src="demo-8-bulk-comparison.png" alt="Demo 8: Multi-Provider Comparison" width="100%">
      <video width="100%" controls>
        <source src="demo-8-bulk-comparison.mp4" type="video/mp4">
        Your browser does not support the video tag.
      </video>
      <p><strong>Session:</strong> Bulk operations across AI providers</p>
      <p><strong>Tools:</strong> <code>acp_bulk_create_sessions</code>, <code>acp_bulk_send_message</code>, <code>acp_bulk_get_session_metrics</code>, <code>acp_bulk_stop_sessions</code></p>
      <p>Query Google Gemini, Anthropic Claude, OpenAI GPT-4 in parallel for comparison and A/B testing.</p>
    </td>
  </tr>
</table>

---

## Tool Coverage (19/19)

**Basic (8):** `acp_whoami`, `acp_list_projects`, `acp_list_sessions`, `acp_get_session`, `acp_create_session`, `acp_stop_session`, `acp_get_events`, `acp_send_message`

**Templates (2):** `acp_list_workflows`, `acp_create_session_from_template`

**Recovery (3):** `acp_get_session_transcript`, `acp_restart_session`, `acp_clone_session`

**Bulk (4):** `acp_bulk_create_sessions`, `acp_bulk_stop_sessions`, `acp_bulk_send_message`, `acp_bulk_get_session_metrics`

**Observability (4):** `acp_get_session_metrics`, `acp_get_session_logs`, `acp_update_session`, `acp_export_session`

---

## Business Impact

**Productivity:** 60-72% time savings (templates + parallelization)
**Reliability:** Crash recovery, session checkpoints
**Visibility:** Metrics, logs, cost tracking ($127.50/session example)
**Collaboration:** Export/share sessions across teams

All based on real workflows, not synthetic examples.

---

# Recording Setup

## Terminal Configuration

**Install Font:**
```bash
brew install --cask font-ibm-plex-mono  # macOS
# Or: https://github.com/IBM/plex/releases
```

**iTerm2 Setup:**
- Font: IBM Plex Mono 14pt, spacing 1.0, line 1.33
- Colors: Background `#000000`, Foreground `#ffffff`
- Window: 108 cols × 35 rows, 0% transparency

## Recording Commands

**Record:**
```bash
asciinema rec demo.cast --cols 108 --rows 35 -c "./demo.sh" --overwrite
```

**Convert:**
```bash
brew install agg
agg --theme config.json demo.cast demo.gif
ffmpeg -i demo.gif -vf "fps=10,scale=1080:-1:flags=lanczos,format=yuv420p" \
  -c:v libx264 -preset slow -crf 23 -y demo.mp4
```

## Bulk Recording

```bash
#!/bin/bash
DEMOS=(demo-1-discovery demo-2-lifecycle demo-3-investigation demo-4-delete-workaround
       demo-5-session-template demo-6-crash-recovery demo-7-metrics-export demo-8-multi-provider)

for demo in "${DEMOS[@]}"; do
  asciinema rec "${demo}.cast" --cols 108 --rows 35 -c "./${demo}.sh" --overwrite
  agg --theme config.json "${demo}.cast" "${demo}.gif"
  ffmpeg -i "${demo}.gif" -vf "fps=10,scale=1080:-1:flags=lanczos,format=yuv420p" \
    -c:v libx264 -preset slow -crf 23 -y "${demo}.mp4"
done
```

## Troubleshooting

**Font not rendering:** agg uses system default - use `asciinema-player` for web embedding
**Background not black:** Set iTerm2 transparency to 0%, blur to 0%
**Text too dim:** Change `\033[2;37m` to `\033[0;90m` in scripts

**Output Quality:** 1080p, 10fps, ~2-8KB cast, ~50-500KB gif, ~100-800KB mp4
