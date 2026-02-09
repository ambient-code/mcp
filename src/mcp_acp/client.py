"""ACP client wrapper for OpenShift CLI operations."""

import asyncio
import json
import re
import secrets
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from mcp_acp.settings import Settings, load_clusters_config, load_settings
from utils.pylogger import get_python_logger

# Initialize structured logger
logger = get_python_logger()


class ACPClient:
    """Client for interacting with ACP via OpenShift CLI.

    Attributes:
        settings: Global settings instance
        clusters_config: Cluster configuration instance
        config: Raw cluster configuration (for backward compatibility)
    """

    # Security constants
    ALLOWED_RESOURCE_TYPES = {"agenticsession", "pods", "event"}  # Whitelist
    MAX_BULK_ITEMS = 3  # Maximum items allowed in bulk operations
    LABEL_PREFIX = "acp.ambient-code.ai/label-"  # Label prefix for ACP labels
    MAX_COMMAND_TIMEOUT = 120  # Maximum command timeout in seconds
    MAX_LOG_LINES = 10000  # Maximum log lines to retrieve

    def __init__(self, config_path: str | None = None, settings: Settings | None = None):
        """Initialize ACP client.

        Args:
            config_path: Path to clusters.yaml config file (deprecated, use settings)
            settings: Settings instance. If not provided, loads default settings.
        """
        # Load or use provided settings
        self.settings = settings or load_settings()

        # Override config path if provided (for backward compatibility)
        if config_path:
            self.settings.config_path = Path(config_path)

        # Load cluster configuration
        try:
            self.clusters_config = load_clusters_config(self.settings)
        except Exception as e:
            logger.error("cluster_config_load_failed", error=str(e))
            raise

        # Backward compatibility: expose raw config
        self.config = {
            "clusters": {
                name: {
                    "server": cluster.server,
                    "default_project": cluster.default_project,
                    "description": cluster.description,
                }
                for name, cluster in self.clusters_config.clusters.items()
            },
            "default_cluster": self.clusters_config.default_cluster,
        }
        self.config_path = str(self.settings.config_path)

        logger.info(
            "acp_client_initialized",
            clusters=list(self.clusters_config.clusters.keys()),
            default_cluster=self.clusters_config.default_cluster,
        )

    # Note: _load_config and _validate_config removed - now handled by Pydantic settings

    def _validate_input(self, value: str, field_name: str, max_length: int = 253) -> None:
        """Validate input to prevent injection attacks.

        Args:
            value: Value to validate
            field_name: Field name for error messages
            max_length: Maximum allowed length

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        if len(value) > max_length:
            raise ValueError(f"{field_name} exceeds maximum length of {max_length}")
        # Validate Kubernetes naming conventions (DNS-1123 subdomain)
        if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", value):
            raise ValueError(f"{field_name} contains invalid characters. Must match: ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")

    def _validate_bulk_operation(self, items: list[str], operation_name: str) -> None:
        """Enforce 3-item limit for safety on bulk operations.

        Args:
            items: List of items to operate on
            operation_name: Operation name for error message

        Raises:
            ValueError: If item count exceeds limit
        """
        if len(items) > self.MAX_BULK_ITEMS:
            raise ValueError(
                f"Bulk {operation_name} limited to {self.MAX_BULK_ITEMS} items for safety. "
                f"You requested {len(items)} items. Split into multiple operations."
            )

    async def _run_oc_command(
        self,
        args: list[str],
        capture_output: bool = True,
        parse_json: bool = False,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess | dict[str, Any]:
        """Run an oc command asynchronously with security controls.

        Args:
            args: Command arguments (will be validated)
            capture_output: Whether to capture stdout/stderr
            parse_json: If True, parse stdout as JSON and return dict
            timeout: Command timeout in seconds (default: MAX_COMMAND_TIMEOUT)

        Returns:
            CompletedProcess result or parsed JSON dict

        Raises:
            asyncio.TimeoutError: If command exceeds timeout
            ValueError: If arguments contain suspicious content
        """
        # Security: Validate arguments don't contain shell metacharacters
        for arg in args:
            if not isinstance(arg, str):
                raise ValueError(f"All arguments must be strings, got {type(arg)}")
            # Detect potential command injection
            if any(char in arg for char in [";", "|", "&", "$", "`", "\n", "\r"]):
                raise ValueError(f"Argument contains suspicious characters: {arg}")

        cmd = ["oc"] + args
        effective_timeout = timeout or self.MAX_COMMAND_TIMEOUT

        if capture_output:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    # Security: Prevent shell injection
                )
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=effective_timeout)
                result = subprocess.CompletedProcess(
                    args=cmd,
                    returncode=process.returncode or 0,
                    stdout=stdout,
                    stderr=stderr,
                )

                if parse_json and result.returncode == 0:
                    try:
                        return json.loads(result.stdout.decode())
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Failed to parse JSON response: {e}") from e

                return result
            except TimeoutError:
                # Kill the process if it times out
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                raise TimeoutError(f"Command timed out after {effective_timeout}s") from None
        else:
            # For non-captured output, use subprocess.run with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(subprocess.run, cmd, capture_output=False, timeout=effective_timeout),
                    timeout=effective_timeout + 5,  # Extra buffer
                )
                return result
            except subprocess.TimeoutExpired:
                raise TimeoutError(f"Command timed out after {effective_timeout}s") from None

    async def _get_resource_json(self, resource_type: str, name: str, namespace: str) -> dict[str, Any]:
        """Get a Kubernetes resource as JSON dict.

        Args:
            resource_type: Resource type (e.g., 'agenticsession')
            name: Resource name
            namespace: Namespace

        Returns:
            Resource as JSON dict

        Raises:
            ValueError: If inputs are invalid
            Exception: If resource not found or command fails
        """
        # Security: Validate inputs
        if resource_type not in self.ALLOWED_RESOURCE_TYPES:
            raise ValueError(f"Resource type '{resource_type}' not allowed")
        self._validate_input(name, "resource name")
        self._validate_input(namespace, "namespace")

        result = await self._run_oc_command(["get", resource_type, name, "-n", namespace, "-o", "json"])

        if result.returncode != 0:
            raise Exception(f"Failed to get {resource_type} '{name}': {result.stderr.decode()}")

        return json.loads(result.stdout.decode())

    async def _list_resources_json(
        self, resource_type: str, namespace: str, selector: str | None = None
    ) -> list[dict[str, Any]]:
        """List Kubernetes resources as JSON dicts.

        Args:
            resource_type: Resource type (e.g., 'agenticsession')
            namespace: Namespace
            selector: Optional label selector

        Returns:
            List of resources as JSON dicts

        Raises:
            ValueError: If inputs are invalid
            Exception: If command fails
        """
        # Security: Validate inputs
        if resource_type not in self.ALLOWED_RESOURCE_TYPES:
            raise ValueError(f"Resource type '{resource_type}' not allowed")
        self._validate_input(namespace, "namespace")
        if selector and not re.match(r"^[a-zA-Z0-9=,_.\-/]+$", selector):
            raise ValueError(f"Invalid label selector format: {selector}")

        args = ["get", resource_type, "-n", namespace, "-o", "json"]
        if selector:
            args.extend(["-l", selector])

        result = await self._run_oc_command(args)

        if result.returncode != 0:
            raise Exception(f"Failed to list {resource_type}: {result.stderr.decode()}")

        data = json.loads(result.stdout.decode())
        return data.get("items", [])

    async def _validate_session_for_dry_run(self, project: str, session: str, operation: str) -> dict[str, Any]:
        """Validate session exists for dry-run and return session info.

        Args:
            project: Project/namespace name
            session: Session name
            operation: Operation name for message (e.g., "delete", "restart")

        Returns:
            Dict with dry_run response including session_info if found
        """
        try:
            session_data = await self._get_resource_json("agenticsession", session, project)

            return {
                "dry_run": True,
                "success": True,
                "message": f"Would {operation} session '{session}' in project '{project}'",
                "session_info": {
                    "name": session_data.get("metadata", {}).get("name"),
                    "status": session_data.get("status", {}).get("phase"),
                    "created": session_data.get("metadata", {}).get("creationTimestamp"),
                    "stopped_at": session_data.get("status", {}).get("stoppedAt"),
                },
            }
        except Exception:
            return {
                "dry_run": True,
                "success": False,
                "message": f"Session '{session}' not found in project '{project}'",
            }

    async def _bulk_operation(
        self,
        project: str,
        sessions: list[str],
        operation_fn: Callable,
        success_key: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Generic bulk operation handler.

        Args:
            project: Project/namespace name
            sessions: List of session names
            operation_fn: Async function to call for each session
            success_key: Key name for successful operations in response
            dry_run: Preview mode

        Returns:
            Standardized bulk operation response
        """
        # Enforce 3-item limit
        self._validate_bulk_operation(sessions, success_key)

        success = []
        failed = []
        dry_run_info = {"would_execute": [], "skipped": []}

        for session in sessions:
            result = await operation_fn(project, session, dry_run=dry_run)

            if dry_run:
                if result.get("success", True):
                    dry_run_info["would_execute"].append(
                        {
                            "session": session,
                            "info": result.get("session_info"),
                        }
                    )
                else:
                    dry_run_info["skipped"].append(
                        {
                            "session": session,
                            "reason": result.get("message"),
                        }
                    )
            else:
                if result.get(success_key, result.get("success")):
                    success.append(session)
                else:
                    failed.append({"session": session, "error": result.get("message")})

        response = {success_key: success, "failed": failed}
        if dry_run:
            response["dry_run"] = True
            response["dry_run_info"] = dry_run_info

        return response

    async def label_resource(
        self,
        resource_type: str,
        name: str,
        project: str,
        labels: dict[str, str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Add/update labels on any resource (generic, works for sessions/workspaces/etc).

        Args:
            resource_type: Resource type (agenticsession, namespace, etc)
            name: Resource name
            project: Project/namespace name
            labels: Label key-value pairs (e.g., {'env': 'prod'})
            dry_run: Preview mode

        Returns:
            Dict with labeling status
        """
        # Validate resource type
        if resource_type not in self.ALLOWED_RESOURCE_TYPES:
            raise ValueError(f"Resource type '{resource_type}' not allowed")

        # Simple validation + prefix (let K8s do heavy lifting)
        k8s_labels = {}
        for key, value in labels.items():
            # Basic format check
            if not key.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"Invalid label key: {key}")
            if not value.replace("-", "").replace("_", "").replace(".", "").isalnum():
                raise ValueError(f"Invalid label value: {value}")
            if len(key) > 63 or len(value) > 63:
                raise ValueError("Label key/value must be ≤63 characters")

            # Add prefix
            k8s_labels[f"{self.LABEL_PREFIX}{key}"] = value

        if dry_run:
            return {
                "dry_run": True,
                "resource": name,
                "labels": labels,
                "message": f"Would label {resource_type} '{name}'",
            }

        # Apply with --overwrite (handles add & update)
        label_args = [f"{k}={v}" for k, v in k8s_labels.items()]
        result = await self._run_oc_command(["label", resource_type, name, "-n", project, "--overwrite"] + label_args)

        if result.returncode == 0:
            return {"labeled": True, "resource": name, "labels": labels}
        else:
            return {"labeled": False, "message": result.stderr.decode()}

    async def unlabel_resource(
        self,
        resource_type: str,
        name: str,
        project: str,
        label_keys: list[str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Remove specific labels from a resource.

        Args:
            resource_type: Resource type (agenticsession, namespace, etc)
            name: Resource name
            project: Project/namespace name
            label_keys: List of label keys to remove (without prefix)
            dry_run: Preview mode

        Returns:
            Dict with unlabeling status
        """
        # Validate resource type
        if resource_type not in self.ALLOWED_RESOURCE_TYPES:
            raise ValueError(f"Resource type '{resource_type}' not allowed")

        # Build prefixed keys
        prefixed_keys = [f"{self.LABEL_PREFIX}{key}" for key in label_keys]

        if dry_run:
            return {
                "dry_run": True,
                "resource": name,
                "label_keys": label_keys,
                "message": f"Would remove labels from {resource_type} '{name}'",
            }

        # Remove labels using oc label with '-' suffix
        label_args = [f"{k}-" for k in prefixed_keys]
        result = await self._run_oc_command(["label", resource_type, name, "-n", project] + label_args)

        if result.returncode == 0:
            return {"unlabeled": True, "resource": name, "removed_keys": label_keys}
        else:
            return {"unlabeled": False, "message": result.stderr.decode()}

    async def bulk_label_resources(
        self,
        resource_type: str,
        names: list[str],
        project: str,
        labels: dict[str, str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Label multiple resources with same labels (max 3).

        Args:
            resource_type: Resource type
            names: List of resource names
            project: Project/namespace name
            labels: Label key-value pairs
            dry_run: Preview mode

        Returns:
            Dict with bulk labeling results
        """
        # Enforce limit
        self._validate_bulk_operation(names, "label")

        success = []
        failed = []

        for name in names:
            result = await self.label_resource(resource_type, name, project, labels, dry_run)
            if result.get("labeled", result.get("success")):
                success.append(name)
            else:
                failed.append({"resource": name, "error": result.get("message")})

        return {
            "labeled": success,
            "failed": failed,
            "dry_run": dry_run,
        }

    async def bulk_unlabel_resources(
        self,
        resource_type: str,
        names: list[str],
        project: str,
        label_keys: list[str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Remove labels from multiple resources (max 3).

        Args:
            resource_type: Resource type
            names: List of resource names
            project: Project/namespace name
            label_keys: List of label keys to remove
            dry_run: Preview mode

        Returns:
            Dict with bulk unlabeling results
        """
        # Enforce limit
        self._validate_bulk_operation(names, "unlabel")

        success = []
        failed = []

        for name in names:
            result = await self.unlabel_resource(resource_type, name, project, label_keys, dry_run)
            if result.get("unlabeled", result.get("success")):
                success.append(name)
            else:
                failed.append({"resource": name, "error": result.get("message")})

        return {
            "unlabeled": success,
            "failed": failed,
            "dry_run": dry_run,
        }

    async def list_sessions(
        self,
        project: str,
        status: str | None = None,
        has_display_name: bool | None = None,
        older_than: str | None = None,
        sort_by: str | None = None,
        limit: int | None = None,
        label_selector: str | None = None,
    ) -> dict[str, Any]:
        """List sessions with enhanced filtering.

        Args:
            project: Project/namespace name
            status: Filter by status (running, stopped, creating, failed)
            has_display_name: Filter by display name presence
            older_than: Filter by age (e.g., "7d", "24h")
            sort_by: Sort field (created, stopped, name)
            limit: Maximum results
            label_selector: Kubernetes label selector (e.g., 'acp.ambient-code.ai/label-env=prod')

        Returns:
            Dict with sessions list and metadata
        """
        sessions = await self._list_resources_json("agenticsession", project, selector=label_selector)

        # Build filter predicates
        filters = []
        filters_applied = {}

        if status:
            filters.append(lambda s: s.get("status", {}).get("phase", "").lower() == status.lower())
            filters_applied["status"] = status

        if has_display_name is not None:
            filters.append(lambda s: bool(s.get("spec", {}).get("displayName")) == has_display_name)
            filters_applied["has_display_name"] = has_display_name

        if older_than:
            cutoff_time = self._parse_time_delta(older_than)
            filters.append(lambda s: self._is_older_than(s.get("metadata", {}).get("creationTimestamp"), cutoff_time))
            filters_applied["older_than"] = older_than

        # Single-pass filter
        filtered = [s for s in sessions if all(f(s) for f in filters)]

        # Sort
        if sort_by:
            filtered = self._sort_sessions(filtered, sort_by)
            filters_applied["sort_by"] = sort_by

        # Limit
        if limit and limit > 0:
            filtered = filtered[:limit]
            filters_applied["limit"] = limit

        return {
            "sessions": filtered,
            "total": len(filtered),
            "filters_applied": filters_applied,
        }

    async def list_sessions_by_user_labels(
        self,
        project: str,
        labels: dict[str, str],
        **kwargs,
    ) -> dict[str, Any]:
        """List sessions by user-friendly labels (convenience wrapper).

        Args:
            project: Project/namespace name
            labels: User-friendly label key-value pairs
            **kwargs: Additional arguments passed to list_sessions

        Returns:
            Dict with sessions list
        """
        # Build K8s label selector from user labels
        label_parts = [f"{self.LABEL_PREFIX}{k}={v}" for k, v in labels.items()]
        label_selector = ",".join(label_parts)

        return await self.list_sessions(project=project, label_selector=label_selector, **kwargs)

    def _sort_sessions(self, sessions: list[dict], sort_by: str) -> list[dict]:
        """Sort sessions by field.

        Args:
            sessions: List of session dicts
            sort_by: Sort field (created, stopped, name)

        Returns:
            Sorted list
        """
        sort_keys = {
            "created": lambda s: s.get("metadata", {}).get("creationTimestamp", ""),
            "stopped": lambda s: s.get("status", {}).get("stoppedAt", ""),
            "name": lambda s: s.get("metadata", {}).get("name", ""),
        }

        key_fn = sort_keys.get(sort_by)
        if key_fn:
            return sorted(sessions, key=key_fn, reverse=(sort_by != "name"))
        return sessions

    def _parse_time_delta(self, time_str: str) -> datetime:
        """Parse time delta string (e.g., '7d', '24h') to datetime.

        Args:
            time_str: Time delta string

        Returns:
            Datetime representing the cutoff time
        """
        match = re.match(r"(\d+)([dhm])", time_str.lower())
        if not match:
            raise ValueError(f"Invalid time format: {time_str}. Use format like '7d', '24h', '30m'")

        value, unit = int(match.group(1)), match.group(2)
        now = datetime.utcnow()

        if unit == "d":
            return now - timedelta(days=value)
        elif unit == "h":
            return now - timedelta(hours=value)
        elif unit == "m":
            return now - timedelta(minutes=value)

        raise ValueError(f"Unknown time unit: {unit}")

    def _is_older_than(self, timestamp_str: str | None, cutoff: datetime) -> bool:
        """Check if timestamp is older than cutoff.

        Args:
            timestamp_str: ISO format timestamp string
            cutoff: Cutoff datetime

        Returns:
            True if older than cutoff
        """
        if not timestamp_str:
            return False

        # Parse ISO format timestamp
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return timestamp.replace(tzinfo=None) < cutoff

    async def delete_session(self, project: str, session: str, dry_run: bool = False) -> dict[str, Any]:
        """Delete a session.

        Args:
            project: Project/namespace name
            session: Session name
            dry_run: Preview without deleting

        Returns:
            Dict with deletion status
        """
        if dry_run:
            return await self._validate_session_for_dry_run(project, session, "delete")

        result = await self._run_oc_command(["delete", "agenticsession", session, "-n", project])

        if result.returncode != 0:
            return {
                "deleted": False,
                "message": f"Failed to delete session: {result.stderr.decode()}",
            }

        return {
            "deleted": True,
            "message": f"Successfully deleted session '{session}' from project '{project}'",
        }

    async def restart_session(self, project: str, session: str, dry_run: bool = False) -> dict[str, Any]:
        """Restart a stopped session.

        Args:
            project: Project/namespace name
            session: Session name
            dry_run: Preview without restarting

        Returns:
            Dict with restart status
        """
        try:
            session_data = await self._get_resource_json("agenticsession", session, project)
            current_status = session_data.get("status", {}).get("phase", "unknown")

            if dry_run:
                return {
                    "status": current_status,
                    "dry_run": True,
                    "success": True,
                    "message": f"Would restart session '{session}' (current status: {current_status})",
                    "session_info": {
                        "name": session_data.get("metadata", {}).get("name"),
                        "current_status": current_status,
                        "stopped_at": session_data.get("status", {}).get("stoppedAt"),
                    },
                }

            # Restart by patching the stopped field to false
            patch = {"spec": {"stopped": False}}
            result = await self._run_oc_command(
                [
                    "patch",
                    "agenticsession",
                    session,
                    "-n",
                    project,
                    "--type=merge",
                    "-p",
                    json.dumps(patch),
                ]
            )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "message": f"Failed to restart session: {result.stderr.decode()}",
                }

            return {
                "status": "restarting",
                "message": f"Successfully restarted session '{session}' in project '{project}'",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def bulk_delete_sessions(self, project: str, sessions: list[str], dry_run: bool = False) -> dict[str, Any]:
        """Delete multiple sessions.

        Args:
            project: Project/namespace name
            sessions: List of session names
            dry_run: Preview without deleting

        Returns:
            Dict with deletion results
        """
        return await self._bulk_operation(project, sessions, self.delete_session, "deleted", dry_run)

    async def bulk_stop_sessions(self, project: str, sessions: list[str], dry_run: bool = False) -> dict[str, Any]:
        """Stop multiple running sessions.

        Args:
            project: Project/namespace name
            sessions: List of session names
            dry_run: Preview without stopping

        Returns:
            Dict with stop results
        """

        async def stop_session(project: str, session: str, dry_run: bool = False) -> dict[str, Any]:
            """Internal stop session helper."""
            try:
                session_data = await self._get_resource_json("agenticsession", session, project)
                current_status = session_data.get("status", {}).get("phase")

                if dry_run:
                    return {
                        "dry_run": True,
                        "success": current_status == "running",
                        "message": f"Session status: {current_status}",
                        "session_info": {
                            "name": session,
                            "status": current_status,
                        },
                    }

                # Stop the session
                patch = {"spec": {"stopped": True}}
                result = await self._run_oc_command(
                    [
                        "patch",
                        "agenticsession",
                        session,
                        "-n",
                        project,
                        "--type=merge",
                        "-p",
                        json.dumps(patch),
                    ]
                )

                if result.returncode == 0:
                    return {"stopped": True, "message": "Success"}
                else:
                    return {
                        "stopped": False,
                        "message": result.stderr.decode(),
                    }
            except Exception as e:
                return {"stopped": False, "success": False, "message": str(e)}

        return await self._bulk_operation(project, sessions, stop_session, "stopped", dry_run)

    async def bulk_restart_sessions(self, project: str, sessions: list[str], dry_run: bool = False) -> dict[str, Any]:
        """Restart multiple stopped sessions (max 3).

        Args:
            project: Project/namespace name
            sessions: List of session names
            dry_run: Preview mode

        Returns:
            Dict with restart results
        """
        # Enforce limit
        self._validate_bulk_operation(sessions, "restart")

        success = []
        failed = []

        for session in sessions:
            result = await self.restart_session(project, session, dry_run)
            if result.get("status") == "restarting" or result.get("success"):
                success.append(session)
            else:
                failed.append({"session": session, "error": result.get("message")})

        return {
            "restarted": success,
            "failed": failed,
            "dry_run": dry_run,
        }

    async def bulk_delete_sessions_by_label(
        self,
        project: str,
        labels: dict[str, str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Delete sessions matching label selector (max 3).

        Args:
            project: Project/namespace name
            labels: Label key-value pairs
            dry_run: Preview mode

        Returns:
            Dict with deletion results
        """
        # Get sessions by label
        result = await self.list_sessions_by_user_labels(project, labels)
        sessions = result.get("sessions", [])

        if not sessions:
            return {
                "deleted": [],
                "failed": [],
                "message": f"No sessions found with labels {labels}",
            }

        session_names = [s["metadata"]["name"] for s in sessions]

        # Early validation with helpful error
        if len(session_names) > self.MAX_BULK_ITEMS:
            raise ValueError(
                f"Label selector matches {len(session_names)} sessions. "
                f"Max {self.MAX_BULK_ITEMS} allowed. Refine your labels to be more specific."
            )

        # Enhanced dry-run output
        if dry_run:
            return {
                "dry_run": True,
                "matched_sessions": session_names,
                "matched_count": len(session_names),
                "label_selector": ",".join([f"{self.LABEL_PREFIX}{k}={v}" for k, v in labels.items()]),
                "message": f"Would delete {len(session_names)} sessions. Review matched_sessions before confirming.",
            }

        # Use existing bulk_delete_sessions
        return await self.bulk_delete_sessions(project, session_names, dry_run=dry_run)

    async def bulk_stop_sessions_by_label(
        self,
        project: str,
        labels: dict[str, str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Stop sessions matching label selector (max 3).

        Args:
            project: Project/namespace name
            labels: Label key-value pairs
            dry_run: Preview mode

        Returns:
            Dict with stop results
        """
        # Get sessions by label
        result = await self.list_sessions_by_user_labels(project, labels)
        sessions = result.get("sessions", [])

        if not sessions:
            return {
                "stopped": [],
                "failed": [],
                "message": f"No sessions found with labels {labels}",
            }

        session_names = [s["metadata"]["name"] for s in sessions]

        # Early validation with helpful error
        if len(session_names) > self.MAX_BULK_ITEMS:
            raise ValueError(
                f"Label selector matches {len(session_names)} sessions. "
                f"Max {self.MAX_BULK_ITEMS} allowed. Refine your labels to be more specific."
            )

        # Enhanced dry-run output
        if dry_run:
            return {
                "dry_run": True,
                "matched_sessions": session_names,
                "matched_count": len(session_names),
                "label_selector": ",".join([f"{self.LABEL_PREFIX}{k}={v}" for k, v in labels.items()]),
                "message": f"Would stop {len(session_names)} sessions. Review matched_sessions before confirming.",
            }

        # Use existing bulk_stop_sessions
        return await self.bulk_stop_sessions(project, session_names, dry_run=dry_run)

    async def bulk_restart_sessions_by_label(
        self,
        project: str,
        labels: dict[str, str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Restart sessions matching label selector (max 3).

        Args:
            project: Project/namespace name
            labels: Label key-value pairs
            dry_run: Preview mode

        Returns:
            Dict with restart results
        """
        # Get sessions by label
        result = await self.list_sessions_by_user_labels(project, labels)
        sessions = result.get("sessions", [])

        if not sessions:
            return {
                "restarted": [],
                "failed": [],
                "message": f"No sessions found with labels {labels}",
            }

        session_names = [s["metadata"]["name"] for s in sessions]

        # Early validation with helpful error
        if len(session_names) > self.MAX_BULK_ITEMS:
            raise ValueError(
                f"Label selector matches {len(session_names)} sessions. "
                f"Max {self.MAX_BULK_ITEMS} allowed. Refine your labels to be more specific."
            )

        # Enhanced dry-run output
        if dry_run:
            return {
                "dry_run": True,
                "matched_sessions": session_names,
                "matched_count": len(session_names),
                "label_selector": ",".join([f"{self.LABEL_PREFIX}{k}={v}" for k, v in labels.items()]),
                "message": f"Would restart {len(session_names)} sessions. Review matched_sessions before confirming.",
            }

        # Use existing bulk_restart_sessions
        return await self.bulk_restart_sessions(project, session_names, dry_run=dry_run)

    async def get_session_logs(
        self,
        project: str,
        session: str,
        container: str | None = None,
        tail_lines: int | None = None,
    ) -> dict[str, Any]:
        """Get logs for a session.

        Args:
            project: Project/namespace name
            session: Session name
            container: Container name (optional)
            tail_lines: Number of lines to retrieve

        Returns:
            Dict with logs
        """
        # Security: Validate inputs
        try:
            self._validate_input(project, "project")
            self._validate_input(session, "session")
            if container:
                # Container names have slightly different naming rules
                if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", container):
                    raise ValueError(f"Invalid container name: {container}")
            # Security: Limit tail_lines to prevent DoS
            if tail_lines and (tail_lines < 1 or tail_lines > self.MAX_LOG_LINES):
                raise ValueError(f"tail_lines must be between 1 and {self.MAX_LOG_LINES}")

            # Find the pod for this session
            pods = await self._list_resources_json("pods", project, selector=f"agenticsession={session}")

            if not pods:
                return {"logs": "", "error": f"No pods found for session '{session}'"}

            pod_name = pods[0].get("metadata", {}).get("name")

            # Build logs command
            logs_args = ["logs", pod_name, "-n", project]
            if container:
                logs_args.extend(["-c", container])
            if tail_lines:
                logs_args.extend(["--tail", str(tail_lines)])
            else:
                # Default limit to prevent memory exhaustion
                logs_args.extend(["--tail", str(1000)])

            result = await self._run_oc_command(logs_args)

            if result.returncode != 0:
                return {
                    "logs": "",
                    "error": f"Failed to retrieve logs: {result.stderr.decode()}",
                }

            return {
                "logs": result.stdout.decode(),
                "container": container or "default",
                "lines": len(result.stdout.decode().split("\n")),
            }
        except ValueError as e:
            return {"logs": "", "error": str(e)}
        except Exception as e:
            return {"logs": "", "error": f"Unexpected error: {str(e)}"}

    def list_clusters(self) -> dict[str, Any]:
        """List configured clusters.

        Returns:
            Dict with clusters list
        """
        clusters = []
        config = self.config
        default_cluster = config.get("default_cluster")

        for name, cluster_config in config.get("clusters", {}).items():
            clusters.append(
                {
                    "name": name,
                    "server": cluster_config.get("server"),
                    "description": cluster_config.get("description", ""),
                    "default_project": cluster_config.get("default_project"),
                    "is_default": name == default_cluster,
                }
            )

        return {"clusters": clusters, "default_cluster": default_cluster}

    async def whoami(self) -> dict[str, Any]:
        """Get current user and cluster information.

        Returns:
            Dict with user info
        """
        # Get current user
        user_result = await self._run_oc_command(["whoami"])
        user = user_result.stdout.decode().strip() if user_result.returncode == 0 else "unknown"

        # Get current server
        server_result = await self._run_oc_command(["whoami", "--show-server"])
        server = server_result.stdout.decode().strip() if server_result.returncode == 0 else "unknown"

        # Get current project
        project_result = await self._run_oc_command(["project", "-q"])
        project = project_result.stdout.decode().strip() if project_result.returncode == 0 else "unknown"

        # Get token info
        token_result = await self._run_oc_command(["whoami", "-t"])
        token_valid = token_result.returncode == 0

        # Try to get token expiry (if available)
        token_expires = None
        if token_valid:
            # Get token and decode to check expiry
            # Note: token variable intentionally unused - for future enhancement
            try:
                # Try to get token info from oc
                token_info_result = await self._run_oc_command(["whoami", "--show-token"])
                if token_info_result.returncode == 0:
                    # Note: OpenShift doesn't provide expiry via CLI easily
                    # This is a placeholder for future enhancement
                    token_expires = None
            except Exception:
                pass

        # Get current cluster name (if available from config)
        cluster = "unknown"
        cluster_config_data = None
        for name, cluster_config in self.config.get("clusters", {}).items():
            if cluster_config.get("server") == server:
                cluster = name
                cluster_config_data = cluster_config
                break

        # Prefer default_project from config over current oc project
        # This ensures we use the configured project even if oc is set to a different one
        if cluster_config_data and cluster_config_data.get("default_project"):
            project = cluster_config_data.get("default_project")

        return {
            "user": user,
            "cluster": cluster,
            "server": server,
            "project": project,
            "token_expires": token_expires,
            "token_valid": token_valid,
            "authenticated": user != "unknown" and server != "unknown",
        }

    # P2 Feature: Clone Session
    async def clone_session(
        self, project: str, source_session: str, new_display_name: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """Clone a session with its configuration.

        Args:
            project: Project/namespace name
            source_session: Source session name to clone
            new_display_name: Display name for new session
            dry_run: Preview without creating

        Returns:
            Dict with cloned session info
        """
        try:
            # Get source session
            source_data = await self._get_resource_json("agenticsession", source_session, project)

            if dry_run:
                return {
                    "dry_run": True,
                    "success": True,
                    "message": f"Would clone session '{source_session}' with display name '{new_display_name}'",
                    "source_info": {
                        "name": source_data.get("metadata", {}).get("name"),
                        "display_name": source_data.get("spec", {}).get("displayName"),
                        "repos": source_data.get("spec", {}).get("repos", []),
                        "workflow": source_data.get("spec", {}).get("workflow"),
                    },
                }

            # Create new session from source spec
            new_spec = source_data.get("spec", {}).copy()
            new_spec["displayName"] = new_display_name
            new_spec["stopped"] = False  # Start new session as running

            # Create session manifest
            manifest = {
                "apiVersion": "vteam.ambient-code/v1alpha1",
                "kind": "AgenticSession",
                "metadata": {
                    "generateName": f"{source_session}-clone-",
                    "namespace": project,
                },
                "spec": new_spec,
            }

            # Apply manifest using secure temporary file
            import os
            import tempfile

            # Security: Use secure temp file with proper permissions (0600)
            fd, manifest_file = tempfile.mkstemp(suffix=".yaml", prefix=f"acp-clone-{secrets.token_hex(8)}-")
            try:
                # Write to file descriptor with secure permissions
                with os.fdopen(fd, "w") as f:
                    yaml.dump(manifest, f)

                result = await self._run_oc_command(["create", "-f", manifest_file, "-o", "json"])

                if result.returncode != 0:
                    return {
                        "cloned": False,
                        "message": f"Failed to clone session: {result.stderr.decode()}",
                    }

                created_data = json.loads(result.stdout.decode())
                new_session_name = created_data.get("metadata", {}).get("name")

                return {
                    "cloned": True,
                    "session": new_session_name,
                    "message": f"Successfully cloned session '{source_session}' to '{new_session_name}'",
                }
            finally:
                # Ensure cleanup even if operation fails
                try:
                    os.unlink(manifest_file)
                except OSError:
                    pass

        except Exception as e:
            return {"cloned": False, "message": str(e)}

    # P2 Feature: Get Session Transcript
    async def get_session_transcript(self, project: str, session: str, format: str = "json") -> dict[str, Any]:
        """Get session transcript/conversation history.

        Args:
            project: Project/namespace name
            session: Session name
            format: Output format ("json" or "markdown")

        Returns:
            Dict with transcript data
        """
        try:
            session_data = await self._get_resource_json("agenticsession", session, project)

            # Get events which contain the conversation
            # Note: events variable intentionally unused - for future enhancement
            # events = await self._list_resources_json(
            #     "event", project, selector=f"involvedObject.name={session}"
            # )

            # Extract transcript from session status if available
            transcript_data = session_data.get("status", {}).get("transcript") or []

            if format == "markdown":
                # Convert to markdown format
                markdown = f"# Session Transcript: {session}\n\n"
                for idx, entry in enumerate(transcript_data):
                    role = entry.get("role", "unknown")
                    content = entry.get("content", "")
                    timestamp = entry.get("timestamp", "")
                    markdown += f"## Message {idx + 1} - {role}\n"
                    if timestamp:
                        markdown += f"*{timestamp}*\n\n"
                    markdown += f"{content}\n\n"
                    markdown += "---\n\n"

                return {
                    "transcript": markdown,
                    "format": "markdown",
                    "message_count": len(transcript_data),
                }
            else:
                # Return as JSON
                return {
                    "transcript": transcript_data,
                    "format": "json",
                    "message_count": len(transcript_data),
                }

        except Exception as e:
            return {"transcript": None, "error": str(e)}

    # P2 Feature: Update Session
    async def update_session(
        self,
        project: str,
        session: str,
        display_name: str | None = None,
        timeout: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Update session metadata.

        Args:
            project: Project/namespace name
            session: Session name
            display_name: New display name
            timeout: New timeout in seconds
            dry_run: Preview without updating

        Returns:
            Dict with update status
        """
        try:
            session_data = await self._get_resource_json("agenticsession", session, project)

            if dry_run:
                updates = {}
                if display_name:
                    updates["displayName"] = display_name
                if timeout:
                    updates["timeout"] = timeout

                return {
                    "dry_run": True,
                    "success": True,
                    "message": f"Would update session '{session}'",
                    "updates": updates,
                    "current": {
                        "displayName": session_data.get("spec", {}).get("displayName"),
                        "timeout": session_data.get("spec", {}).get("timeout"),
                    },
                }

            # Build patch
            patch = {"spec": {}}
            if display_name:
                patch["spec"]["displayName"] = display_name
            if timeout:
                patch["spec"]["timeout"] = timeout

            if not patch["spec"]:
                return {"updated": False, "message": "No updates specified"}

            result = await self._run_oc_command(
                [
                    "patch",
                    "agenticsession",
                    session,
                    "-n",
                    project,
                    "--type=merge",
                    "-p",
                    json.dumps(patch),
                    "-o",
                    "json",
                ]
            )

            if result.returncode != 0:
                return {
                    "updated": False,
                    "message": f"Failed to update session: {result.stderr.decode()}",
                }

            updated_data = json.loads(result.stdout.decode())

            return {
                "updated": True,
                "session": updated_data,
                "message": f"Successfully updated session '{session}'",
            }

        except Exception as e:
            return {"updated": False, "message": str(e)}

    # P2 Feature: Export Session
    async def export_session(self, project: str, session: str) -> dict[str, Any]:
        """Export session configuration and transcript.

        Args:
            project: Project/namespace name
            session: Session name

        Returns:
            Dict with exported session data
        """
        try:
            session_data = await self._get_resource_json("agenticsession", session, project)

            # Get transcript
            transcript_result = await self.get_session_transcript(project, session, format="json")

            export_data = {
                "config": {
                    "name": session_data.get("metadata", {}).get("name"),
                    "displayName": session_data.get("spec", {}).get("displayName"),
                    "repos": session_data.get("spec", {}).get("repos", []),
                    "workflow": session_data.get("spec", {}).get("workflow"),
                    "llmConfig": session_data.get("spec", {}).get("llmConfig", {}),
                },
                "transcript": transcript_result.get("transcript", []),
                "metadata": {
                    "created": session_data.get("metadata", {}).get("creationTimestamp"),
                    "status": session_data.get("status", {}).get("phase"),
                    "stoppedAt": session_data.get("status", {}).get("stoppedAt"),
                    "messageCount": transcript_result.get("message_count", 0),
                },
            }

            return {
                "exported": True,
                "data": export_data,
                "message": f"Successfully exported session '{session}'",
            }

        except Exception as e:
            return {"exported": False, "error": str(e)}

    # P3 Feature: Get Session Metrics
    async def get_session_metrics(self, project: str, session: str) -> dict[str, Any]:
        """Get session metrics and statistics.

        Args:
            project: Project/namespace name
            session: Session name

        Returns:
            Dict with session metrics
        """
        try:
            session_data = await self._get_resource_json("agenticsession", session, project)

            # Get transcript for analysis
            transcript_result = await self.get_session_transcript(project, session, format="json")
            transcript = transcript_result.get("transcript") or []

            # Calculate metrics
            token_count = 0
            message_count = len(transcript) if transcript else 0
            tool_calls = {}

            for entry in transcript:
                # Count tokens (approximate)
                content = entry.get("content", "")
                token_count += len(content.split()) * 1.3  # Rough estimate

                # Count tool calls
                if "tool_calls" in entry:
                    for tool_call in entry.get("tool_calls", []):
                        tool_name = tool_call.get("name", "unknown")
                        tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1

            # Calculate duration
            created = session_data.get("metadata", {}).get("creationTimestamp")
            stopped = session_data.get("status", {}).get("stoppedAt")

            duration_seconds = 0
            if created and stopped:
                try:
                    from datetime import datetime

                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    stopped_dt = datetime.fromisoformat(stopped.replace("Z", "+00:00"))
                    duration_seconds = int((stopped_dt - created_dt).total_seconds())
                except Exception:
                    pass

            return {
                "token_count": int(token_count),
                "duration_seconds": duration_seconds,
                "tool_calls": tool_calls,
                "message_count": message_count,
                "status": session_data.get("status", {}).get("phase"),
            }

        except Exception as e:
            return {"error": str(e)}

    # P3 Feature: List Workflows
    async def list_workflows(self, repo_url: str | None = None) -> dict[str, Any]:
        """List available workflows from repository.

        Args:
            repo_url: Repository URL (defaults to ootb-ambient-workflows)

        Returns:
            Dict with workflows list
        """
        if not repo_url:
            repo_url = "https://github.com/ambient-code/ootb-ambient-workflows"

        # Security: Validate repo URL format
        if not isinstance(repo_url, str):
            return {"workflows": [], "error": "Repository URL must be a string"}
        if not (repo_url.startswith("https://") or repo_url.startswith("http://")):
            return {"workflows": [], "error": "Repository URL must use http:// or https://"}
        # Prevent command injection through URL
        if any(char in repo_url for char in [";", "|", "&", "$", "`", "\n", "\r", " "]):
            return {"workflows": [], "error": "Invalid characters in repository URL"}

        try:
            # Clone repo to temp directory
            import shutil
            import tempfile

            # Security: Use secure temp directory with random name
            temp_dir = tempfile.mkdtemp(prefix=f"acp-workflows-{secrets.token_hex(8)}-")

            try:
                # Clone the repo using secure subprocess
                process = await asyncio.create_subprocess_exec(
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--",
                    repo_url,
                    temp_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=60,  # 60 second timeout for git clone
                )

                if process.returncode != 0:
                    return {
                        "workflows": [],
                        "error": f"Failed to clone repository: {stderr.decode()}",
                    }

                # Find workflow files
                workflows = []
                workflows_dir = Path(temp_dir) / "workflows"

                if workflows_dir.exists():
                    # Limit to prevent DoS
                    file_count = 0
                    max_files = 100
                    for workflow_file in workflows_dir.glob("**/*.yaml"):
                        if file_count >= max_files:
                            break
                        file_count += 1

                        # Security: Validate file is within expected directory
                        try:
                            workflow_file.resolve().relative_to(workflows_dir.resolve())
                        except ValueError:
                            continue  # Skip files outside workflows directory

                        # Read workflow to get metadata
                        try:
                            with open(workflow_file) as f:
                                workflow_data = yaml.safe_load(f)
                                if not isinstance(workflow_data, dict):
                                    workflow_data = {}

                            workflows.append(
                                {
                                    "name": workflow_file.stem,
                                    "path": str(workflow_file.relative_to(workflows_dir)),
                                    "description": (
                                        workflow_data.get("description", "")
                                        if isinstance(workflow_data.get("description"), str)
                                        else ""
                                    ),
                                }
                            )
                        except (yaml.YAMLError, OSError):
                            # Skip invalid workflow files
                            continue

                return {
                    "workflows": workflows,
                    "repo_url": repo_url,
                    "count": len(workflows),
                }

            finally:
                # Clean up temp directory securely
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

        except TimeoutError:
            return {"workflows": [], "error": "Repository clone timed out"}
        except Exception as e:
            return {"workflows": [], "error": f"Unexpected error: {str(e)}"}

    # P3 Feature: Create Session from Template
    async def create_session_from_template(
        self,
        project: str,
        template: str,
        display_name: str,
        repos: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create session from predefined template.

        Args:
            project: Project/namespace name
            template: Template name (triage, bugfix, feature, exploration)
            display_name: Display name for session
            repos: Optional list of repository URLs
            dry_run: Preview without creating

        Returns:
            Dict with session creation status
        """
        # Define templates
        templates = {
            "triage": {
                "workflow": "triage",
                "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.7},
                "description": "Triage and analyze issues",
            },
            "bugfix": {
                "workflow": "bugfix",
                "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.3},
                "description": "Fix bugs and issues",
            },
            "feature": {
                "workflow": "feature-development",
                "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.5},
                "description": "Develop new features",
            },
            "exploration": {
                "workflow": "codebase-exploration",
                "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.8},
                "description": "Explore codebase",
            },
        }

        if template not in templates:
            return {
                "created": False,
                "message": f"Unknown template: {template}. Available: {', '.join(templates.keys())}",
            }

        template_config = templates[template]

        if dry_run:
            return {
                "dry_run": True,
                "success": True,
                "message": f"Would create session from template '{template}'",
                "template_config": template_config,
                "display_name": display_name,
                "repos": repos or [],
            }

        try:
            # Create session manifest
            manifest = {
                "apiVersion": "vteam.ambient-code/v1alpha1",
                "kind": "AgenticSession",
                "metadata": {
                    "generateName": f"{template}-",
                    "namespace": project,
                },
                "spec": {
                    "displayName": display_name,
                    "workflow": template_config["workflow"],
                    "llmConfig": template_config["llmConfig"],
                    "repos": repos or [],
                },
            }

            # Apply manifest using secure temporary file
            import os
            import tempfile

            # Security: Use secure temp file with proper permissions (0600)
            fd, manifest_file = tempfile.mkstemp(suffix=".yaml", prefix=f"acp-template-{secrets.token_hex(8)}-")
            try:
                # Write to file descriptor with secure permissions
                with os.fdopen(fd, "w") as f:
                    yaml.dump(manifest, f)

                result = await self._run_oc_command(["create", "-f", manifest_file, "-o", "json"])

                if result.returncode != 0:
                    return {
                        "created": False,
                        "message": f"Failed to create session: {result.stderr.decode()}",
                    }

                created_data = json.loads(result.stdout.decode())
                session_name = created_data.get("metadata", {}).get("name")

                return {
                    "created": True,
                    "session": session_name,
                    "message": f"Successfully created session '{session_name}' from template '{template}'",
                }
            finally:
                # Ensure cleanup even if operation fails
                try:
                    os.unlink(manifest_file)
                except OSError:
                    pass

        except Exception as e:
            return {"created": False, "message": str(e)}

    # Auth Feature: Login
    async def login(self, cluster: str, web: bool = True, token: str | None = None) -> dict[str, Any]:
        """Authenticate to OpenShift cluster.

        Args:
            cluster: Cluster alias name or server URL
            web: Use web login flow
            token: Direct token authentication

        Returns:
            Dict with login status
        """
        # Look up cluster in config
        server = cluster
        if cluster in self.config.get("clusters", {}):
            server = self.config["clusters"][cluster]["server"]

        try:
            if token:
                # Token-based login
                result = await self._run_oc_command(
                    ["login", "--token", token, "--server", server],
                    capture_output=False,
                )
            elif web:
                # Web-based login
                result = await self._run_oc_command(
                    ["login", "--web", "--server", server],
                    capture_output=False,
                )
            else:
                return {
                    "authenticated": False,
                    "message": "Either 'web' or 'token' must be provided",
                }

            if result.returncode != 0:
                return {
                    "authenticated": False,
                    "message": "Login failed",
                }

            # Get user info after login
            whoami_result = await self.whoami()

            return {
                "authenticated": True,
                "user": whoami_result.get("user"),
                "cluster": cluster,
                "server": server,
                "message": f"Successfully logged in to {cluster}",
            }

        except Exception as e:
            return {"authenticated": False, "message": str(e)}

    # Auth Feature: Switch Cluster
    async def switch_cluster(self, cluster: str) -> dict[str, Any]:
        """Switch to a different cluster context.

        Args:
            cluster: Cluster alias name

        Returns:
            Dict with switch status
        """
        if cluster not in self.config.get("clusters", {}):
            return {
                "switched": False,
                "message": f"Unknown cluster: {cluster}. Use acp_list_clusters to see available clusters.",
            }

        cluster_config = self.config["clusters"][cluster]
        server = cluster_config["server"]

        try:
            # Get current context
            current_whoami = await self.whoami()
            previous_cluster = current_whoami.get("cluster", "unknown")

            # Switch context (assumes already authenticated)
            result = await self._run_oc_command(
                ["login", "--server", server],
                capture_output=False,
            )

            if result.returncode != 0:
                return {
                    "switched": False,
                    "message": f"Failed to switch to {cluster}. You may need to login first.",
                }

            # Get new user info
            new_whoami = await self.whoami()

            return {
                "switched": True,
                "previous": previous_cluster,
                "current": cluster,
                "user": new_whoami.get("user"),
                "message": f"Switched from {previous_cluster} to {cluster}",
            }

        except Exception as e:
            return {"switched": False, "message": str(e)}

    # Auth Feature: Add Cluster
    def add_cluster(
        self,
        name: str,
        server: str,
        description: str | None = None,
        default_project: str | None = None,
        set_default: bool = False,
    ) -> dict[str, Any]:
        """Add a new cluster to configuration.

        Args:
            name: Cluster alias name
            server: Server URL
            description: Optional description
            default_project: Optional default project
            set_default: Set as default cluster

        Returns:
            Dict with add status
        """
        try:
            # Security: Validate inputs
            if not isinstance(name, str) or not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", name):
                return {"added": False, "message": "Invalid cluster name format"}
            if not isinstance(server, str) or not (server.startswith("https://") or server.startswith("http://")):
                return {"added": False, "message": "Server must be a valid HTTP/HTTPS URL"}
            if description and (not isinstance(description, str) or len(description) > 500):
                return {
                    "added": False,
                    "message": "Description must be a string under 500 characters",
                }
            if default_project:
                try:
                    self._validate_input(default_project, "default_project")
                except ValueError as e:
                    return {"added": False, "message": str(e)}

            # Update config
            if "clusters" not in self.config:
                self.config["clusters"] = {}

            self.config["clusters"][name] = {
                "server": server,
                "description": description or "",
                "default_project": default_project,
            }

            if set_default:
                self.config["default_cluster"] = name

            # Save config securely
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)

            # Security: Write with restricted permissions
            with open(config_file, "w") as f:
                yaml.dump(self.config, f)
            # Set file permissions to 0600 (owner read/write only)
            import os

            os.chmod(config_file, 0o600)

            return {
                "added": True,
                "cluster": {
                    "name": name,
                    "server": server,
                    "description": description,
                    "default_project": default_project,
                    "is_default": set_default,
                },
                "message": f"Successfully added cluster '{name}'",
            }

        except Exception as e:
            return {"added": False, "message": f"Failed to add cluster: {str(e)}"}
