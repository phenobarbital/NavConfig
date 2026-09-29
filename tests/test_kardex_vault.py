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
