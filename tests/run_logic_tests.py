"""无依赖逻辑测试运行器（不需 NEKO 宿主环境 / 不走 plugin 包链）。

用法：uv run python tests/run_logic_tests.py
把 neko_warthunder 注册为轻量顶层包，按文件路径加载 test_*.py 并执行其 test_* 函数。
（标准 CI 仍可 `uv run pytest -c tests/pytest.ini tests -q`，conftest 做同样的桩。）
"""

from __future__ import annotations

import importlib.util
import asyncio
import contextlib
import inspect
import pathlib
import sys
import tempfile
import traceback
import types

_TESTS_DIR = pathlib.Path(__file__).resolve().parent
_PLUGIN_DIR = _TESTS_DIR.parent

if "neko_warthunder" not in sys.modules:
    _pkg = types.ModuleType("neko_warthunder")
    _pkg.__path__ = [str(_PLUGIN_DIR)]  # type: ignore[attr-defined]
    sys.modules["neko_warthunder"] = _pkg


def _load(path: pathlib.Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("wt_" + path.stem, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run_test_function(fn) -> None:
    signature = inspect.signature(fn)
    with contextlib.ExitStack() as stack:
        kwargs = {}
        for param in signature.parameters.values():
            if param.name == "tmp_path":
                tmp_dir = stack.enter_context(tempfile.TemporaryDirectory())
                kwargs[param.name] = pathlib.Path(tmp_dir)
                continue
            if param.default is not inspect.Parameter.empty:
                continue
            raise TypeError(f"unsupported test fixture: {param.name}")
        result = fn(**kwargs)
        if inspect.isawaitable(result):
            asyncio.run(result)


def main() -> int:
    results: list[tuple[str, str]] = []
    for f in sorted(_TESTS_DIR.glob("test_*.py")):
        mod = _load(f)
        for name in sorted(vars(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            label = f"{f.stem}.{name}"
            try:
                _run_test_function(fn)
                results.append(("PASS", label))
            except Exception:
                results.append(("FAIL", label))
                print(f"--- FAIL {label} ---")
                traceback.print_exc()
    passed = sum(1 for r, _ in results if r == "PASS")
    print()
    for r, label in results:
        print(f"{r}  {label}")
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
