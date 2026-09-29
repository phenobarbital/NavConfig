"""Unit tests for Kardex vault/external-reader integration."""
import pytest

from navconfig import config
from navconfig.kardex import Kardex


class FakeReader:
    enabled = True

    def __init__(self, data=None):
        self.data = data or {}
        self.get_calls = 0
        self.exists_calls = 0

    def get(self, key):
        self.get_calls += 1
        return self.data.get(key)

    def exists(self, key):
        self.exists_calls += 1
        return key in self.data


def _isolate(monkeypatch, readers):
    monkeypatch.setattr(Kardex, "_readers", readers)
    monkeypatch.setattr(config, "_mapping_", {})


def test_kardex_get_external_single_call(monkeypatch):
    reader = FakeReader({"ZZ_KEY": "v"})
    _isolate(monkeypatch, {"vault": reader})
    assert config.get("ZZ_KEY") == "v"
    assert reader.get_calls == 1
    assert reader.exists_calls == 0


def test_kardex_contains_checks_all_readers(monkeypatch):
    first, second = FakeReader(), FakeReader({"ZZ_ONLY_SECOND": "x"})
    _isolate(monkeypatch, {"a": first, "b": second})
    assert "ZZ_ONLY_SECOND" in config
    assert "ZZ_NOPE" not in config


@pytest.mark.asyncio
async def test_kardex_aget_resolution_order(monkeypatch):
    reader = FakeReader({"ZZ_K": "reader", "ZZ_ENV": "reader"})
    _isolate(monkeypatch, {"vault": reader})
    monkeypatch.setenv("ZZ_ENV", "environ")
    monkeypatch.setattr(config, "_mapping_", {"ZZ_K": "mapping"})
    assert await config.aget("ZZ_K") == "mapping"
    assert await config.aget("ZZ_ENV") == "environ"
    assert reader.get_calls == 0
    monkeypatch.setattr(config, "_mapping_", {})
    assert await config.aget("ZZ_K") == "reader"
    assert await config.aget("ZZ_MISSING", fallback="fb") == "fb"
    assert await config.aexists("ZZ_K") is True
    assert await config.aexists("ZZ_MISSING") is False


@pytest.mark.asyncio
async def test_kardex_aload_vault_disabled(monkeypatch):
    _isolate(monkeypatch, {})
    assert await config.aload_vault(["x"]) == {}
    config.invalidate_vault_cache()  # no-op, must not raise


# --- end-to-end: Kardex over a real VaultReader with a counting fake hvac ---

import copy  # noqa: E402
import threading  # noqa: E402

import hvac  # noqa: E402

from navconfig.readers import vault_cache  # noqa: E402
from navconfig.readers.vault import VaultReader  # noqa: E402


class _State:
    def __init__(self):
        self.store = {"dev": {"VK": "vault-value"}}
        self.reads = {}
        self.lock = threading.Lock()

    @property
    def total(self):
        return sum(self.reads.values())


@pytest.fixture
def vault_env(monkeypatch):
    state = _State()

    class KV2:
        def read_secret_version(self, path, mount_point=None):
            with state.lock:
                state.reads[path] = state.reads.get(path, 0) + 1
                if path not in state.store:
                    raise hvac.exceptions.InvalidPath()
                return {"data": {"data": copy.deepcopy(state.store[path])}}

        def create_or_update_secret(self, path, secret, mount_point=None):
            with state.lock:
                state.store[path] = dict(secret)

    class Client:
        def __init__(self, url=None, token=None):
            self.secrets = type(
                "S", (), {"kv": type("K", (), {"v2": KV2()})()}
            )()

        def is_authenticated(self):
            return True

    monkeypatch.setattr(hvac, "Client", Client)
    for k, v in (("VAULT_TOKEN", "t"), ("VAULT_URL", "http://v.test"),
                 ("VAULT_ENV", "dev"), ("VAULT_VERSION", "2")):
        monkeypatch.setenv(k, v)
    vault_cache._reset_document_cache()
    monkeypatch.setattr(Kardex, "_mapping_", {})
    monkeypatch.setattr(config, "_mapping_", {})
    monkeypatch.setattr(config, "_use_vault", True, raising=False)
    monkeypatch.setattr(Kardex, "_readers", {"vault": VaultReader()})
    yield state
    vault_cache._reset_document_cache()


def test_e2e_get_one_read_then_zero(vault_env):
    assert config.get("VK") == "vault-value"
    assert vault_env.total == 1
    assert config.get("VK") == "vault-value"
    assert vault_env.total == 1


def test_e2e_missing_key_at_most_one_read(vault_env):
    assert config.exists("ZZ_ABSENT") is False
    assert ("ZZ_ABSENT" in config) is False
    assert config.get("ZZ_ABSENT") is None
    assert vault_env.total == 1


def test_e2e_startup_loader_and_kardex_share_read(vault_env, monkeypatch):
    # a second reader (as vaultLoader builds), URL differing by trailing slash
    monkeypatch.setenv("VAULT_URL", "http://v.test/")
    other = VaultReader()
    assert other.list(path="dev") == {"VK": "vault-value"}
    assert config.get("VK") == "vault-value"
    assert vault_env.total == 1


@pytest.mark.asyncio
async def test_e2e_aload_vault_then_sync_get_zero_reads(vault_env):
    assert await config.aload_vault(["dev"]) == {"dev": True}
    before = vault_env.total
    assert config.get("VK") == "vault-value"
    assert vault_env.total == before == 1


@pytest.mark.asyncio
async def test_e2e_aget_aexists_real_reader(vault_env):
    assert await config.aget("VK") == "vault-value"
    assert await config.aexists("VK") is True
    assert await config.aexists("ZZ_ABSENT") is False
    assert vault_env.total == 1


def test_e2e_invalidate_vault_cache_forces_reread(vault_env):
    config.get("VK")
    config.invalidate_vault_cache()
    config.get("VK")
    assert vault_env.total == 2
