"""
Environment configuration loader for GitHub v1 integration.
Automatically loads credentials from .env files and environment variables.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from loguru import logger


class EnvironmentLoader:
    """Loads configuration from environment files and environment variables."""

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the environment loader.

        Args:
            project_root: Root directory to search for .env files.
                         Defaults to current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self._config_cache: Optional[Dict[str, Any]] = None
        self._load_env_files()

    def _load_env_files(self) -> None:
        """Load environment files in order of precedence."""
        # List of env files to check, in order of precedence (later files override earlier)
        env_files = [
            self.project_root / ".env",
            self.project_root / ".env.local",
            self.project_root / "config.env",
            self.project_root / ".env.development",
        ]

        loaded_files = []
        for env_file in env_files:
            if env_file.exists():
                load_dotenv(env_file, override=True)
                loaded_files.append(str(env_file))
                logger.debug(f"Loaded environment from: {env_file}")

        if loaded_files:
            logger.info(f"Environment loaded from: {', '.join(loaded_files)}")
        else:
            logger.info("No .env files found, using system environment variables only")

    def get_config(self) -> Dict[str, Any]:
        """
        Get the complete configuration from environment variables.

        Returns:
            Dictionary containing all configuration values
        """
        if self._config_cache is not None:
            return self._config_cache

        config = {
            # Port.io Configuration
            "port": {
                "client_id": self._get_env("OCEAN__PORT__CLIENT_ID"),
                "client_secret": self._get_env("OCEAN__PORT__CLIENT_SECRET"),
                "base_url": self._get_env(
                    "OCEAN__PORT__BASE_URL", "https://api.getport.io"
                ),
            },
            # Integration Configuration
            "integration": {
                "identifier": self._get_env(
                    "OCEAN__INTEGRATION__IDENTIFIER", "github-integration"
                ),
                "type": self._get_env("OCEAN__INTEGRATION__TYPE", "github"),
                "event_listener_type": self._get_env(
                    "OCEAN__INTEGRATION__EVENT_LISTENER__TYPE", "POLLING"
                ),
            },
            # GitHub Configuration
            "github": {
                "token": self._get_env("OCEAN__INTEGRATION__CONFIG__GITHUB_TOKEN"),
                "host": self._get_env(
                    "OCEAN__INTEGRATION__CONFIG__GITHUB_HOST", "https://api.github.com"
                ),
            },
            # Optional Configuration
            "log_level": self._get_env("OCEAN__LOG_LEVEL", "INFO"),
        }

        # Validate required configuration
        self._validate_config(config)

        # Cache the config
        self._config_cache = config
        return config

    def _get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable with optional default."""
        value = os.getenv(key, default)
        if value and value != default:
            logger.debug(f"Loaded {key} from environment")
        return value

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate that required configuration is present."""
        required_fields = [
            ("port.client_id", config["port"]["client_id"]),
            ("port.client_secret", config["port"]["client_secret"]),
            ("github.token", config["github"]["token"]),
        ]

        missing_fields = []
        for field_name, field_value in required_fields:
            if not field_value or field_value in [
                "your-port-client-id-here",
                "your-port-client-secret-here",
                "your-github-personal-access-token-here",
                "your-github-token-here",
            ]:
                missing_fields.append(field_name)

        if missing_fields:
            logger.error(f"Missing required configuration: {', '.join(missing_fields)}")
            logger.error("Please check your .env file or environment variables")
            raise ValueError(
                f"Missing required configuration: {', '.join(missing_fields)}"
            )

    def get_github_config(self) -> Dict[str, Any]:
        """Get GitHub-specific configuration."""
        config = self.get_config()
        return {
            "githubToken": config["github"]["token"],
            "githubHost": config["github"]["host"],
        }

    def get_port_config(self) -> Dict[str, Any]:
        """Get Port.io-specific configuration."""
        config = self.get_config()
        return config["port"]

    def setup_environment_variables(self) -> None:
        """Set up environment variables for Ocean framework."""
        config = self.get_config()

        # Set Ocean environment variables
        os.environ["OCEAN__PORT__CLIENT_ID"] = config["port"]["client_id"]
        os.environ["OCEAN__PORT__CLIENT_SECRET"] = config["port"]["client_secret"]
        os.environ["OCEAN__PORT__BASE_URL"] = config["port"]["base_url"]

        os.environ["OCEAN__INTEGRATION__IDENTIFIER"] = config["integration"][
            "identifier"
        ]
        os.environ["OCEAN__INTEGRATION__TYPE"] = config["integration"]["type"]
        os.environ["OCEAN__INTEGRATION__EVENT_LISTENER__TYPE"] = config["integration"][
            "event_listener_type"
        ]

        os.environ["OCEAN__INTEGRATION__CONFIG__GITHUB_TOKEN"] = config["github"][
            "token"
        ]
        os.environ["OCEAN__INTEGRATION__CONFIG__GITHUB_HOST"] = config["github"]["host"]

        os.environ["OCEAN__LOG_LEVEL"] = config["log_level"]

        logger.debug("Environment variables set for Ocean framework")


# Global environment loader instance
_env_loader: Optional[EnvironmentLoader] = None


def get_env_loader() -> EnvironmentLoader:
    """Get the global environment loader instance."""
    global _env_loader
    if _env_loader is None:
        _env_loader = EnvironmentLoader()
    return _env_loader


def load_config() -> Dict[str, Any]:
    """Load configuration from environment files and variables."""
    return get_env_loader().get_config()


def setup_environment() -> None:
    """Set up environment variables for the Ocean framework."""
    get_env_loader().setup_environment_variables()
