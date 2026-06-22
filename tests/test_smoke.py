"""Repository smoke tests for the standalone plugin package."""

from __future__ import annotations

import pathlib
import tomllib


_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _manifest() -> dict:
    return tomllib.loads((_ROOT / "plugin.toml").read_text(encoding="utf-8"))


def test_plugin_manifest_declares_expected_entrypoint_and_runtime():
    manifest = _manifest()

    assert manifest["plugin"]["id"] == "neko_warthunder"
    assert manifest["plugin"]["entry"] == "plugin.plugins.neko_warthunder:NekoWarthunderPlugin"
    assert manifest["plugin_runtime"]["enabled"] is True
    assert manifest["neko_warthunder"]["dry_run"] is True


def test_plugin_manifest_declares_hosted_ui_surface_and_files_exist():
    manifest = _manifest()
    panels = manifest["plugin"]["ui"]["panel"]

    assert manifest["plugin"]["ui"]["enabled"] is True
    assert panels == [
        {
            "id": "main",
            "title": "战雷猫娘副驾驶",
            "entry": "ui/panel.tsx",
            "context": "dashboard",
            "permissions": ["state:read", "action:call"],
        }
    ]
    assert (_ROOT / "__init__.py").is_file()
    assert (_ROOT / "ui" / "panel.tsx").is_file()
