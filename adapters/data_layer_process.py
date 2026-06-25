"""Optional lifecycle owner for the vendored War Thunder data-layer process."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from ..core.contracts import WtConfig


HealthCheck = Callable[[str, float], bool]
PopenFactory = Callable[..., Any]
SleepFn = Callable[[float], None]


def check_data_layer_health(base_url: str, timeout: float) -> bool:
    url = f"{base_url.rstrip('/')}/health"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= int(getattr(resp, "status", 200)) < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _port_from_url(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.port is not None:
        return str(parsed.port)
    return "443" if parsed.scheme == "https" else "80"


class DataLayerProcessManager:
    """Start and stop only the data-layer process this plugin owns.

    If :8112 is already healthy, it is treated as external and never killed.
    """

    def __init__(
        self,
        config: WtConfig,
        *,
        plugin_root: Path,
        health_check: HealthCheck = check_data_layer_health,
        popen_factory: PopenFactory = subprocess.Popen,
        sleep: SleepFn = time.sleep,
    ) -> None:
        self.config = config
        self.plugin_root = Path(plugin_root)
        self.health_check = health_check
        self.popen_factory = popen_factory
        self.sleep = sleep
        self._process: Any | None = None
        self._mode = "unknown"
        self._started_by_plugin = False
        self._last_error: str | None = None
        self._last_health = False

    def configure(self, config: WtConfig) -> None:
        self.config = config

    def start_if_needed(self) -> dict[str, Any]:
        if self.health_check(self.config.data_layer_url, self.config.http_timeout_seconds):
            self._mode = "external"
            self._started_by_plugin = False
            self._last_health = True
            self._last_error = None
            return self.snapshot()

        self._last_health = False
        if not self.config.data_layer_auto_start:
            self._mode = "missing"
            self._started_by_plugin = False
            self._last_error = None
            return self.snapshot()

        try:
            self._process = self._spawn()
            self._started_by_plugin = True
            self._mode = "starting"
            self._last_error = None
        except Exception as exc:  # noqa: BLE001
            self._process = None
            self._started_by_plugin = False
            self._mode = "failed"
            self._last_error = f"{type(exc).__name__}: {exc}"
            return self.snapshot()

        deadline = time.monotonic() + self.config.data_layer_startup_timeout_seconds
        while time.monotonic() < deadline:
            if self.health_check(self.config.data_layer_url, self.config.http_timeout_seconds):
                self._mode = "managed"
                self._last_health = True
                return self.snapshot()
            if self._process is not None and self._process.poll() is not None:
                self._mode = "failed"
                self._last_error = "process_exited_before_healthy"
                return self.snapshot()
            self.sleep(0.1)

        self._mode = "managed"
        self._last_health = False
        self._last_error = "health_timeout"
        return self.snapshot()

    def stop(self) -> dict[str, Any]:
        if not self._started_by_plugin or self._process is None:
            return self.snapshot()

        proc = self._process
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=self.config.data_layer_shutdown_timeout_seconds)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1.0)
        finally:
            self._process = None
            self._started_by_plugin = False
            self._mode = "stopped"
            self._last_health = False
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        pid = getattr(self._process, "pid", None) if self._process is not None else None
        return {
            "mode": self._mode,
            "url": self.config.data_layer_url,
            "pid": pid,
            "started_by_plugin": self._started_by_plugin,
            "auto_start": self.config.data_layer_auto_start,
            "health": self._last_health,
            "last_error": self._last_error,
        }

    def _spawn(self):
        data_process_dir = self.plugin_root / "data_layer" / "data process"
        script = data_process_dir / "wt_server.py"
        if not script.exists():
            raise FileNotFoundError(str(script))

        cmd = [sys.executable, "wt_server.py", "--port", _port_from_url(self.config.data_layer_url)]
        kwargs: dict[str, Any] = {
            "cwd": str(data_process_dir),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return self.popen_factory(cmd, **kwargs)
