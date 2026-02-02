#!/bin/bash
# Demo 8: Bulk Prompt Comparison Across AI Providers
# Use case: Brainstorming, security scanning, creative generation
# Shows: acp_bulk_create_sessions, acp_bulk_send_message, acp_bulk_get_session_metrics, acp_bulk_stop_sessions

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
    sleep 1.5
}

assistant() {
    stream "$1" 0.015
    sleep 1.0
}

tool() {
    print "    ${TOOL}Using $1${RESET}"
    sleep 0.8
}

result() {
    print "    ${ASSISTANT}$1${RESET}"
    echo
    sleep 1.5
}

clear
echo
echo

# === DEMO START ===

user "I need to brainstorm security risks for our new API. Compare responses from Google, Anthropic, and OpenAI."

assistant "I'll use bulk operations to create 3 sessions and query all providers simultaneously."
echo
sleep 0.5

tool "acp_bulk_create_sessions"
echo
sleep 1.0

result "Bulk creating sessions:
  Request: 3 sessions
  Providers: [google, anthropic, openai]
  Workflow: brainstorming

✓ Created 3 sessions:
  ${ACCENT}session-1769701001${RESET} ${DIM}→ Google Gemini 3.0${RESET}
  ${ACCENT}session-1769701002${RESET} ${DIM}→ Anthropic Claude 3.5${RESET}
  ${ACCENT}session-1769701003${RESET} ${DIM}→ OpenAI GPT-4${RESET}"

user "Send this to all 3: 'What are the top 5 security risks for a REST API that handles payment data?'"

assistant "Using bulk send to broadcast prompt to all providers..."
echo
sleep 0.5

tool "acp_bulk_send_message"
echo
sleep 1.0

result "Bulk message sent:
  Sessions: 3
  Message: \"What are the top 5 security risks...\"

✓ Sent to all providers simultaneously
${DIM}Waiting for responses...${RESET}"

sleep 2.5

assistant "Responses received. Aggregating results..."
echo
sleep 0.5

tool "acp_bulk_get_responses"
echo
sleep 1.0

result "${SUCCESS}Response 1 - Google Gemini 3.0:${RESET}
  1. SQL Injection attacks
  2. Insufficient authentication/authorization
  3. Man-in-the-middle attacks (no TLS)
  4. Sensitive data exposure in logs
  5. Rate limiting bypass
  ${DIM}Focus: Infrastructure security${RESET}

${SUCCESS}Response 2 - Anthropic Claude 3.5:${RESET}
  1. PCI-DSS compliance violations
  2. Insecure direct object references
  3. JWT token vulnerabilities
  4. API key exposure in client code
  5. Lack of input validation
  ${DIM}Focus: Compliance & code security${RESET}

${SUCCESS}Response 3 - OpenAI GPT-4:${RESET}
  1. Broken authentication mechanisms
  2. Mass assignment vulnerabilities
  3. CORS misconfiguration
  4. Insufficient transport layer security
  5. Business logic flaws in payment flow
  ${DIM}Focus: Application logic${RESET}"

sleep 2.0

user "Show me metrics for all 3"

sleep 0.5

tool "acp_bulk_get_session_metrics"
echo
sleep 1.0

result "Bulk metrics across 3 sessions:

  ${DIM}Provider        Time    Tokens   Cost      Value/Token${RESET}
  ${DIM}────────────────────────────────────────────────────────${RESET}
  Google Gemini    2.3s    487     \$0.0002  ${ACCENT}★ Best${RESET}
  Anthropic        3.1s    612     \$0.018   Good
  OpenAI GPT-4     2.8s    534     \$0.032   Good

${DIM}Parallel time: 3.1s${RESET}
${DIM}(Sequential would be: 8.2s - 67% slower)${RESET}

${SUCCESS}★ Google Gemini${RESET} fastest, fewest tokens, lowest cost (\$0.40/1M tokens)"

sleep 2.0

user "Stop all sessions"

sleep 0.5

tool "acp_bulk_stop_sessions"
echo
sleep 1.0

result "Bulk stop:
  Sessions: 3

✓ Stopped all comparison sessions
✓ Resources released

${DIM}Summary:${RESET}
  • 3 AI providers queried in parallel
  • Total time: 8 seconds
  • 67% faster than sequential
  • Got 3 unique perspectives on API security"

sleep 3.0
