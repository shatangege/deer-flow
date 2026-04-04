from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime


def _runtime_framework_name() -> str:
    return "Microsoft.NETCore.App" if os.name != "nt" else "Microsoft.WindowsDesktop.App"


def ensure_runtime_config(runtime_host) -> str:
    runtime_config = os.path.join(runtime_host.managed_dir, "runtimeconfig.json")
    payload = {
        "runtimeOptions": {
            "tfm": "net8.0",
            "framework": {"name": _runtime_framework_name(), "version": "8.0.0"},
        }
    }

    try:
        current = None
        if os.path.exists(runtime_config):
            with open(runtime_config, "r", encoding="utf-8") as handle:
                current = json.load(handle)
        if current != payload:
            with open(runtime_config, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
    except OSError:
        fallback_dir = os.path.join(tempfile.gettempdir(), "paper_agent")
        os.makedirs(fallback_dir, exist_ok=True)
        runtime_config = os.path.join(fallback_dir, "runtimeconfig.json")
        with open(runtime_config, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    return runtime_config


def configure_local_dotnet(runtime_host) -> None:
    local_dotnet_root = os.path.join(runtime_host.script_dir, ".dotnet")
    local_dotnet = os.path.join(local_dotnet_root, "dotnet")
    if os.path.exists(local_dotnet) and not os.environ.get("DOTNET_ROOT"):
        os.environ["DOTNET_ROOT"] = local_dotnet_root
        current_path = os.environ.get("PATH", "")
        if local_dotnet_root not in current_path.split(os.pathsep):
            os.environ["PATH"] = local_dotnet_root + os.pathsep + current_path

    if os.name != "nt":
        current_ld_library_path = os.environ.get("LD_LIBRARY_PATH", "")
        search_paths = [item for item in current_ld_library_path.split(os.pathsep) if item]
        if runtime_host.native_dir not in search_paths:
            os.environ["LD_LIBRARY_PATH"] = runtime_host.native_dir + (
                os.pathsep + current_ld_library_path if current_ld_library_path else ""
            )


def ensure_linux_native_available(runtime_host) -> None:
    if os.name == "nt":
        return
    native_path = os.path.join(runtime_host.native_dir, "libSkiaSharp.so")
    if not os.path.exists(native_path):
        raise RuntimeError(f"Missing Linux native dependency: {native_path}")
    try:
        ctypes.CDLL(native_path, mode=getattr(ctypes, "RTLD_GLOBAL", 0))
    except OSError as exc:
        detail = str(exc)
        try:
            probe = subprocess.run(
                ["ldd", native_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            ldd_output = (probe.stdout or probe.stderr or "").strip()
            if ldd_output:
                detail = f"{detail}\n{ldd_output}"
        except Exception:
            pass
        raise RuntimeError(f"Unable to load Linux native dependency {native_path}: {detail}") from exc


def _latest_dotnet_runtime_dir() -> str | None:
    dotnet_root = os.environ.get("DOTNET_ROOT", "").strip()
    if not dotnet_root:
        return None
    shared_root = os.path.join(dotnet_root, "shared", "Microsoft.NETCore.App")
    if not os.path.isdir(shared_root):
        return None
    versions = sorted(
        [
            (name, os.path.join(shared_root, name))
            for name in os.listdir(shared_root)
            if os.path.isdir(os.path.join(shared_root, name))
        ],
        key=lambda item: item[0],
    )
    return versions[-1][1] if versions else None


def _ensure_native_probe_copy(source_path: str, target_dir: str) -> None:
    if not target_dir:
        return
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, os.path.basename(source_path))
    if os.path.exists(target_path):
        return
    try:
        os.symlink(source_path, target_path)
    except OSError:
        shutil.copy2(source_path, target_path)


def prepare_native_probe_paths(runtime_host) -> None:
    if os.name == "nt":
        return
    native_path = os.path.join(runtime_host.native_dir, "libSkiaSharp.so")
    if not os.path.exists(native_path):
        return
    probe_dirs = [runtime_host.managed_dir]
    runtime_dir = _latest_dotnet_runtime_dir()
    if runtime_dir:
        probe_dirs.append(runtime_dir)
    for probe_dir in probe_dirs:
        _ensure_native_probe_copy(native_path, probe_dir)


def load_dependencies(runtime_host, caller_globals: dict[str, object]) -> None:
    configure_local_dotnet(runtime_host)
    ensure_linux_native_available(runtime_host)
    prepare_native_probe_paths(runtime_host)

    if runtime_host.system == "windows" and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(runtime_host.managed_dir)
        if runtime_host.native_dir != runtime_host.managed_dir:
            os.add_dll_directory(runtime_host.native_dir)

    import pythonnet

    runtime_config = ensure_runtime_config(runtime_host)
    pythonnet.load("coreclr", runtime_config=runtime_config)

    import clr

    clr.AddReference(os.path.join(runtime_host.managed_dir, "SkiaSharp.dll"))
    clr.AddReference(os.path.join(runtime_host.managed_dir, "Aspose.Words.dll"))
    clr.AddReference("System.Text.Encoding.CodePages")

    import System
    import System.Drawing as SystemDrawing
    import System.Text
    from Aspose.Words import Document, ImportFormatMode, License, NodeType, Paragraph, Run, SaveFormat
    from Aspose.Words.Layout import LayoutCollector

    caller_globals.update(
        {
            "System": System,
            "SystemDrawing": SystemDrawing,
            "License": License,
            "Document": Document,
            "SaveFormat": SaveFormat,
            "NodeType": NodeType,
            "Paragraph": Paragraph,
            "LayoutCollector": LayoutCollector,
            "ImportFormatMode": ImportFormatMode,
            "Run": Run,
        }
    )

    runtime_host.SystemModule = System
    runtime_host.SystemDrawingModule = SystemDrawing
    runtime_host.License = License
    runtime_host.Document = Document
    runtime_host.LayoutCollector = LayoutCollector
    runtime_host.NodeType = NodeType
    runtime_host.SaveFormat = SaveFormat
    runtime_host.ImportFormatMode = ImportFormatMode
    runtime_host.Run = Run
    runtime_host.Paragraph = Paragraph

    System.Text.Encoding.RegisterProvider(System.Text.CodePagesEncodingProvider.Instance)
    activate_license(runtime_host)


def activate_license(runtime_host) -> None:
    lic = runtime_host.License()
    if not os.path.exists(runtime_host.license_path):
        runtime_host.license_loaded = False
        return
    import System.IO

    stream = System.IO.FileStream(
        runtime_host.license_path,
        System.IO.FileMode.Open,
        System.IO.FileAccess.Read,
    )
    try:
        lic.SetLicense(stream)
        runtime_host.license_loaded = True
    finally:
        stream.Dispose()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")
