# navconfig/loaders/vault.py
"""
Unified Vault + File Loader - Default loader for NavConfig

This loader combines vault and file-based configuration loading:
1. Reads vault credentials from .env files
2. Connects to vault and loads environment-specific secrets
3. Supplements with .env.* files for additional configuration
4. Falls back to file-only loading if vault unavailable
5. Supports multi-file loading (.env, .env.resources, .env.databases, etc.)
"""

import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path, PurePath
from dotenv import load_dotenv, dotenv_values
from .abstract import BaseLoader


def sort_key(path):
    """Sort key for .env files - .env first, then alphabetical."""
    name = path.name
    return "0" if name == ".env" else name


class vaultLoader(BaseLoader):
    """
    Unified Vault + File Loader - Default loader for NavConfig.

    This loader provides seamless integration between HashiCorp Vault and
    traditional .env files with intelligent fallback behavior.

    Loading Strategy:
    1. Load base .env file to get vault credentials and basic config
    2. If vault credentials present, connect to vault
    3. Load environment-specific secrets from vault (vault/{env}/)
    4. Load additional .env.* files to supplement vault data
    5. If vault unavailable, continue with file-only loading

    Environment Structure:
    - Vault: {mount_point}/{env}/* (e.g., navapi/dev/DATABASE_URL)
    - Files: env/{env}/.env, env/{env}/.env.*, etc.
    """

    # Default file patterns for multi-file loading
    DEFAULT_ENV_FILES = [
        ".env",            # Base configuration + vault credentials
        ".env.resources",  # Resource configurations
        ".env.databases",  # Database configurations (non-secret)
        ".env.api",        # API configurations (non-secret)
        ".env.cache",      # Cache configurations
        ".env.local"       # Local overrides (loaded last)
    ]

    def __init__(
        self,
        env_path: PurePath,
        env: str = None,
        override: bool = False,
        create: bool = True,
        file_patterns: List[str] = None,
        auto: bool = False,
        **kwargs
    ) -> None:
        super().__init__(env_path, override, create=create, **kwargs)

        # Environment determination
        self.env = env or os.getenv('ENV', 'dev')

        # File loading configuration
        if auto:
            # Auto-discover .env* files
            if env_files := list(self.env_path.glob(".env*")):
                env_files.sort(key=sort_key)
                self.file_patterns = [file.name for file in env_files]
            else:
                self.file_patterns = self.DEFAULT_ENV_FILES
        else:
            self.file_patterns = file_patterns or self.DEFAULT_ENV_FILES

        # Vault configuration
        self.vault_enabled = False
        self.vault_reader = None
        self.vault_config = {}

        # Tracking
        self.loaded_files = []
        self.vault_data = {}
        self.file_data = {}

    def load_environment(self) -> Dict[str, Any]:
        """
        Main loading method - orchestrates vault + file loading.
        """
        all_data = {}

        # Step 1: Load base .env file first to get vault credentials
        base_env_data = self._load_base_env_file()
        all_data |= base_env_data

        # Step 2: Initialize and load from vault if credentials available
        if vault_data := self._load_from_vault():
            all_data |= vault_data
            self.vault_data = vault_data
            logging.info(f"Loaded {len(vault_data)} variables from vault")

        # Step 3: Load additional .env.* files (excluding base .env)
        file_data = self._load_additional_env_files()

        # Step 4: Merge data with precedence: vault > additional files > base .env
        for key, value in file_data.items():
            if key not in all_data:  # Only add if not in vault or base .env
                all_data[key] = value

        self.file_data = file_data

        # Step 5: Update environment variables
        self._update_environment_variables(all_data)

        logging.debug(
            f"Environment '{self.env}' loaded: "
            f"{len(self.vault_data)} from vault, "
            f"{len(file_data)} from files, "
            f"{len(all_data)} total variables"
        )

        return all_data

    def _load_base_env_file(self) -> Dict[str, Any]:
        """
        Load the base .env file to get vault credentials and basic configuration.
        """
        base_env_path = self.env_path / ".env"
        base_data = {}

        if base_env_path.exists() and base_env_path.stat().st_size > 0:
            try:
                # Load into environment first
                load_dotenv(dotenv_path=base_env_path, override=self.override)

                # Also get as dict for return value
                base_data = dotenv_values(base_env_path)

                self.loaded_files.append(base_env_path)
                logging.debug(f"Loaded base .env file: {base_env_path}")

                # Extract vault configuration
                self._extract_vault_config(base_data)

            except Exception as e:
                logging.warning(f"Error loading base .env file {base_env_path}: {e}")
        else:
            logging.debug(f"No base .env file found at {base_env_path}")

        return base_data

    def _extract_vault_config(self, env_data: Dict[str, Any]) -> None:
        """
        Extract vault configuration from environment data.
        """
        # Check if vault is enabled
        vault_enabled = env_data.get('VAULT_ENABLED', os.getenv('VAULT_ENABLED', ''))
        self.vault_enabled = vault_enabled.lower() in ('true', '1', 'yes')

        if self.vault_enabled:
            self.vault_config = {
                'url': env_data.get('VAULT_URL', os.getenv('VAULT_URL')),
                'token': env_data.get('VAULT_TOKEN', os.getenv('VAULT_TOKEN')),
                'mount_point': env_data.get('VAULT_MOUNT_POINT', os.getenv('VAULT_MOUNT_POINT', 'navigator')),
                'version': int(env_data.get('VAULT_VERSION', os.getenv('VAULT_VERSION', '2'))),
            }

            # Validate required vault config
            if not self.vault_config['url'] or not self.vault_config['token']:
                logging.warning(
                    "Vault enabled but missing VAULT_URL or VAULT_TOKEN, "
                    "falling back to file-only loading"
                )
                self.vault_enabled = False

    def _load_from_vault(self) -> Dict[str, Any]:
        """
        Load environment variables from HashiCorp Vault.
        """
        if not self.vault_enabled:
            return {}

        try:
            # Initialize vault reader
            self._init_vault_reader()

            if not self.vault_reader:
                return {}

            # Load secrets for current environment
            vault_data = self.vault_reader.list(path=self.env)

            if isinstance(vault_data, dict):
                logging.debug(f"Retrieved {len(vault_data)} secrets from vault path: {self.env}")
                return vault_data
            else:
                logging.debug(f"No secrets found in vault path: {self.env}")
                return {}

        except Exception as e:
            logging.warning(f"Vault loading failed: {e}")
            return {}

    def _init_vault_reader(self) -> None:
        """
        Initialize vault reader with current configuration.
        """
        try:
            from ..readers.vault import VaultReader  # noqa: F401

            # Set environment variables for VaultReader
            os.environ['VAULT_URL'] = self.vault_config['url']
            os.environ['VAULT_TOKEN'] = self.vault_config['token']
            os.environ['VAULT_MOUNT_POINT'] = self.vault_config['mount_point']
            os.environ['VAULT_VERSION'] = str(self.vault_config['version'])

            self.vault_reader = VaultReader(env=self.env)
            logging.debug(f"Vault reader initialized for environment: {self.env}")

        except Exception as e:
            logging.warning(
                f"Failed to initialize vault reader: {e}"
            )
            self.vault_reader = None
            self.vault_enabled = False

    def _load_additional_env_files(self) -> Dict[str, Any]:
        """
        Load additional .env.* files (excluding the base .env file).
        """
        additional_data = {}
        additional_patterns = [p for p in self.file_patterns if p != ".env"]

        for file_pattern in additional_patterns:
            file_path = self.env_path / file_pattern

            if file_path.exists() and file_path.is_file():
                try:
                    if file_path.stat().st_size == 0:
                        logging.warning(f"Empty environment file: {file_path}")
                        continue

                    # Load file data
                    file_data = dotenv_values(file_path)

                    # Also load into environment
                    load_dotenv(dotenv_path=file_path, override=self.override)

                    # Merge data
                    additional_data |= file_data

                    self.loaded_files.append(file_path)
                    logging.debug(f"Loaded additional env file: {file_path}")

                except Exception as e:
                    logging.warning(f"Error loading env file {file_path}: {e}")

        return additional_data

    def _update_environment_variables(self, data: Dict[str, Any]) -> None:
        """
        Update os.environ with loaded data (respecting override setting).
        """
        for key, value in data.items():
            if self.override or key not in os.environ:
                os.environ[key] = str(value)

    def get_variable(self, key: str, default: Any = None) -> Any:
        """
        Get a single variable with vault-first, then file fallback.
        """
        # Check vault first
        if self.vault_enabled and self.vault_reader:
            try:
                value = self.vault_reader.get(key)
                if value is not None:
                    return value
            except Exception as e:
                logging.debug(f"Vault lookup failed for {key}: {e}")

        # Check environment
        return os.getenv(key, default)

    def set_environment(self, new_env: str) -> None:
        """
        Switch to a different environment at runtime.
        """
        if new_env == self.env:
            return  # No change needed

        old_env = self.env
        self.env = new_env

        try:
            # Update environment path
            new_env_path = self.env_path.parent / new_env
            if new_env_path.exists():
                self.env_path = new_env_path
            else:
                logging.warning(f"Environment directory does not exist: {new_env_path}")

            # Reload configuration
            self.load_environment()

            logging.info(f"Environment switched from {old_env} to {new_env}")

        except Exception as e:
            # Rollback on error
            self.env = old_env
            logging.error(f"Failed to switch to environment {new_env}: {e}")
            raise

    def get_loaded_files(self) -> List[Path]:
        """Return list of successfully loaded files."""
        return self.loaded_files

    def get_vault_status(self) -> Dict[str, Any]:
        """Get vault connection and loading status."""
        return {
            'enabled': self.vault_enabled,
            'connected': self.vault_reader is not None,
            'config': {k: v for k, v in self.vault_config.items() if k != 'token'},
            'secrets_loaded': len(self.vault_data),
            'environment': self.env
        }

    def save_environment(self):
        """Save current environment (not implemented for vault loader)."""
        raise NotImplementedError(
            "Saving environment not supported by vault loader. "
            "Use vault CLI or API directly to manage secrets."
        )
