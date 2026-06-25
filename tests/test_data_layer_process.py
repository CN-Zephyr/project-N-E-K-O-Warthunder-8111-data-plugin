"""Data-layer process ownership contracts for L8 orchestration."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from neko_warthunder.adapters.data_layer_process import DataLayerProcessManager
from neko_warthunder.core.contracts import WtConfig


class FakeProcess:
    def __init__(self) -> None:
        self.pid = 4321
        self.terminated = False
        self.killed = False
        self.waited = False

    def poll(self):
        return None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout=None):
        self.waited = True
        return 0


def _fake_plugin_root() -> TemporaryDirectory[str]:
    temp = TemporaryDirectory()
    root = Path(temp.name)
    data_process = root / "data_layer" / "data process"
    data_process.mkdir(parents=True)
    (data_process / "wt_server.py").write_text("# fake server\n", encoding="utf-8")
    return temp


def test_external_data_layer_is_not_terminated_on_shutdown():
    cfg = WtConfig(data_layer_auto_start=True)
    launched: list[Any] = []

    with _fake_plugin_root() as root:
        manager = DataLayerProcessManager(
            cfg,
            plugin_root=Path(root),
            health_check=lambda _url, _timeout: True,
            popen_factory=lambda *args, **kwargs: launched.append((args, kwargs)),
        )

        status = manager.start_if_needed()
        manager.stop()

    assert status["mode"] == "external"
    assert status["started_by_plugin"] is False
    assert status["health"] is True
    assert launched == []
    assert manager.snapshot()["mode"] == "external"


def test_missing_data_layer_is_started_and_owned_by_plugin():
    cfg = WtConfig(data_layer_auto_start=True, data_layer_url="http://127.0.0.1:8112")
    checks = iter([False, True])
    proc = FakeProcess()
    launched: list[list[str]] = []

    with _fake_plugin_root() as root:
        manager = DataLayerProcessManager(
            cfg,
            plugin_root=Path(root),
            health_check=lambda _url, _timeout: next(checks),
            popen_factory=lambda args, **_kwargs: launched.append(list(args)) or proc,
            sleep=lambda _seconds: None,
        )

        status = manager.start_if_needed()
        manager.stop()

    assert status["mode"] == "managed"
    assert status["pid"] == 4321
    assert status["started_by_plugin"] is True
    assert launched
    assert launched[0][-3:] == ["wt_server.py", "--port", "8112"]
    assert proc.terminated is True
    assert proc.waited is True
    assert proc.killed is False


def test_data_layer_auto_start_can_be_disabled():
    cfg = WtConfig(data_layer_auto_start=False)

    with _fake_plugin_root() as root:
        manager = DataLayerProcessManager(
            cfg,
            plugin_root=Path(root),
            health_check=lambda _url, _timeout: False,
        )

        status = manager.start_if_needed()

    assert status["mode"] == "missing"
    assert status["started_by_plugin"] is False
    assert status["health"] is False
