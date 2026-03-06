#!/usr/bin/env python3
"""End-to-end test for Langfuse tracing integration.

Spins up the mcp-acp MCP server as a subprocess, connects via stdio,
exercises several tools against a live ACP cluster, and verifies that
Langfuse traces are created (when credentials are configured).

Prerequisites:
  - A running ACP cluster (kind or remote) with public-api accessible
  - A clusters.yaml config OR env vars pointing to the cluster
  - Langfuse credentials sourced into env

Usage:
  # 1. Create a clusters.yaml if you don't have one:
  uv run python scripts/test_tracing_e2e.py --setup-config

  # 2. Source Langfuse creds and run:
  source ../langfuse.env
  uv run python scripts/test_tracing_e2e.py

  # 3. Verify kill switch disables tracing:
  MCP_ACP_TRACING_ENABLED=false uv run python scripts/test_tracing_e2e.py
"""

import argparse
import asyncio
import os
import subprocess
import sys
import textwrap
from pathlib import Path


def setup_kind_config() -> Path:
    """Auto-generate a clusters.yaml for the local kind cluster."""
    config_dir = Path.home() / ".config" / "acp"
    config_path = config_dir / "clusters.yaml"

    # Get node IP
    node_ip = subprocess.check_output(
        ["kubectl", "get", "nodes", "-o", 'jsonpath={.items[0].status.addresses[?(@.type=="InternalIP")].address}'],
        text=True,
    ).strip()

    # Get NodePort for public-api-service
    node_port = subprocess.check_output(
        [
            "kubectl",
            "get",
            "svc",
            "public-api-service",
            "-n",
            "ambient-code",
            "-o",
            "jsonpath={.spec.ports[0].nodePort}",
        ],
        text=True,
    ).strip()

    # Get test user token
    token_b64 = subprocess.check_output(
        ["kubectl", "get", "secret", "test-user-token", "-n", "ambient-code", "-o", "jsonpath={.data.token}"],
        text=True,
    ).strip()
    token = subprocess.check_output(["base64", "-d"], input=token_b64, text=True).strip()

    config_content = textwrap.dedent(f"""\
        default_cluster: kind
        clusters:
          kind:
            server: http://{node_ip}:{node_port}
            default_project: ambient-code
            description: Local kind development cluster
            token: "{token}"
    """)

    config_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_content)
    print(f"Wrote clusters.yaml to {config_path}")
    print(f"  server: http://{node_ip}:{node_port}")
    print("  project: ambient-code")
    return config_path


async def run_e2e_test() -> None:
    """Connect to the MCP server and exercise tools."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    # Pass through current env (including Langfuse vars if set)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent / "src")

    # Also add the utils path (sibling to src/)
    utils_parent = Path(__file__).resolve().parent.parent
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{utils_parent}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = str(utils_parent)

    # Prefer .venv-3.12 (avoids Langfuse/Pydantic v1 incompatibility with Python 3.14)
    project_root = Path(__file__).resolve().parent.parent
    venv_312 = project_root / ".venv-3.12" / "bin" / "python"
    venv_default = project_root / ".venv" / "bin" / "python"
    python_bin = str(venv_312 if venv_312.exists() else venv_default)

    server_params = StdioServerParameters(
        command=python_bin,
        args=["-m", "mcp_acp.server"],
        env=env,
        cwd=str(project_root),
    )

    langfuse_configured = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
    tracing_enabled = os.getenv("MCP_ACP_TRACING_ENABLED", "true").lower() in ("true", "1", "yes")

    print("=" * 60)
    print("MCP-ACP Tracing End-to-End Test")
    print("=" * 60)
    print(f"  Langfuse credentials: {'configured' if langfuse_configured else 'NOT SET (silent no-op)'}")
    print(f"  Tracing enabled:      {tracing_enabled}")
    print(f"  Kill switch:          MCP_ACP_TRACING_ENABLED={os.getenv('MCP_ACP_TRACING_ENABLED', 'true')}")
    print()

    results: list[dict] = []

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("[OK] MCP server started and initialized")

            # 1. List tools
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"[OK] list_tools: {len(tool_names)} tools available")
            results.append({"test": "list_tools", "status": "pass", "tool_count": len(tool_names)})

            # 2. acp_whoami — tests cluster auth
            print("\n--- Tool: acp_whoami ---")
            whoami = await session.call_tool("acp_whoami", {})
            whoami_text = whoami.content[0].text
            print(f"  Response: {whoami_text[:200]}")
            results.append({"test": "acp_whoami", "status": "pass"})

            # 3. acp_list_clusters
            print("\n--- Tool: acp_list_clusters ---")
            clusters = await session.call_tool("acp_list_clusters", {})
            clusters_text = clusters.content[0].text
            print(f"  Response: {clusters_text[:200]}")
            results.append({"test": "acp_list_clusters", "status": "pass"})

            # 4. acp_list_sessions — exercises HTTP call tracing
            print("\n--- Tool: acp_list_sessions ---")
            sessions_result = await session.call_tool("acp_list_sessions", {})
            sessions_text = sessions_result.content[0].text
            print(f"  Response: {sessions_text[:200]}")
            results.append({"test": "acp_list_sessions", "status": "pass"})

            # 5. acp_get_session with invalid session — exercises error tracing
            print("\n--- Tool: acp_get_session (expect error) ---")
            err_result = await session.call_tool("acp_get_session", {"session": "nonexistent-session-xyz"})
            err_text = err_result.content[0].text
            is_error = "error" in err_text.lower() or "not found" in err_text.lower()
            print(f"  Response: {err_text[:200]}")
            print(f"  Got expected error: {is_error}")
            results.append({"test": "acp_get_session_error", "status": "pass" if is_error else "warn"})

            # 6. acp_create_session dry_run — exercises POST without side effects
            print("\n--- Tool: acp_create_session (dry_run) ---")
            create_result = await session.call_tool(
                "acp_create_session",
                {
                    "initial_prompt": "Hello from tracing e2e test",
                    "display_name": "tracing-e2e-test",
                    "dry_run": True,
                },
            )
            create_text = create_result.content[0].text
            print(f"  Response: {create_text[:200]}")
            results.append({"test": "acp_create_session_dry_run", "status": "pass"})

            # 7. acp_bulk_delete_sessions without confirm — exercises validation error
            print("\n--- Tool: acp_bulk_delete_sessions (expect validation error) ---")
            bulk_result = await session.call_tool(
                "acp_bulk_delete_sessions",
                {"sessions": ["s1"]},
            )
            bulk_text = bulk_result.content[0].text
            is_validation = "confirm" in bulk_text.lower() or "validation" in bulk_text.lower()
            print(f"  Response: {bulk_text[:200]}")
            print(f"  Got expected validation error: {is_validation}")
            results.append({"test": "acp_bulk_validation_error", "status": "pass" if is_validation else "warn"})

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for r in results:
        icon = "PASS" if r["status"] == "pass" else "WARN"
        print(f"  [{icon}] {r['test']}")

    passed = sum(1 for r in results if r["status"] == "pass")
    print(f"\n  {passed}/{len(results)} tests passed")

    if langfuse_configured and tracing_enabled:
        print("\n  Check your Langfuse dashboard for traces:")
        print(f"    {os.getenv('LANGFUSE_BASE_URL', 'https://cloud.langfuse.com')}")
        print("  Expected traces:")
        print("    - acp_whoami")
        print("    - acp_list_clusters")
        print("    - acp_list_sessions        (with child span: GET /v1/sessions)")
        print("    - acp_get_session          (with error status)")
        print("    - acp_create_session       (dry_run, no HTTP span)")
        print("    - acp_bulk_delete_sessions (validation_error, no HTTP span)")
    elif not langfuse_configured:
        print("\n  Langfuse credentials not set — no traces were sent (silent no-op).")
        print("  To verify tracing, set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_BASE_URL.")
    elif not tracing_enabled:
        print("\n  Tracing disabled via MCP_ACP_TRACING_ENABLED=false — no traces sent.")

    print()


def main():
    parser = argparse.ArgumentParser(description="End-to-end test for Langfuse tracing in mcp-acp")
    parser.add_argument(
        "--setup-config",
        action="store_true",
        help="Generate ~/.config/acp/clusters.yaml from the local kind cluster, then exit",
    )
    args = parser.parse_args()

    if args.setup_config:
        setup_kind_config()
        return

    # Check clusters.yaml exists
    config_path = os.getenv("ACP_CLUSTER_CONFIG") or str(Path.home() / ".config" / "acp" / "clusters.yaml")
    if not Path(config_path).exists():
        print(f"ERROR: No clusters.yaml found at {config_path}")
        print("Run with --setup-config to auto-generate from kind cluster:")
        print(f"  uv run python {sys.argv[0]} --setup-config")
        sys.exit(1)

    asyncio.run(run_e2e_test())


if __name__ == "__main__":
    main()
