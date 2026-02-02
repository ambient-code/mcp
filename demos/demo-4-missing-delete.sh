#!/bin/bash
# Demo 4: The Missing Delete Tool - THE TRANSCRIPT THAT LED TO FEATURE REQUEST
# Based on: ses_3f786ee8cffe64kXQITAC75943.jsonl
# Shows: Real pain point where user had to use raw `oc delete`
# Tools: list_sessions, [bash fallback shows gap] (1 tool + problem demonstration)
# Impact: This exact conversation led to the 14-tool feature request document

# Claude Code color scheme
USER='\033[0;36m'      # Cyan for user messages
ASSISTANT='\033[0;37m' # White for assistant
TOOL='\033[2;37m'
ACCENT='\033[0;36m'
SUCCESS='\033[0;32m'
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

user "show me stopped sessions older than 7 days"

sleep 0.5

tool "acp_list_sessions"
echo
sleep 1.0

result "Found ${ACCENT}4 stopped sessions${RESET}:

  ${ACCENT}session-1769449187${RESET} ${DIM}→ stopped 9 days ago${RESET}
  ${ACCENT}session-1769278378${RESET} ${DIM}→ stopped 8 days ago${RESET}
  ${ACCENT}session-1769235378${RESET} ${DIM}→ stopped 11 days ago${RESET}
  ${ACCENT}agentic-session-1763524333${RESET} ${DIM}→ stopped 62 days ago${RESET}"

# THE MOMENT OF TRUTH - User wants to delete but tool doesn't exist
user "delete these sessions: session-1769449187 session-1769278378 session-1769235378 agentic-session-1763524333"

assistant "I'll delete those sessions..."
echo
sleep 0.5

tool "bash: oc delete agenticsession"
echo
sleep 1.0

result "${ERROR}⚠${RESET} Falling back to ${ACCENT}oc delete${RESET} command
(No ${ACCENT}acp_delete_session${RESET} tool available)

${SUCCESS}✓${RESET} Deleted 4 sessions via kubectl"

# THE REALIZATION
user "why didn't you use the mcp to delete?"

assistant "There is ${ERROR}no acp_delete_session tool${RESET} available in the MCP server.

I had to fall back to raw ${ACCENT}oc delete${RESET} commands.

${ERROR}This is a gap${RESET} - the MCP should support session deletion."

sleep 3.0
