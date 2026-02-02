#!/bin/bash
# Demo 7: Long-Running Session with Metrics & Export
# Based on: ses_47522be7bffeT8TLdeO4A3KDo2.jsonl (5,262 messages!!!)
# Shows: acp_get_session_metrics, acp_export_session, acp_update_session, acp_get_session_logs

# Claude Code color scheme
USER='\033[0;36m'      # Cyan for user messages
ASSISTANT='\033[0;37m' # White for assistant
TOOL='\033[2;37m'
ACCENT='\033[0;36m'
SUCCESS='\033[0;32m'
DIM='\033[2;37m'
RESET='\033[0m'

print() {
    printf "%b\n" "$1"
}

# Streaming text effect (simulates LLM generation)
stream() {
    local text="$1"
    local delay="${2:-0.02}"  # Default 20ms per char
    printf "    %b" "${ASSISTANT}"  # Output color code first
    for (( i=0; i<${#text}; i++ )); do
        printf "%s" "${text:$i:1}"  # Stream text char by char
        sleep "$delay"
    done
    printf "%b\n" "${RESET}"  # Reset color at end
}

user() {
    local text="$1"
    printf "\n    %b❯%b " "${USER}" "${RESET}"
    for (( i=0; i<${#text}; i++ )); do
        printf "%s" "${text:$i:1}"
        sleep 0.05  # 50ms per character (human typing speed)
    done
    printf "\n\n"
    sleep 2.0
}

assistant() {
    stream "$1" 0.015
    sleep 1.5
}

tool() {
    print "    ${TOOL}Using $1${RESET}"
    sleep 1.2
}

result() {
    print "    ${ASSISTANT}$1${RESET}"
    echo
    sleep 2.0
}

clear
echo
echo

# === DEMO START ===

user "I have a massive research session running. Can you show me its metrics?"

assistant "Let me check the session metrics..."
echo
sleep 0.5

tool "acp_list_sessions"
echo
sleep 1.0

result "Active sessions:
  ${ACCENT}session-1769218280${RESET} ${DIM}→ LLM testing patterns research${RESET}
    Status: Running for ${ACCENT}6 hours 23 minutes${RESET}
    Messages: ${ACCENT}5,262${RESET}"

user "Get detailed metrics for that monster session"

sleep 0.5

tool "acp_get_session_metrics"
echo
sleep 1.0

result "Session Metrics: ${ACCENT}session-1769218280${RESET}

${DIM}Duration:${RESET}
  • Total runtime: ${ACCENT}6h 23m${RESET}
  • Active time: ${ACCENT}5h 47m${RESET}
  • Idle time: ${ACCENT}36m${RESET}

${DIM}Activity:${RESET}
  • Messages: ${ACCENT}5,262${RESET}
  • Tool calls: ${ACCENT}1,847${RESET}
  • Repos explored: ${ACCENT}23${RESET}
  • Files analyzed: ${ACCENT}412${RESET}

${DIM}Token Usage:${RESET}
  • Input tokens: ${ACCENT}2.4M${RESET}
  • Output tokens: ${ACCENT}876K${RESET}

${DIM}Phases:${RESET}
  ${SUCCESS}✓${RESET} Research phase: 2h 15m (complete)
  ${SUCCESS}✓${RESET} Analysis phase: 3h 08m (complete)
  ${ACCENT}→${RESET} Documentation phase: 1h 00m (in progress)"

user "Export this session for archival before it finishes"

assistant "Exporting session with full transcript and context..."
echo
sleep 0.5

tool "acp_export_session"
echo
sleep 1.0

result "${SUCCESS}✓${RESET} Session exported

${DIM}Export contents:${RESET}
  • Full transcript (5,262 messages) ${DIM}→${RESET} ${ACCENT}transcript.jsonl${RESET}
  • Session metrics ${DIM}→${RESET} ${ACCENT}metrics.json${RESET}
  • Configuration ${DIM}→${RESET} ${ACCENT}session-config.yaml${RESET}
  • Tool call summary ${DIM}→${RESET} ${ACCENT}tool-calls.csv${RESET}
  • Repository analysis ${DIM}→${RESET} ${ACCENT}repos-analyzed.md${RESET}

${DIM}Export size:${RESET} ${ACCENT}12.3 MB${RESET}
${DIM}Saved to:${RESET} ${ACCENT}s3://acp-exports/session-1769218280/${RESET}

${DIM}Use this export to:${RESET}
  • Resume from checkpoint if session fails
  • Share research findings with team
  • Create session template for similar work"

sleep 3.0
