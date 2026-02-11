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
        """Make an HTTP request to the public API."""
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

    async def list_sessions(
        self,
        project: str,
        status: str | None = None,
        older_than: str | None = None,
        sort_by: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List sessions with filtering.

        Args:
            project: Project/namespace name
            status: Filter by status (running, stopped, creating, failed)
            older_than: Filter by age (e.g., "7d", "24h")
            sort_by: Sort field (created, stopped, name)
            limit: Maximum results
        """
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

    async def get_session(self, project: str, session: str) -> dict[str, Any]:
        """Get a session by ID.

        Args:
            project: Project/namespace name
            session: Session ID
        """
        self._validate_input(project, "project")
        self._validate_input(session, "session")

        return await self._request("GET", f"/v1/sessions/{session}", project)

    async def delete_session(self, project: str, session: str, dry_run: bool = False) -> dict[str, Any]:
        """Delete a session.

        Args:
            project: Project/namespace name
            session: Session name
            dry_run: Preview without deleting
        """
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

    async def bulk_delete_sessions(self, project: str, sessions: list[str], dry_run: bool = False) -> dict[str, Any]:
        """Delete multiple sessions (max 3).

        Args:
            project: Project/namespace name
            sessions: List of session names
            dry_run: Preview without deleting
        """
        self._validate_bulk_operation(sessions, "delete")

        success = []
        failed = []
        dry_run_info = {"would_execute": [], "skipped": []}

        for session in sessions:
            result = await self.delete_session(project, session, dry_run=dry_run)

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
                if result.get("deleted"):
                    success.append(session)
                else:
                    failed.append({"session": session, "error": result.get("message")})

        response = {"deleted": success, "failed": failed}
        if dry_run:
            response["dry_run"] = True
            response["dry_run_info"] = dry_run_info

        return response

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
        """Switch to a different cluster context.

        Args:
            cluster: Cluster alias name
        """
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

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
