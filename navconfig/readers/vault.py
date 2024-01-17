from typing import Any
import os
import logging
import hvac
from ..exceptions import ReaderNotSet
from .abstract import AbstractReader
import urllib3


# Disable warnings for insecure requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("urllib3").setLevel(logging.WARNING)

class VaultReader(AbstractReader):
    """VaultReader.

    Description: Class for HashiCorp Vault Reader.
    """

    def __init__(self, env: str = None) -> None:
        url = os.getenv(
            "VAULT_HVAC_URL",
            "http://localhost:8200"
        )
        token = os.getenv("VAULT_HVAC_TOKEN")
        self.version = int(os.getenv("VAULT_HVAC_VERSION", 1))
        self._mount = os.getenv("VAULT_HVAC_MOUNT_POINT", "navigator")
        self._env = env
        if not self._env:
            self._env = os.getenv("ENV", "")
        if not token:
            raise ValueError("VAULT_HVAC_TOKEN is not set")
        try:
            self.client = hvac.Client(url=url, token=token)
            self.open()
        except Exception as err:  # pylint: disable=W0703
            self.enabled = False
            raise ReaderNotSet(f"Vault Error: {err}")

    def open(self) -> bool:
        if self.client.is_authenticated():
            logging.debug("Hashicorp Vault Connected")
            return True
        return False

    def close(self) -> None:
        pass

    def get(
        self,
        key: str,
        default: Any = None,
        path: str = "secrets",
        sub_key: str = None,
    ) -> Any:
        if self.enabled is False:
            raise ReaderNotSet()
        data = {}
        try:
            secret_parts = key.split("/")
            secret_key = secret_parts.pop()
            secret_path = "/".join(secret_parts)
            if not secret_path:
                secret_path = self._env
        except ValueError:
            secret_path = self._env
            secret_key = key
        try:
            if self.version == 1:
                print('GET > ', secret_path, self._mount)
                response = self.client.secrets.kv.v1.read_secret(
                    path=secret_path, mount_point=self._mount
                )
                data = response["data"]
            elif self.version == 2:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=secret_path, mount_point=self._mount
                )
                data = response["data"]["data"]
        except hvac.exceptions.InvalidPath:
            return default

        if secret_key == "*":
            return data

        secret_data = data.get(secret_key, default)
        if sub_key is not None:
            return secret_data.get(sub_key, default)
        return secret_data

    def exists(
        self,
        key: str,
    ) -> bool:
        if self.enabled is False:
            raise ReaderNotSet()
        data = {}
        try:
            secret_parts = key.split("/")
            secret_key = secret_parts.pop()
            secret_path = "/".join(secret_parts)
            if not secret_path:
                secret_path = self._env
        except ValueError:
            secret_path = self._env
            secret_key = key
        try:
            if self.version == 1:
                response = self.client.secrets.kv.v1.read_secret(
                    path=secret_path, mount_point=self._mount
                )
                data = response["data"]
            elif self.version == 2:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=secret_path, mount_point=self._mount
                )
                data = response["data"]["data"]
        except hvac.exceptions.InvalidPath:
            return False
        if secret_key == "*":
            return True
        return secret_key in data

    def set(
        self,
        key: str,
        value: Any,
        **kwargs
    ) -> None:
        if self.enabled is False:
            raise ReaderNotSet()
        try:
            secret_path, secret_key = key.split("/", 1)
            if not secret_path:
                secret_path = self._env
        except ValueError:
            secret_path = self._env
            secret_key = key
        try:
            if self.version == 1:
                # Read the existing secret data
                existing_data = {}
                try:
                    read_response = self.client.secrets.kv.v1.read_secret(
                        path=secret_path, mount_point=self._mount
                    )
                    existing_data = read_response['data']
                except hvac.exceptions.InvalidPath:
                    # If the path doesn't exist yet, it's fine
                    pass

                # Update the existing data with the new key-value pair
                existing_data[secret_key] = value

                # Write the updated data back to the path
                self.client.secrets.kv.v1.create_or_update_secret(
                    path=secret_path,
                    secret=existing_data,
                    mount_point=self._mount,
                )
            elif self.version == 2:
                # For KV v2, you need to provide the full data for the path
                # Fetch existing data if you want to preserve other keys
                existing_data = {}
                try:
                    read_response = self.client.secrets.kv.v2.read_secret_version(
                        path=secret_path, mount_point=self._mount
                    )
                    existing_data = read_response['data']['data']
                except hvac.exceptions.InvalidPath:
                    # If the path doesn't exist yet, it's fine
                    pass

                # Update the existing data with the new key-value pair
                existing_data[secret_key] = value

                # Write the updated data back to the path
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=secret_path,
                    secret=existing_data,
                    mount_point=self._mount
                )
        except Exception as ex:
            raise ValueError(
                f"Error writing to Vault: {ex}"
            )

    def delete(self, key: str, secret_path: str = None) -> bool:
        if self.enabled is False:
            raise ReaderNotSet()  # Or some appropriate exception

        try:
            secret_path, secret_key = key.split("/", 1)
            if not secret_path:
                secret_path = self._env
        except ValueError:
            secret_path = self._env
            secret_key = key

        try:
            if self.version == 1:
                current_secret = self.client.secrets.kv.v1.read_secret(
                    path=secret_path,
                    mount_point=self._mount
                )['data']
                if secret_key in current_secret:
                    del current_secret[secret_key]
                    self.client.secrets.kv.v1.create_or_update_secret(
                        path=secret_path,
                        secret=current_secret,
                        mount_point=self._mount
                    )
            elif self.version == 2:
                current_secret = self.client.secrets.kv.v2.read_secret_version(
                    path=secret_path,
                    mount_point=self._mount
                )['data']['data']
                if secret_key in current_secret:
                    del current_secret[secret_key]
                    self.client.secrets.kv.v2.create_or_update_secret(
                        path=secret_path,
                        secret=current_secret,
                        mount_point=self._mount
                    )
            return True
        except Exception as e:
            logging.warning(
                f"Error deleting key '{key}' from '{secret_path}': {e}"
            )
            return False

    def list(self, path: str = None, filter: str = None) -> list:
        if self.enabled is False:
            raise ReaderNotSet()
        data = {}
        secret_path = path if path else self._env
        try:
            if self.version == 1:
                response = self.client.secrets.kv.v1.read_secret(
                    path=secret_path, mount_point=self._mount
                )
                data = response["data"]
            elif self.version == 2:
                response = self.client.secrets.kv.v2.list_secrets(
                    path=secret_path, mount_point=self._mount
                )
                data = response["data"]["data"]
            else:
                raise ValueError("Invalid KV version specified")

            result = data
            if filter:
                result = {
                    k: v for k, v in data.items() if k.startswith(filter)
                }
            return result

        except hvac.exceptions.InvalidPath as ex:
            return {}
        except Exception as e:
            print(f"Error listing keys at path '{secret_path}': {e}")
            return {}
