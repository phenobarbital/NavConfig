"""Optional event loop integration without requiring uvloop or Windows."""

import asyncio
import builtins
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from navconfig.utils.uvl import install_uvloop


def test_windows_does_not_import_uvloop(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = asyncio.get_event_loop_policy()
    monkeypatch.setattr(sys, "platform", "win32")
    with patch.object(builtins, "__import__", wraps=builtins.__import__) as importer:
        install_uvloop()

    assert all(call.args[0] != "uvloop" for call in importer.call_args_list)
    assert asyncio.get_event_loop_policy() is policy


def test_missing_uvloop_preserves_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = asyncio.get_event_loop_policy()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setitem(sys.modules, "uvloop", None)

    install_uvloop()

    assert asyncio.get_event_loop_policy() is policy


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_available_uvloop_is_installed(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    install = Mock()
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setitem(sys.modules, "uvloop", SimpleNamespace(install=install))

    install_uvloop()

    install.assert_called_once_with()


@pytest.mark.parametrize("available", [False, True])
def test_uvloop_is_lazy_and_automatic(available: bool, tmp_path: Path) -> None:
    """Use a fresh process so earlier imports cannot hide eager activation."""
    script = """
import importlib.abc
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

class UvloopFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    attempts = 0
    install = Mock()

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "uvloop":
            self.attempts += 1
            if not AVAILABLE:
                raise ModuleNotFoundError("uvloop is not installed")
            return importlib.util.spec_from_loader(fullname, self)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.install = self.install

finder = UvloopFinder()
sys.meta_path.insert(0, finder)
import navconfig
assert finder.attempts == 0
assert "uvloop" not in sys.modules

# Simulate a supported platform only after importing platform-sensitive modules.
sys.platform = "linux"
root = Path(sys.argv[1])
navconfig.project_root = lambda _: (root, root)
navconfig.get_env_type = lambda: "file"
navconfig.get_environment = lambda: "dev"
cfg = SimpleNamespace(debug=False, getboolean=Mock(return_value=False),
                      get=Mock(side_effect=lambda key, fallback: fallback))
navconfig.Kardex = Mock(return_value=cfg)
assert navconfig.config is cfg
assert navconfig.bootstrap() is cfg
assert finder.attempts == 1
assert finder.install.call_count == int(AVAILABLE)
"""
    result = subprocess.run(
        [sys.executable, "-c", f"AVAILABLE = {available!r}\n{script}", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
