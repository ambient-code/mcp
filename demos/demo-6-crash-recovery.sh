#!/bin/bash
# Demo 6: Session Recovery After Crash - THE KILLER DEMO
# Based on: ses_474c8f806ffeEXpdztsMUN7mc6.jsonl (295 messages)
# Shows: acp_get_session_transcript, acp_restart_session, acp_clone_session, bulk operations

# Claude Code color scheme
USER='\033[0;36m'      # Cyan for user messages
ASSISTANT='\033[0;37m' # White for assistant
TOOL='\033[2;37m'
ACCENT='\033[0;36m'
ERROR='\033[0;31m'
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

user "Our session crashed. It was analyzing 13 features across agentready and reference repos."

assistant "Let me find and recover the crashed session."
echo

tool "mcp__acp__acp_list_sessions(status=\"failed\")"
echo

result "Found crashed session:
  ${ERROR}✗${RESET} ${ACCENT}session-1769142790${RESET} - Status: ${ERROR}Failed${RESET}
    Display name: ${DIM}Feature comparison: agentready vs reference${RESET}
    Crashed at: ${DIM}2026-01-28 14:23:41${RESET}
    Progress: ${DIM}6/13 features analyzed${RESET}"

user "Recover the context from that session"

assistant "Loading session transcript to extract context..."
echo

tool "mcp__acp__acp_get_session_transcript(session=\"session-1769142790\")"
echo

result "Transcript recovered (295 messages)

${DIM}Original task:${RESET}
  \"Pull useful stuff out of agentready repo and integrate into reference\"

${DIM}Progress before crash:${RESET}
  ✓ Features analyzed: Harbor, Renovate, Dependabot, Code reviews, CI/CD, PR automation
  ✗ Pending: 7 more features across 2 repos

${DIM}Context extracted:${RESET}
  • 13 features total to compare
  • 2 repos: agentready + reference
  • Multi-agent review needed (@code-architect, @code-simplifier)"

user "Clone the session and use bulk operations to finish the remaining 7 features in parallel"

assistant "Creating parallel analysis sessions for remaining features..."
echo

tool "mcp__acp__acp_clone_session(source=\"session-1769142790\", new_display_name=\"Feature comparison (resumed)\")"
echo

result "✓ Cloned to ${ACCENT}session-1769156892${RESET}"
echo

assistant "Spawning 7 parallel sessions for remaining features..."
echo

tool "mcp__acp__acp_bulk_create_sessions(count=7, template=\"feature-analysis\")"
echo

result "✓ Created 7 parallel sessions:

  ${ACCENT}session-1769156901${RESET} ${DIM}→ Analyzing: GitHub Actions workflows${RESET}
  ${ACCENT}session-1769156902${RESET} ${DIM}→ Analyzing: Issue templates${RESET}
  ${ACCENT}session-1769156903${RESET} ${DIM}→ Analyzing: Documentation patterns${RESET}
  ${ACCENT}session-1769156904${RESET} ${DIM}→ Analyzing: Security scanning${RESET}
  ${ACCENT}session-1769156905${RESET} ${DIM}→ Analyzing: Code quality gates${RESET}
  ${ACCENT}session-1769156906${RESET} ${DIM}→ Analyzing: Release automation${RESET}
  ${ACCENT}session-1769156907${RESET} ${DIM}→ Analyzing: Monitoring setup${RESET}

All sessions running in parallel..."

user "Monitor progress across all sessions"

tool "mcp__acp__acp_get_session_metrics(sessions=[\"session-1769156901\"...\"session-1769156907\"])"
echo

result "Parallel execution status:

  ${DIM}Average completion:${RESET} 73%
  ${DIM}Estimated time remaining:${RESET} ${ACCENT}8 minutes${RESET}
  ${DIM}Time saved vs sequential:${RESET} ${ACCENT}~42 minutes (72% reduction)${RESET}

  ${DIM}6/7 sessions completed${RESET}
  ${DIM}1/7 still running (Documentation patterns)${RESET}"

user "Stop all sessions when done"

assistant "Waiting for final session... done. Cleaning up."
echo

tool "mcp__acp__acp_bulk_stop_sessions(sessions=[\"session-1769156901\"...\"session-1769156907\"])"
echo

result "✓ Stopped 7 sessions
✓ Results aggregated
✓ Crash recovery complete

${DIM}Total analysis: 13 features across 2 repos in 50 minutes${RESET}
${DIM}(Would have taken 3 hours sequentially)${RESET}"

sleep 2
