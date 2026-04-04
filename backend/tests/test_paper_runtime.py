from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
PAPER_PACKAGE_ROOT = ROOT / "custom_agents" / "paper"
if str(PAPER_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PAPER_PACKAGE_ROOT))

from paper.core.runtime import resolve_linux_native_path
from paper.core.execution import AsposeExecutionAgent


def _runtime_host(tmp_path: Path) -> SimpleNamespace:
    script_dir = tmp_path / "paper-root"
    managed_dir = script_dir / "lib"
    native_dir = tmp_path / "missing-native"
    managed_dir.mkdir(parents=True, exist_ok=True)
    native_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        script_dir=str(script_dir),
        managed_dir=str(managed_dir),
        native_dir=str(native_dir),
        system="linux",
    )


def test_resolve_linux_native_path_prefers_existing_candidate(tmp_path: Path, monkeypatch):
    host = _runtime_host(tmp_path)
    expected_native = Path(host.managed_dir) / "libSkiaSharp.so"
    expected_native.write_bytes(b"test")
    monkeypatch.delenv("ASPOSE_NATIVE_DIR", raising=False)

    resolved = resolve_linux_native_path(host)

    assert resolved == str(expected_native)
    assert host.native_dir == str(Path(host.managed_dir))
    assert os.environ["ASPOSE_NATIVE_DIR"] == str(Path(host.managed_dir))


def test_resolve_linux_native_path_bootstraps_when_missing(tmp_path: Path, monkeypatch):
    host = _runtime_host(tmp_path)
    bootstrapped = tmp_path / "bootstrapped" / "libSkiaSharp.so"
    bootstrapped.parent.mkdir(parents=True, exist_ok=True)
    bootstrapped.write_bytes(b"boot")
    monkeypatch.delenv("ASPOSE_NATIVE_DIR", raising=False)
    monkeypatch.setattr("paper.core.runtime._bootstrap_linux_native_dependency", lambda runtime_host: str(bootstrapped))

    resolved = resolve_linux_native_path(host)

    assert resolved == str(bootstrapped)
    assert host.native_dir == str(bootstrapped.parent)
    assert os.environ["ASPOSE_NATIVE_DIR"] == str(bootstrapped.parent)


def test_aspose_execution_agent_binds_cached_runtime_to_new_instances(monkeypatch):
    runtime_exports = {
        "SystemModule": object(),
        "SystemDrawingModule": object(),
        "License": object(),
        "Document": object(),
        "LayoutCollector": object(),
        "NodeType": object(),
        "SaveFormat": object(),
        "ImportFormatMode": object(),
        "Run": object(),
        "Paragraph": object(),
    }
    monkeypatch.setattr("paper.core.execution.load_dependencies", lambda host, caller_globals: [setattr(host, key, value) for key, value in runtime_exports.items()])
    monkeypatch.setattr("paper.core.execution.AsposeExecutionAgent._runtime_ready", False)
    monkeypatch.setattr("paper.core.execution.AsposeExecutionAgent._runtime_exports", {})
    monkeypatch.setattr("paper.core.execution.AsposeExecutionAgent._preferred_width", None)
    monkeypatch.setattr("paper.core.execution.AsposeExecutionAgent._license_loaded", False)

    first = AsposeExecutionAgent()
    second = AsposeExecutionAgent()

    assert first.Document is runtime_exports["Document"]
    assert second.Document is runtime_exports["Document"]
