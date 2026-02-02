#!/bin/bash
# Demo 5: Session Template - Integration Workflow
# Based on: ses_46c071cf8ffemzlB5HiRGRqYPy.jsonl (391 messages)
# Shows: acp_create_session_from_template, acp_list_workflows

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

user "I need to integrate OpenCode CLI with the Ambient Code Platform. Can you help?"

assistant "Let me check available session templates for integration workflows."
echo
sleep 0.5

tool "acp_list_workflows"
echo
sleep 1.0

result "Available workflow templates:
  ${ACCENT}triage${RESET}       - Bug investigation and root cause analysis
  ${ACCENT}bugfix${RESET}       - Targeted bug fixes with tests
  ${ACCENT}feature${RESET}      - Feature development workflow
  ${ACCENT}integration${RESET}  - Multi-repo API integration
  ${ACCENT}exploration${RESET}  - Codebase exploration and research"

user "Perfect! Use the integration template."

assistant "Creating session from integration template..."
echo
sleep 0.5

tool "acp_create_session_from_template"
echo
sleep 1.0

result "${SUCCESS}✓${RESET} Session ${ACCENT}agentic-session-1768140089${RESET} created

Pre-configured environment:
  ${DIM}• Repositories:${RESET} ambient-code/platform, jeremyeder/mcp
  ${DIM}• Kubernetes context:${RESET} vteam-stage
  ${DIM}• API docs loaded:${RESET} platform REST API reference
  ${DIM}• Workflow phases:${RESET} API review → design → implement → test

${DIM}Time saved with template: ~45 minutes of manual setup${RESET}"

sleep 3.0
