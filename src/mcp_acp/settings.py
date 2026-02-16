"""Configuration settings for MCP-ACP server.

Uses Pydantic BaseSettings for type-safe configuration with validation.
"""

from pathlib import Path

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from utils.pylogger import get_python_logger

logger = get_python_logger()


class ClusterConfig(BaseSettings):
    """Configuration for a single OpenShift cluster.

    Attributes:
        server: OpenShift API server URL
        default_project: Default project/namespace to use
        description: Optional human-readable description
    """

    server: str = Field(
        ...,
        description="OpenShift API server URL",
        json_schema_extra={"example": "https://api.cluster.example.com:6443"},
    )
    default_project: str = Field(
        ...,
        description="Default project/namespace for operations",
        json_schema_extra={"example": "my-workspace"},
    )
    description: str | None = Field(
        default=None,
        description="Human-readable cluster description",
        json_schema_extra={"example": "Production cluster"},
    )

    @field_validator("server")
    @classmethod
    def validate_server_url(cls, v: str) -> str:
        """Validate server URL format."""
        if not v.startswith(("https://", "http://")):
            raise ValueError("Server URL must start with https:// or http://")
        return v

    @field_validator("default_project")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        """Validate project name follows DNS-1123 rules."""
        if not v:
            raise ValueError("default_project cannot be empty")
        if len(v) > 63:
            raise ValueError("default_project must be 63 characters or less")
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("default_project must contain only alphanumeric characters, hyphens, or underscores")
        return v


class ClustersConfig(BaseSettings):
    """Configuration for all OpenShift clusters.

    Attributes:
        clusters: Dictionary of cluster configurations
        default_cluster: Name of the default cluster to use
    """

    clusters: dict[str, ClusterConfig] = Field(
        default_factory=dict,
        description="Map of cluster names to configurations",
    )
    default_cluster: str | None = Field(
        default=None,
        description="Name of the default cluster",
    )

    @field_validator("default_cluster")
    @classmethod
    def validate_default_cluster(cls, v: str | None, info) -> str | None:
        """Ensure default_cluster exists in clusters."""
        if v is not None:
            clusters = info.data.get("clusters", {})
            if v not in clusters:
                raise ValueError(f"default_cluster '{v}' not found in clusters: {list(clusters.keys())}")
        return v

    @classmethod
    def from_yaml(cls, path: Path) -> "ClustersConfig":
        """Load configuration from YAML file.

        Args:
            path: Path to clusters.yaml file

        Returns:
            Validated ClustersConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Cluster configuration not found: {path}")

        try:
            with open(path) as f:
                data = yaml.safe_load(f)

            if not data:
                raise ValueError("Cluster configuration is empty")

            # Convert cluster configs to ClusterConfig objects
            clusters_data = data.get("clusters", {})
            clusters = {}
            for name, config in clusters_data.items():
                try:
                    clusters[name] = ClusterConfig(**config)
                except Exception as e:
                    logger.error(
                        "cluster_config_invalid",
                        cluster=name,
                        error=str(e),
                    )
                    raise ValueError(f"Invalid config for cluster '{name}': {e}") from e

            return cls(
                clusters=clusters,
                default_cluster=data.get("default_cluster"),
            )

        except yaml.YAMLError as e:
            logger.error("yaml_parse_error", path=str(path), error=str(e))
            raise ValueError(f"Failed to parse YAML: {e}") from e
        except Exception as e:
            logger.error("config_load_error", path=str(path), error=str(e))
            raise


class Settings(BaseSettings):
    """Global settings for MCP-ACP server.

    Attributes:
        config_path: Path to clusters.yaml configuration file
        log_level: Logging level
        timeout_default: Default timeout for oc commands (seconds)
        max_log_lines: Maximum log lines to retrieve
        max_file_size: Maximum file size for exports (bytes)
    """

    config_path: Path = Field(
        default=Path.home() / ".config" / "acp" / "clusters.yaml",
        description="Path to cluster configuration file",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        json_schema_extra={"enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
    )
    timeout_default: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Default timeout for oc commands (seconds)",
    )
    max_log_lines: int = Field(
        default=10000,
        ge=1,
        le=100000,
        description="Maximum log lines to retrieve",
    )
    max_file_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        ge=1024,
        le=100 * 1024 * 1024,  # 100MB
        description="Maximum file size for exports (bytes)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    model_config = SettingsConfigDict(
        env_prefix="MCP_ACP_",
        case_sensitive=False,
    )


def load_settings() -> Settings:
    """Load and validate global settings.

    Returns:
        Validated Settings instance
    """
    return Settings()


def load_clusters_config(settings: Settings | None = None) -> ClustersConfig:
    """Load and validate cluster configuration.

    Args:
        settings: Optional Settings instance. If not provided, loads default settings.

    Returns:
        Validated ClustersConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if settings is None:
        settings = load_settings()

    return ClustersConfig.from_yaml(settings.config_path)


# Global settings instance
settings = load_settings()
