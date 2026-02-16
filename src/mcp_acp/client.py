"""ACP client for Ambient Code Platform public API.

This client communicates with the public-api gateway service which provides
a simplified REST API for managing AgenticSessions.
"""

import os
import re
from datetime import datetime, timedelta
from typing import Any

import httpx

from mcp_acp.settings import load_clusters_config, load_settings
from utils.pylogger import get_python_logger

logger = get_python_logger()

LABEL_VALUE_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$")

SESSION_TEMPLATES: dict[str, dict[str, Any]] = {
    "triage": {
        "workflow": "triage",
        "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.7},
    },
    "bugfix": {
        "workflow": "bugfix",
        "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.3},
    },
    "feature": {
        "workflow": "feature-development",
        "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.5},
    },
    "exploration": {
        "workflow": "codebase-exploration",
        "llmConfig": {"model": "claude-sonnet-4", "temperature": 0.8},
    },
}


class ACPClient:
    """Client for interacting with Ambient Code Platform via public API.

    Attributes:
        settings: Global settings instance
        clusters_config: Cluster configuration instance
    """

    MAX_BULK_ITEMS = 3
    DEFAULT_TIMEOUT = 30.0

    def __init__(self, config_path: str | None = None, settings=None):
        """Initialize ACP client.

        Args:
            config_path: Path to clusters.yaml config file
            settings: Settings instance. If not provided, loads default settings.
        """
        from pathlib import Path

        self.settings = settings or load_settings()

        if config_path:
            self.settings.config_path = Path(config_path)

        try:
            self.clusters_config = load_clusters_config(self.settings)
        except Exception as e:
            logger.error("cluster_config_load_failed", error=str(e))
            raise

        self._http_client: httpx.AsyncClient | None = None

        logger.info(
            "acp_client_initialized",
            clusters=list(self.clusters_config.clusters.keys()),
            default_cluster=self.clusters_config.default_cluster,
        )

    # ── HTTP infrastructure ──────────────────────────────────────────────

    def _get_cluster_config(self, cluster_name: str | None = None) -> dict[str, Any]:
        """Get cluster configuration."""
        name = cluster_name or self.clusters_config.default_cluster
        if not name:
            raise ValueError("No cluster specified and no default_cluster configured")

        cluster = self.clusters_config.clusters.get(name)
        if not cluster:
            raise ValueError(f"Cluster '{name}' not found in configuration")

        return {
            "server": cluster.server,
            "default_project": cluster.default_project,
            "description": cluster.description,
            "token": cluster.token,
        }

    def _get_token(self, cluster_config: dict[str, Any]) -> str:
        """Get authentication token for a cluster."""
        token = cluster_config.get("token") or os.getenv("ACP_TOKEN")

        if not token:
            raise ValueError(
                "No authentication token available. Set 'token' in clusters.yaml or ACP_TOKEN environment variable."
            )

        return token

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.DEFAULT_TIMEOUT),
                follow_redirects=True,
            )
        return self._http_client

    async def _request(
        self,
        method: str,
        path: str,
        project: str,
        cluster_name: str | None = None,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the public API expecting JSON response."""
        cluster_config = self._get_cluster_config(cluster_name)
        token = self._get_token(cluster_config)
        base_url = cluster_config["server"]

        url = f"{base_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Ambient-Project": project,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        client = await self._get_http_client()

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", f"HTTP {response.status_code}")
                except Exception:
                    error_msg = f"HTTP {response.status_code}: {response.text}"

                logger.warning(
                    "api_request_failed",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    error=error_msg,
                )
                raise ValueError(error_msg)

            if response.status_code == 204:
                return {"success": True}

            return response.json()

        except httpx.TimeoutException as e:
            logger.error("api_request_timeout", method=method, path=path, error=str(e))
            raise TimeoutError(f"Request timed out: {path}") from e
        except httpx.RequestError as e:
            logger.error("api_request_error", method=method, path=path, error=str(e))
            raise ValueError(f"Request failed: {str(e)}") from e

    async def _request_text(
        self,
        method: str,
        path: str,
        project: str,
        cluster_name: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Make an HTTP request expecting text response (e.g., logs)."""
        cluster_config = self._get_cluster_config(cluster_name)
        token = self._get_token(cluster_config)
        base_url = cluster_config["server"]

        url = f"{base_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Ambient-Project": project,
            "Accept": "text/plain",
        }

        client = await self._get_http_client()

        try:
            response = await client.request(method=method, url=url, headers=headers, params=params)

            if response.status_code >= 400:
                raise ValueError(f"HTTP {response.status_code}: {response.text}")

            return response.text

        except httpx.TimeoutException as e:
            logger.error("api_request_timeout", method=method, path=path, error=str(e))
            raise TimeoutError(f"Request timed out: {path}") from e
        except httpx.RequestError as e:
            logger.error("api_request_error", method=method, path=path, error=str(e))
            raise ValueError(f"Request failed: {str(e)}") from e

    # ── Validation ───────────────────────────────────────────────────────

    def _validate_input(self, value: str, field_name: str, max_length: int = 253) -> None:
        """Validate input to prevent injection attacks."""
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        if len(value) > max_length:
            raise ValueError(f"{field_name} exceeds maximum length of {max_length}")
        if not re.match(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", value):
            raise ValueError(f"{field_name} contains invalid characters. Must match DNS-1123 format.")

    def _validate_bulk_operation(self, items: list[str], operation_name: str) -> None:
        """Enforce item limit for bulk operations."""
        if len(items) > self.MAX_BULK_ITEMS:
            raise ValueError(
                f"Bulk {operation_name} limited to {self.MAX_BULK_ITEMS} items. "
                f"You requested {len(items)}. Split into multiple operations."
            )

    def _validate_labels(self, labels: dict[str, str]) -> None:
        """Validate label keys and values."""
        if not labels:
            raise ValueError("Labels must not be empty")
        for key, value in labels.items():
            if len(key) > 63 or not LABEL_VALUE_PATTERN.match(key):
                raise ValueError(
                    f"Invalid label key '{key}'. Must be 1-63 alphanumeric chars, dashes, dots, or underscores."
                )
            if len(value) > 63 or not LABEL_VALUE_PATTERN.match(value):
                raise ValueError(
                    f"Invalid label value '{value}' for key '{key}'. Must be 1-63 alphanumeric chars, dashes, dots, or underscores."
                )

    # ── Time utilities ───────────────────────────────────────────────────

    def _parse_time_delta(self, time_str: str) -> datetime:
        """Parse time delta string to datetime."""
        match = re.match(r"(\d+)([dhm])", time_str.lower())
        if not match:
            raise ValueError(f"Invalid time format: {time_str}. Use '7d', '24h', or '30m'")

        value, unit = int(match.group(1)), match.group(2)
        now = datetime.utcnow()

        deltas = {"d": timedelta(days=value), "h": timedelta(hours=value), "m": timedelta(minutes=value)}
        return now - deltas[unit]

    def _is_older_than(self, timestamp_str: str | None, cutoff: datetime) -> bool:
        """Check if timestamp is older than cutoff."""
        if not timestamp_str:
            return False
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return timestamp.replace(tzinfo=None) < cutoff

    def _sort_sessions(self, sessions: list[dict], sort_by: str) -> list[dict]:
        """Sort sessions by field."""
        sort_keys = {
            "created": lambda s: s.get("createdAt", ""),
            "stopped": lambda s: s.get("completedAt", ""),
            "name": lambda s: s.get("id", ""),
        }

        key_fn = sort_keys.get(sort_by)
        if key_fn:
            return sorted(sessions, key=key_fn, reverse=(sort_by != "name"))
        return sessions

    # ── Session CRUD ─────────────────────────────────────────────────────

    async def list_sessions(
        self,
        project: str,
        status: str | None = None,
        older_than: str | None = None,
        sort_by: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List sessions with filtering."""
        self._validate_input(project, "project")

        response = await self._request("GET", "/v1/sessions", project)
        sessions = response.get("items", [])

        filters = []
        filters_applied = {}

        if status:
            filters.append(lambda s: s.get("status", "").lower() == status.lower())
            filters_applied["status"] = status

        if older_than:
            cutoff_time = self._parse_time_delta(older_than)
            filters.append(lambda s: self._is_older_than(s.get("createdAt"), cutoff_time))
            filters_applied["older_than"] = older_than

        filtered = [s for s in sessions if all(f(s) for f in filters)]

        if sort_by:
            filtered = self._sort_sessions(filtered, sort_by)
            filters_applied["sort_by"] = sort_by

        if limit and limit > 0:
            filtered = filtered[:limit]
            filters_applied["limit"] = limit

        return {
            "sessions": filtered,
            "total": len(filtered),
            "filters_applied": filters_applied,
        }

    async def get_session(self, project: str, session: str) -> dict[str, Any]:
        """Get a session by ID."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        return await self._request("GET", f"/v1/sessions/{session}", project)

    async def create_session(
        self,
        project: str,
        initial_prompt: str,
        display_name: str | None = None,
        repos: list[str] | None = None,
        interactive: bool = False,
        model: str = "claude-sonnet-4",
        timeout: int = 900,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create an AgenticSession with a custom prompt."""
        self._validate_input(project, "project")

        session_data: dict[str, Any] = {
            "initialPrompt": initial_prompt,
            "interactive": interactive,
            "llmConfig": {"model": model},
            "timeout": timeout,
        }

        if display_name:
            session_data["displayName"] = display_name

        if repos:
            session_data["repos"] = repos

        if dry_run:
            return {
                "dry_run": True,
                "success": True,
                "message": "Would create session with custom prompt",
                "manifest": session_data,
                "project": project,
            }

        try:
            result = await self._request("POST", "/v1/sessions", project, json_data=session_data)
            session_id = result.get("id", "unknown")
            return {
                "created": True,
                "session": session_id,
                "project": project,
                "message": f"Session '{session_id}' created in project '{project}'",
            }
        except (ValueError, TimeoutError) as e:
            return {"created": False, "message": str(e)}

    async def create_session_from_template(
        self,
        project: str,
        template: str,
        display_name: str,
        repos: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create a session from a predefined template (triage/bugfix/feature/exploration)."""
        self._validate_input(project, "project")

        if template not in SESSION_TEMPLATES:
            raise ValueError(f"Unknown template '{template}'. Available: {', '.join(SESSION_TEMPLATES.keys())}")

        template_config = SESSION_TEMPLATES[template]
        session_data: dict[str, Any] = {
            "displayName": display_name,
            **template_config,
        }

        if repos:
            session_data["repos"] = repos

        if dry_run:
            return {
                "dry_run": True,
                "success": True,
                "message": f"Would create session from template '{template}'",
                "manifest": session_data,
                "project": project,
            }

        try:
            result = await self._request("POST", "/v1/sessions", project, json_data=session_data)
            session_id = result.get("id", "unknown")
            return {
                "created": True,
                "session": session_id,
                "project": project,
                "template": template,
                "message": f"Session '{session_id}' created from template '{template}'",
            }
        except (ValueError, TimeoutError) as e:
            return {"created": False, "message": str(e)}

    async def delete_session(self, project: str, session: str, dry_run: bool = False) -> dict[str, Any]:
        """Delete a session."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        if dry_run:
            try:
                session_data = await self._request("GET", f"/v1/sessions/{session}", project)
                return {
                    "dry_run": True,
                    "success": True,
                    "message": f"Would delete session '{session}' in project '{project}'",
                    "session_info": {
                        "name": session_data.get("id"),
                        "status": session_data.get("status"),
                        "created": session_data.get("createdAt"),
                    },
                }
            except ValueError:
                return {
                    "dry_run": True,
                    "success": False,
                    "message": f"Session '{session}' not found in project '{project}'",
                }

        try:
            await self._request("DELETE", f"/v1/sessions/{session}", project)
            return {
                "deleted": True,
                "message": f"Successfully deleted session '{session}' from project '{project}'",
            }
        except ValueError as e:
            return {
                "deleted": False,
                "message": f"Failed to delete session: {str(e)}",
            }

    async def restart_session(self, project: str, session: str, dry_run: bool = False) -> dict[str, Any]:
        """Restart a stopped session."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        if dry_run:
            try:
                session_data = await self._request("GET", f"/v1/sessions/{session}", project)
                return {
                    "dry_run": True,
                    "success": True,
                    "message": f"Would restart session '{session}' in project '{project}'",
                    "session_info": {
                        "name": session_data.get("id"),
                        "status": session_data.get("status"),
                    },
                }
            except ValueError:
                return {"dry_run": True, "success": False, "message": f"Session '{session}' not found"}

        try:
            await self._request("PATCH", f"/v1/sessions/{session}", project, json_data={"stopped": False})
            return {"restarted": True, "message": f"Successfully restarted session '{session}'"}
        except ValueError as e:
            return {"restarted": False, "message": f"Failed to restart session: {str(e)}"}

    async def stop_session(self, project: str, session: str, dry_run: bool = False) -> dict[str, Any]:
        """Stop a running session."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        if dry_run:
            try:
                session_data = await self._request("GET", f"/v1/sessions/{session}", project)
                return {
                    "dry_run": True,
                    "success": True,
                    "message": f"Would stop session '{session}' in project '{project}'",
                    "session_info": {
                        "name": session_data.get("id"),
                        "status": session_data.get("status"),
                    },
                }
            except ValueError:
                return {"dry_run": True, "success": False, "message": f"Session '{session}' not found"}

        try:
            await self._request("PATCH", f"/v1/sessions/{session}", project, json_data={"stopped": True})
            return {"stopped": True, "message": f"Successfully stopped session '{session}'"}
        except ValueError as e:
            return {"stopped": False, "message": f"Failed to stop session: {str(e)}"}

    async def clone_session(
        self, project: str, source_session: str, new_display_name: str, dry_run: bool = False
    ) -> dict[str, Any]:
        """Clone an existing session with its configuration."""
        self._validate_input(project, "project")
        self._validate_input(source_session, "source_session")

        source = await self._request("GET", f"/v1/sessions/{source_session}", project)

        clone_data: dict[str, Any] = {
            "displayName": new_display_name,
            "initialPrompt": source.get("initialPrompt", ""),
            "interactive": source.get("interactive", False),
            "timeout": source.get("timeout", 900),
        }

        if source.get("llmConfig"):
            clone_data["llmConfig"] = source["llmConfig"]
        if source.get("repos"):
            clone_data["repos"] = source["repos"]

        if dry_run:
            return {
                "dry_run": True,
                "success": True,
                "message": f"Would clone session '{source_session}' as '{new_display_name}'",
                "manifest": clone_data,
                "source_session": source_session,
                "project": project,
            }

        try:
            result = await self._request("POST", "/v1/sessions", project, json_data=clone_data)
            session_id = result.get("id", "unknown")
            return {
                "created": True,
                "session": session_id,
                "source_session": source_session,
                "project": project,
                "message": f"Session '{session_id}' cloned from '{source_session}'",
            }
        except (ValueError, TimeoutError) as e:
            return {"created": False, "message": str(e)}

    async def update_session(
        self,
        project: str,
        session: str,
        display_name: str | None = None,
        timeout: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Update session metadata (display name, timeout)."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        patch_data: dict[str, Any] = {}
        if display_name is not None:
            patch_data["displayName"] = display_name
        if timeout is not None:
            patch_data["timeout"] = timeout

        if not patch_data:
            raise ValueError("No fields to update. Provide display_name or timeout.")

        if dry_run:
            try:
                current = await self._request("GET", f"/v1/sessions/{session}", project)
                return {
                    "dry_run": True,
                    "success": True,
                    "message": f"Would update session '{session}'",
                    "current": current,
                    "patch": patch_data,
                }
            except ValueError:
                return {"dry_run": True, "success": False, "message": f"Session '{session}' not found"}

        try:
            result = await self._request("PATCH", f"/v1/sessions/{session}", project, json_data=patch_data)
            return {
                "updated": True,
                "message": f"Successfully updated session '{session}'",
                "session": result,
            }
        except ValueError as e:
            return {"updated": False, "message": f"Failed to update session: {str(e)}"}

    # ── Observability ────────────────────────────────────────────────────

    async def get_session_logs(
        self,
        project: str,
        session: str,
        container: str | None = None,
        tail_lines: int = 1000,
    ) -> dict[str, Any]:
        """Retrieve container logs for a session."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        if tail_lines > 10000:
            raise ValueError("tail_lines cannot exceed 10000")

        params: dict[str, Any] = {"tailLines": tail_lines}
        if container:
            params["container"] = container

        try:
            text = await self._request_text("GET", f"/v1/sessions/{session}/logs", project, params=params)
            return {"logs": text, "session": session, "tail_lines": tail_lines}
        except (ValueError, TimeoutError) as e:
            return {"logs": "", "error": str(e), "session": session}

    async def get_session_transcript(
        self,
        project: str,
        session: str,
        format: str = "json",
    ) -> dict[str, Any]:
        """Retrieve conversation history for a session."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        if format not in ("json", "markdown"):
            raise ValueError("format must be 'json' or 'markdown'")

        params = {"format": format}
        result = await self._request("GET", f"/v1/sessions/{session}/transcript", project, params=params)
        result["session"] = session
        result["format"] = format
        return result

    async def get_session_metrics(self, project: str, session: str) -> dict[str, Any]:
        """Get usage statistics for a session (tokens, duration, tool calls)."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        result = await self._request("GET", f"/v1/sessions/{session}/metrics", project)
        result["session"] = session
        return result

    # ── Labels ───────────────────────────────────────────────────────────

    async def label_session(self, project: str, session: str, labels: dict[str, str]) -> dict[str, Any]:
        """Add labels to a session."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")
        self._validate_labels(labels)

        await self._request("PATCH", f"/v1/sessions/{session}", project, json_data={"labels": labels})
        return {
            "labeled": True,
            "session": session,
            "labels_added": labels,
            "message": f"Added {len(labels)} label(s) to session '{session}'",
        }

    async def unlabel_session(self, project: str, session: str, label_keys: list[str]) -> dict[str, Any]:
        """Remove labels from a session."""
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        if not label_keys:
            raise ValueError("label_keys must not be empty")

        await self._request("PATCH", f"/v1/sessions/{session}", project, json_data={"removeLabels": label_keys})
        return {
            "unlabeled": True,
            "session": session,
            "labels_removed": label_keys,
            "message": f"Removed {len(label_keys)} label(s) from session '{session}'",
        }

    async def list_sessions_by_label(self, project: str, labels: dict[str, str]) -> dict[str, Any]:
        """List sessions matching label selectors."""
        self._validate_input(project, "project")
        self._validate_labels(labels)

        # Build label selector query: key1=value1,key2=value2
        selector = ",".join(f"{k}={v}" for k, v in labels.items())
        params = {"labelSelector": selector}

        response = await self._request("GET", "/v1/sessions", project, params=params)
        sessions = response.get("items", [])

        return {
            "sessions": sessions,
            "total": len(sessions),
            "labels_filter": labels,
        }

    # ── Bulk operations ──────────────────────────────────────────────────

    async def _run_bulk(
        self,
        project: str,
        sessions: list[str],
        op_fn,
        operation_name: str,
        success_key: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Shared bulk operation runner. Iterates sessions, calls op_fn, collects results."""
        self._validate_bulk_operation(sessions, operation_name)

        success: list[str] = []
        failed: list[dict[str, str]] = []
        dry_run_info: dict[str, list] = {"would_execute": [], "skipped": []}

        for session_name in sessions:
            result = await op_fn(project=project, session=session_name, dry_run=dry_run)

            if dry_run:
                if result.get("success", True):
                    dry_run_info["would_execute"].append({"session": session_name, "info": result.get("session_info")})
                else:
                    dry_run_info["skipped"].append({"session": session_name, "reason": result.get("message")})
            else:
                if result.get(success_key):
                    success.append(session_name)
                else:
                    failed.append({"session": session_name, "error": result.get("message", "unknown error")})

        response: dict[str, Any] = {success_key: success, "failed": failed}
        if dry_run:
            response["dry_run"] = True
            response["dry_run_info"] = dry_run_info
        return response

    async def _run_bulk_by_label(
        self,
        project: str,
        labels: dict[str, str],
        op_fn,
        operation_name: str,
        success_key: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Find sessions by label, then run bulk operation on them."""
        matched = await self.list_sessions_by_label(project, labels)
        sessions = matched.get("sessions", [])
        names = [s.get("id", s.get("metadata", {}).get("name", "")) for s in sessions]

        if not names:
            return {
                success_key: [],
                "failed": [],
                "message": "No sessions match the given labels",
                "labels_filter": labels,
            }

        self._validate_bulk_operation(names, operation_name)
        result = await self._run_bulk(project, names, op_fn, operation_name, success_key, dry_run)
        result["labels_filter"] = labels
        return result

    async def bulk_delete_sessions(self, project: str, sessions: list[str], dry_run: bool = False) -> dict[str, Any]:
        """Delete multiple sessions (max 3)."""
        return await self._run_bulk(project, sessions, self.delete_session, "delete", "deleted", dry_run)

    async def bulk_stop_sessions(self, project: str, sessions: list[str], dry_run: bool = False) -> dict[str, Any]:
        """Stop multiple running sessions (max 3)."""
        return await self._run_bulk(project, sessions, self.stop_session, "stop", "stopped", dry_run)

    async def bulk_restart_sessions(self, project: str, sessions: list[str], dry_run: bool = False) -> dict[str, Any]:
        """Restart multiple stopped sessions (max 3)."""
        return await self._run_bulk(project, sessions, self.restart_session, "restart", "restarted", dry_run)

    async def bulk_label_sessions(
        self, project: str, sessions: list[str], labels: dict[str, str], dry_run: bool = False
    ) -> dict[str, Any]:
        """Add labels to multiple sessions (max 3)."""
        self._validate_bulk_operation(sessions, "label")
        self._validate_labels(labels)

        success: list[str] = []
        failed: list[dict[str, str]] = []

        if dry_run:
            return {
                "dry_run": True,
                "sessions": sessions,
                "labels": labels,
                "message": f"Would add {len(labels)} label(s) to {len(sessions)} session(s)",
            }

        for session_name in sessions:
            try:
                await self.label_session(project, session_name, labels)
                success.append(session_name)
            except (ValueError, TimeoutError) as e:
                failed.append({"session": session_name, "error": str(e)})

        return {"labeled": success, "failed": failed, "labels": labels}

    async def bulk_unlabel_sessions(
        self, project: str, sessions: list[str], label_keys: list[str], dry_run: bool = False
    ) -> dict[str, Any]:
        """Remove labels from multiple sessions (max 3)."""
        self._validate_bulk_operation(sessions, "unlabel")

        if dry_run:
            return {
                "dry_run": True,
                "sessions": sessions,
                "label_keys": label_keys,
                "message": f"Would remove {len(label_keys)} label(s) from {len(sessions)} session(s)",
            }

        success: list[str] = []
        failed: list[dict[str, str]] = []

        for session_name in sessions:
            try:
                await self.unlabel_session(project, session_name, label_keys)
                success.append(session_name)
            except (ValueError, TimeoutError) as e:
                failed.append({"session": session_name, "error": str(e)})

        return {"unlabeled": success, "failed": failed, "label_keys": label_keys}

    async def bulk_delete_sessions_by_label(
        self, project: str, labels: dict[str, str], dry_run: bool = False
    ) -> dict[str, Any]:
        """Delete sessions matching label selectors (max 3 matches)."""
        return await self._run_bulk_by_label(project, labels, self.delete_session, "delete", "deleted", dry_run)

    async def bulk_stop_sessions_by_label(
        self, project: str, labels: dict[str, str], dry_run: bool = False
    ) -> dict[str, Any]:
        """Stop sessions matching label selectors (max 3 matches)."""
        return await self._run_bulk_by_label(project, labels, self.stop_session, "stop", "stopped", dry_run)

    async def bulk_restart_sessions_by_label(
        self, project: str, labels: dict[str, str], dry_run: bool = False
    ) -> dict[str, Any]:
        """Restart sessions matching label selectors (max 3 matches)."""
        return await self._run_bulk_by_label(project, labels, self.restart_session, "restart", "restarted", dry_run)

    # ── Cluster & auth ───────────────────────────────────────────────────

    def list_clusters(self) -> dict[str, Any]:
        """List configured clusters."""
        clusters = []
        default_cluster = self.clusters_config.default_cluster

        for name, cluster in self.clusters_config.clusters.items():
            clusters.append(
                {
                    "name": name,
                    "server": cluster.server,
                    "description": cluster.description or "",
                    "default_project": cluster.default_project,
                    "is_default": name == default_cluster,
                }
            )

        return {"clusters": clusters, "default_cluster": default_cluster}

    async def whoami(self) -> dict[str, Any]:
        """Get current configuration status."""
        try:
            cluster_config = self._get_cluster_config()
            cluster_name = self.clusters_config.default_cluster or "unknown"

            try:
                self._get_token(cluster_config)
                token_valid = True
            except ValueError:
                token_valid = False

            return {
                "cluster": cluster_name,
                "server": cluster_config.get("server", "unknown"),
                "project": cluster_config.get("default_project", "unknown"),
                "token_valid": token_valid,
                "authenticated": token_valid,
            }
        except ValueError as e:
            return {
                "cluster": "unknown",
                "server": "unknown",
                "project": "unknown",
                "token_valid": False,
                "authenticated": False,
                "error": str(e),
            }

    async def switch_cluster(self, cluster: str) -> dict[str, Any]:
        """Switch to a different cluster context."""
        if cluster not in self.clusters_config.clusters:
            return {
                "switched": False,
                "message": f"Unknown cluster: {cluster}. Use acp_list_clusters to see available clusters.",
            }

        previous_cluster = self.clusters_config.default_cluster
        self.clusters_config.default_cluster = cluster

        return {
            "switched": True,
            "previous": previous_cluster,
            "current": cluster,
            "message": f"Switched from {previous_cluster} to {cluster}",
        }

    async def login(self, cluster: str, token: str | None = None) -> dict[str, Any]:
        """Authenticate to a cluster with a token.

        Sets the token on the cluster config (in memory) and verifies it works.
        """
        if cluster not in self.clusters_config.clusters:
            return {
                "authenticated": False,
                "message": f"Unknown cluster: {cluster}. Use acp_list_clusters to see available clusters.",
            }

        cluster_obj = self.clusters_config.clusters[cluster]

        if token:
            cluster_obj.token = token

        # Verify the token works by calling whoami
        previous = self.clusters_config.default_cluster
        self.clusters_config.default_cluster = cluster

        try:
            cluster_config = self._get_cluster_config(cluster)
            self._get_token(cluster_config)
            return {
                "authenticated": True,
                "cluster": cluster,
                "server": cluster_config["server"],
                "message": f"Successfully authenticated to cluster '{cluster}'",
            }
        except ValueError as e:
            return {"authenticated": False, "cluster": cluster, "message": str(e)}
        finally:
            self.clusters_config.default_cluster = previous

    # ── Cleanup ──────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
