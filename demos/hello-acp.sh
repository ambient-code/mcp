#!/bin/bash
# Hello ACP — First Session via acp_create_session
# Demonstrates creating an AgenticSession with a custom prompt via MCP
# Runtime: ~45 seconds

source ~/.claude/skills/asciinema/templates/claude-code-demo.sh

# === Step 1: Dry Run ===
turn "Create a hello-world session on ACP with dry_run=true" \
     "mcp__acp__acp_create_session" \
     "${SUCCESS}✓${NC} DRY RUN MODE - No changes made

Would create session with custom prompt

Manifest:
  apiVersion: ${CODE}vteam.ambient-code/v1alpha1${NC}
  kind: ${CODE}AgenticSession${NC}
  metadata:
    generateName: ${CODE}compiled-${NC}
    namespace: ${CODE}jeder-workspace${NC}
  spec:
    initialPrompt: ${CODE}\"Write a Python script that prints HELLO_ACP_SUCCESS, then run it.\"${NC}
    interactive: ${CODE}false${NC}
    llmConfig:
      model: ${CODE}claude-sonnet-4${NC}
    timeout: ${CODE}300${NC}
    displayName: ${CODE}hello-acp-test${NC}"

sleep 2.0

# === Step 2: Create for Real ===
turn "Now create it for real — remove dry_run" \
     "mcp__acp__acp_create_session" \
     "${SUCCESS}✓${NC} Session created: ${CODE}compiled-lp4cr${NC}
- Project: ${CODE}jeder-workspace${NC}
- Prompt: ${CODE}Write a Python script that prints HELLO_ACP_SUCCESS...${NC}

Check status:
  ${CODE}acp_list_sessions(project=\"jeder-workspace\")${NC}
  ${CODE}acp_get_session_logs(project=\"jeder-workspace\", session=\"compiled-lp4cr\")${NC}"

sleep 2.0

# === Step 3: Poll Status ===
turn "Check the session status" \
     "mcp__acp__acp_list_sessions" \
     "${SUCCESS}✓${NC} Found ${CODE}1${NC} matching session:

${CODE}compiled-lp4cr${NC}     hello-acp-test      ${CODE}Running${NC}    12s ago

stream:Session is running — Claude is processing the prompt..."

sleep 2.5

# === Step 4: Check Logs ===
turn "Check the runner logs for our marker" \
     "mcp__acp__acp_get_session_logs" \
     "${SUCCESS}✓${NC} Logs from ${CODE}compiled-lp4cr${NC} (ambient-code-runner):

${TOOL}INFO:adapter:[ClaudeSDKClient Message #51]:${NC}
  ToolResultBlock: ${CODE}HELLO_ACP_SUCCESS${NC}

${TOOL}INFO:adapter:[ClaudeSDKClient Message #62]:${NC}
  AssistantMessage: ${CODE}Done. The script was created and executed
  successfully, printing HELLO_ACP_SUCCESS.${NC}

${TOOL}INFO:adapter:[ClaudeSDKClient Message #66]:${NC}
  ResultMessage: subtype=${CODE}success${NC} num_turns=${CODE}3${NC}
  total_cost_usd=${CODE}0.36${NC}"

sleep 2.5

# === Step 5: Cleanup ===
turn "Delete the session — test passed, clean up" \
     "mcp__acp__acp_delete_session" \
     "${SUCCESS}✓${NC} Deleted session ${CODE}compiled-lp4cr${NC} from project ${CODE}jeder-workspace${NC}"

sleep 2.0

# === Step 6: Run the Pytest ===
turn "Now run the automated integration test" \
     "Bash" \
     "stream:\$ pytest tests/integration/test_hello_acp.py -m integration -v

${CODE}tests/integration/test_hello_acp.py::test_hello_acp${NC} ${SUCCESS}PASSED${NC}          [100%]

${SUCCESS}======================== 1 passed in 21.90s =========================${NC}

stream:Full pipeline verified:
stream:  MCP tool → K8s CR → Operator → Runner Pod → Claude → Marker in logs → Cleanup"

sleep 2.0

print "\n${SUCCESS}═══════════════════════════════════════════════════════${NC}"
print "${SUCCESS}  Hello ACP — Demo Complete${NC}"
print "${SUCCESS}═══════════════════════════════════════════════════════${NC}\n"
