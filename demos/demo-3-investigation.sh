#!/bin/bash
# Demo 3: Session Investigation
# Based on: ses_41f10c121ffeAS9N3wT0X8D5BO.jsonl (get_events usage)
# Tools: list_sessions, get_events (2 tools)

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

user "what sessions are running?"

sleep 0.5

tool "acp_list_sessions"
echo
sleep 1.0

result "You have ${ACCENT}3 running${RESET} sessions:

  ${ACCENT}session-1768856372${RESET} ${DIM}→ ${SUCCESS}TRIAGE ODH DASHBOARD${RESET}
  ${ACCENT}agentic-session-1768140089${RESET} ${DIM}→ Platform Repository Setup${RESET}
  ${ACCENT}agentic-session-1767732662${RESET} ${DIM}→ PRD-RFE workflow guide${RESET}"

user "what is the triage session working on?"

sleep 0.5

tool "acp_get_events"
echo
sleep 1.0

result "The ${ACCENT}TRIAGE ODH DASHBOARD${RESET} session is:

  ${SUCCESS}✓${RESET} Analyzing ODH dashboard issues
  ${SUCCESS}✓${RESET} Running triage workflow from ootb-ambient-workflows
  ${SUCCESS}✓${RESET} Repository: https://github.com/opendatahub-io/odh-dashboard

  Last activity: ${ACCENT}12 minutes ago${RESET}"

sleep 3.0
