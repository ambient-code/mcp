#!/bin/bash
# Demo 2: Session Creation & Lifecycle
# Based on: ses_46ba07032ffemtVlajQyy4ODNr.jsonl (full create → get → stop)
# Tools: create_session, get_session, stop_session (3 tools)

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

user "create a new session called COP-123"

sleep 0.5

tool "acp_create_session"
echo
sleep 1.0

result "${SUCCESS}✓${RESET} Created session ${ACCENT}session-1769003871${RESET}
  Display name: ${ACCENT}COP-123${RESET}
  Status: ${ACCENT}Creating${RESET}..."

user "is it running yet?"

sleep 0.5

tool "acp_get_session"
echo
sleep 1.0

result "${SUCCESS}✓${RESET} Session is now ${ACCENT}Running${RESET}
  Ready to receive messages"

user "ok stop that session"

sleep 0.5

tool "acp_stop_session"
echo
sleep 1.0

result "${SUCCESS}✓${RESET} Session ${ACCENT}COP-123${RESET} stopped
  Resources released"

sleep 3.0
