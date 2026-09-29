"""Unit tests for the cache-through VaultReader."""
import copy
import threading

import hvac
import pytest

from navconfig.readers import vault_cache
from navconfig.readers.vault import VaultReader


class _KV2:
    def __init__(self, owner):
        self.o = owner

    def read_secret_version(self, path, mount_point=None):
        with self.o.lock:
            self.o.reads[path] = self.o.reads.get(path, 0) + 1
            if self.o.fail_next:
                self.o.fail_next = False
                raise RuntimeError("transient")
            if path not in self.o.store:
                raise hvac.exceptions.InvalidPath()
            return {"data": {"data": copy.deepcopy(self.o.store[path])}}

    def create_or_update_secret(self, path, secret, mount_point=None):
        with self.o.lock:
            self.o.store[path] = dict(secret)


class _Secrets:
    def __init__(self, owner):
        self.kv = type("KV", (), {"v2": _KV2(owner)})()


class FakeState:
    def __init__(self):
        self.store = {}
        self.reads = {}
        self.fail_next = False
        self.lock = threading.Lock()

    @property
    def total(self):
        return sum(self.reads.values())


@pytest.fixture(autouse=True)
def fresh_cache():
    vault_cache._reset_document_cache()
    yield
    vault_cache._reset_document_cache()


@pytest.fixture
def fake_hvac(monkeypatch):
    state = FakeState()

    class FakeClient:
        def __init__(self, url=None, token=None):
            self.secrets = _Secrets(state)

        def is_authenticated(self):
            return True

    monkeypatch.setattr(hvac, "Client", FakeClient)
    monkeypatch.setenv("VAULT_TOKEN", "tok")
    monkeypatch.setenv("VAULT_URL", "http://vault.test")
    monkeypatch.setenv("VAULT_ENV", "dev")
    monkeypatch.setenv("VAULT_VERSION", "2")
    state.store["dev"] = {"A": "1", "D": {"x": 1}}
    return state


def test_reader_get_exists_one_fetch(fake_hvac):
    r = VaultReader()
    assert r.exists("A") is True
    assert r.get("A") == "1"
    assert r.list() == {"A": "1", "D": {"x": 1}}
    assert fake_hvac.total == 1


def test_reader_shared_cache_across_instances(fake_hvac):
    assert VaultReader().get("A") == "1"
    assert VaultReader().get("A") == "1"
    assert fake_hvac.total == 1


def test_reader_different_token_not_shared(fake_hvac, monkeypatch):
    VaultReader().get("A")
    monkeypatch.setenv("VAULT_TOKEN", "other")
    VaultReader().get("A")
    assert fake_hvac.total == 2


def test_reader_missing_path_cached(fake_hvac):
    r = VaultReader()
    assert r.get("nope/KEY", default="d") == "d"
    assert r.exists("nope/KEY") is False
    assert r.get("nope/KEY", default="d") == "d"
    assert fake_hvac.reads["nope"] == 1


def test_reader_transient_error_not_cached(fake_hvac):
    r = VaultReader()
    fake_hvac.fail_next = True
    assert r.get("A", default="d") == "d"
    assert r.get("A", default="d") == "1"
    assert fake_hvac.total == 2


def test_reader_split_key_last_slash(fake_hvac):
    r = VaultReader()
    assert r._split_key("a/b/KEY") == ("a/b", "KEY")
    assert r._split_key("KEY") == ("dev", "KEY")
    assert r._split_key("/KEY") == ("dev", "KEY")
    r.set("a/b/KEY", "v")
    assert fake_hvac.store["a/b"] == {"KEY": "v"}
    assert r.get("a/b/KEY") == "v"
    assert r.delete("a/b/KEY") is True
    assert fake_hvac.store["a/b"] == {}
    assert r.exists("a/b/KEY") is False


def test_reader_set_write_through(fake_hvac):
    r = VaultReader()
    r.get("A")
    before = fake_hvac.total
    r.set("B", "2")
    assert r.get("B") == "2"
    assert r.get("A") == "1"
    assert fake_hvac.total == before + 1  # only set's fresh read


def test_reader_list_returns_copy(fake_hvac):
    r = VaultReader()
    doc = r.list()
    doc["A"] = "mutated"
    assert r.get("A") == "1"
    assert r.get("*")["A"] == "1"


@pytest.mark.asyncio
async def test_reader_aget_aexists(fake_hvac):
    r = VaultReader()
    assert await r.aget("A") == r.get("A")
    assert await r.aexists("A") is True
    assert await r.aexists("Z") is False
    assert await r.alist() == r.list()


@pytest.mark.asyncio
async def test_reader_aload_concurrent(fake_hvac):
    fake_hvac.store["a"] = {"k": 1}
    fake_hvac.store["b"] = {"k": 2}
    r = VaultReader()
    res = await r.aload(["a", "b", "missing"])
    assert res == {"a": True, "b": True, "missing": False}
    assert fake_hvac.reads == {"a": 1, "b": 1, "missing": 1}
    assert r.get("a/k") == 1
    assert fake_hvac.reads["a"] == 1


def test_reader_concurrent_set_cache_matches_vault(fake_hvac):
    r = VaultReader()
    threads = [
        threading.Thread(target=r.set, args=(f"K{i}", str(i))) for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert r.list() == fake_hvac.store["dev"]
    assert all(r.get(f"K{i}") == str(i) for i in range(8))


def test_reader_nested_values_are_deep_copied(fake_hvac):
    fake_hvac.store["dev"]["L"] = {"inner": [1, 2]}
    r = VaultReader()
    r.get("L")["inner"].append(3)
    r.get("L", sub_key="inner").append(4)
    r.list()["L"]["inner"].append(5)
    assert r.get("L") == {"inner": [1, 2]}


def test_reader_sub_key_on_missing_key_returns_default(fake_hvac):
    assert VaultReader().get("NOPE", default="d", sub_key="x") == "d"


def test_reader_trailing_slash_url_shares_cache(fake_hvac, monkeypatch):
    VaultReader().get("A")
    monkeypatch.setenv("VAULT_URL", "http://vault.test/")
    VaultReader().get("A")
    assert fake_hvac.total == 1


def test_reader_delete_honours_secret_path(fake_hvac):
    fake_hvac.store["other"] = {"K": "v", "J": "w"}
    r = VaultReader()
    assert r.delete("K", secret_path="other") is True
    assert fake_hvac.store["other"] == {"J": "w"}
