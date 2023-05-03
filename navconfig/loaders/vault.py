import os
import logging
from pathlib import PurePath
from .abstract import BaseLoader
from ..readers.vault import VaultReader


class vaultLoader(BaseLoader):
    """vaultLoader.

    Use to read configuration settings from Hashicorp Vault.
    """
    def __init__(
            self, env_path: PurePath, override: bool = False, create: bool = True, **kwargs) -> None:
        super().__init__(env_path, override, create=create, **kwargs)
        try:
            env = kwargs['env']
        except KeyError:
            env = None
        self._vault = VaultReader()
        self.secret_path = os.getenv('VAULT_HVAC_SECRETS_PATH', 'env_vars')
        if env is not None:
            self.secret_path = f'{env}/{self.secret_path}'


    def load_environment(self):
        # Retrieve the entire secret at the specified path
        secret_data = self._vault.get(f'{self.secret_path}/*')

        # Load the secret data as environment variables
        for key, value in secret_data.items():
            if self.override or key not in os.environ:
                try:
                    os.environ[key] = str(value)
                except (AttributeError, KeyError):
                    logging.warning(
                        f'Vault: Could not set ENV variable {key} with value {value}'
                    )

    def save_environment(self):
        pass
