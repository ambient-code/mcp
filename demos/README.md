# MCP-ACP Demo Guide

> 8 terminal recordings demonstrating MCP-ACP workflows based on real Claude Code sessions

**Coverage:** 19/19 tools (100%) | **Formats:** `.sh`, `.cast`, `.gif`, `.mp4` | **Size:** ~4.3MB

**Visual Style:** Black background (`#000000`), white text (`#ffffff`), IBM Plex Mono 14pt, 108×35 terminal

## Demo Catalog

### Basic Workflows (Demos 1-4)

**Demo 1: Discovery** (~15s) - `acp_list_projects`, `acp_list_sessions`, `acp_get_events`
Daily project navigation and session monitoring.

**Demo 2: Lifecycle** (~20s) - `acp_create_session`, `acp_get_session`, `acp_stop_session`
Create, check status, and stop sessions.

**Demo 3: Investigation** (~18s) - `acp_list_sessions`, `acp_get_events`
Monitor active sessions and retrieve event history.

**Demo 4: Delete Workaround** (~12s) - Shows missing delete tool, bash fallback to `oc delete`

### Advanced Workflows (Demos 5-8)

#### Demo 5: Session Templates ⚡
**~25s** | 391-message session | "How can I connect OpenCode CLI to Ambient Code Platform?"

**Tools:** `acp_list_workflows`, `acp_create_session_from_template`, `acp_get_session`

Lists templates (triage, bugfix, feature, integration) → Creates session with pre-loaded repos, K8s context, docs, and workflow phases.

**Impact:** 60% time reduction (~45min saved) on multi-repo integration setup.

#### Demo 6: Crash Recovery + Bulk Operations ⭐
**~45s** | 295-message session | "our last session crashed... working on agentready repo"

**Tools:** `acp_list_sessions(status="failed")`, `acp_get_session_transcript`, `acp_clone_session`, `acp_bulk_create_sessions`, `acp_get_session_metrics`, `acp_bulk_stop_sessions`

Session crashed after analyzing 6/13 features → List failed → Get transcript (295 msgs) → Clone → Bulk create 7 parallel sessions → Monitor metrics (73% complete) → Bulk stop.

**Impact:** 72% time reduction (3h → 50min). Shows real crash recovery, parallelization (7 concurrent sessions), and multi-agent orchestration.

#### Demo 7: Metrics & Export
**~35s** | 5,262-message session (6h 23m) | "Search for code patterns... testing LLM-generated code"

**Tools:** `acp_get_session_metrics`, `acp_update_session`, `acp_get_session_logs`, `acp_export_session`

Get metrics (5,262 msgs, 1,847 tool calls, 412 files, $127.50 token cost) → Extend timeout (6h→12h) → Get logs → Export for archival.

**Impact:** Observability for monster sessions, cost tracking, team sharing, compliance trails.

#### Demo 8: Multi-Provider Comparison
**~30s** | Bulk operations across AI providers

**Tools:** `acp_bulk_create_sessions`, `acp_bulk_send_message`, `acp_bulk_get_session_metrics`, `acp_bulk_stop_sessions`

Query Google Gemini, Anthropic Claude, OpenAI GPT-4 in parallel for comparison and A/B testing.

## Tool Coverage (19/19)

**Basic (8):** `acp_whoami`, `acp_list_projects`, `acp_list_sessions`, `acp_get_session`, `acp_create_session`, `acp_stop_session`, `acp_get_events`, `acp_send_message`

**Templates (2):** `acp_list_workflows`, `acp_create_session_from_template`

**Recovery (3):** `acp_get_session_transcript`, `acp_restart_session`, `acp_clone_session`

**Bulk (4):** `acp_bulk_create_sessions`, `acp_bulk_stop_sessions`, `acp_bulk_send_message`, `acp_bulk_get_session_metrics`

**Observability (4):** `acp_get_session_metrics`, `acp_get_session_logs`, `acp_update_session`, `acp_export_session`

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
