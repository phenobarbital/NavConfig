from typing import Any
import os
import logging
import hvac
from .abstract import AbstractReader


class VaultReader(AbstractReader):
    """VaultReader.

    Description: Class for HashiCorp Vault Reader.
    """

    def __init__(self):
        url = os.getenv('VAULT_HVAC_URL', 'http://localhost:8200')
        token = os.getenv('VAULT_HVAC_TOKEN')
        self._mount = os.getenv('VAULT_HVAC_MOUNT_POINT', 'secret')
        if not token:
            raise ValueError(
                'VAULT_HVAC_TOKEN is not set'
            )
        try:
            self.client = hvac.Client(url=url, token=token)
            self.open()
        except Exception as err: # pylint: disable=W0703
            logging.exception(
                f"Vault Error: {err}", stack_info=True
            )

    def open(self) -> bool:
        if self.client.is_authenticated():
            logging.debug('Hashicorp Vault Connected')
            return True
        return False

    def close(self) -> None:
        pass

    def get(self, key: str, default: Any = None, version: int = None, path: str = 'secrets', sub_key: str = None) -> Any:
        try:
            secret_parts = key.split("/")
            secret_key = secret_parts.pop()
            secret_path = "/".join(secret_parts)
        except ValueError:
            secret_path = path
            secret_key = key
        try:
            response = self.client.secrets.kv.read_secret_version(
                path=secret_path, version=version, mount_point=self._mount
            )
        except hvac.exceptions.InvalidPath as exc:
            # logging.error(
            #      f"Vault Error over key {key}: {exc}"
            # )
            return default
        if secret_key == "*":
            return response['data']['data']

        secret_data = response['data']['data'].get(secret_key, default)
        if sub_key is not None:
            return secret_data.get(sub_key, default)
        return secret_data


    def exists(self, key: str, path: str = 'secrets', version: int = None) -> bool:
        try:
            secret_parts = key.split("/")
            secret_key = secret_parts.pop()
            secret_path = "/".join(secret_parts)
        except ValueError:
            secret_path = path
            secret_key = key
        try:
            response = self.client.secrets.kv.read_secret_version(
                path=secret_path, version=version, mount_point=self._mount
            )
        except hvac.exceptions.InvalidPath as exc:
            # logging.error(
            #     f"Vault Error over key {key}: {exc}"
            # )
            return False
        if secret_key == "*":
            return True
        return secret_key in response['data']['data']

    def set(self, key: str, value: Any, path: str = 'secrets', timeout: int = None, version: int = None) -> None:
        try:
            secret_path, secret_key = key.split("/", 1)
        except ValueError:
            secret_path = path
            secret_key = key
        secret_data = {secret_key: value}
        self.client.secrets.kv.v2.create_or_update_secret(
            path=secret_path, version=version, secret=secret_data, mount_point=self._mount
        )

    def delete(self, key: str, path: str = 'secrets', version: int = None) -> bool:
        try:
            secret_path, secret_key = key.split("/", 1)
        except ValueError:
            secret_path = path
            secret_key = key
        response = self.client.secrets.kv.read_secret_version(
            path=secret_path, version=version, mount_point=self._mount
        )
        if secret_key in response['data']['data']:
            del response['data']['data'][secret_key]
            self.client.secrets.kv.v2.create_or_update_secret(
                path=secret_path, secret=response['data']['data'], mount_point=self._mount
            )
            return True
        return False
