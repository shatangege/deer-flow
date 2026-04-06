from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from time import perf_counter


def _runtime_framework_name() -> str:
    return "Microsoft.NETCore.App" if os.name != "nt" else "Microsoft.WindowsDesktop.App"


def _diag_enabled() -> bool:
    return os.environ.get("PAPER_ASPOSE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _diag_log(message: str, **fields: object) -> None:
    if not _diag_enabled():
        return
    payload = {"message": message, **fields}
    sys.stderr.write(f"[paper-aspose] {json.dumps(payload, ensure_ascii=False)}\n")
    sys.stderr.flush()


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


def _candidate_linux_native_dirs(runtime_host) -> list[str]:
    candidates = [
        getattr(runtime_host, "native_dir", ""),
        os.environ.get("ASPOSE_NATIVE_DIR", "").strip(),
        getattr(runtime_host, "managed_dir", ""),
        os.path.join(getattr(runtime_host, "script_dir", ""), "lib"),
        "/opt/paper-agent/native",
        "/app/custom_agents/paper/lib",
    ]
    resolved: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = os.path.abspath(candidate)
        if path in seen:
            continue
        seen.add(path)
        resolved.append(path)
    return resolved


def _bootstrap_linux_native_dependency(runtime_host) -> str | None:
    package_name = os.environ.get("SKIASHARP_NATIVE_PACKAGE", "SkiaSharp.NativeAssets.Linux").strip() or "SkiaSharp.NativeAssets.Linux"
    package_version = os.environ.get("SKIASHARP_NATIVE_VERSION", "2.88.9").strip() or "2.88.9"
    flat_container_base = os.environ.get("NUGET_FLAT_CONTAINER_BASE", "https://api.nuget.org/v3-flatcontainer").rstrip("/")
    package_lower = package_name.lower()
    version_lower = package_version.lower()
    download_url = f"{flat_container_base}/{package_lower}/{version_lower}/{package_lower}.{version_lower}.nupkg"
    cache_root = os.path.join(tempfile.gettempdir(), "paper_agent", "native-cache", f"{package_lower}-{version_lower}")
    native_dir = os.path.join(cache_root, "linux-x64")
    native_path = os.path.join(native_dir, "libSkiaSharp.so")
    if os.path.exists(native_path):
        runtime_host.last_native_bootstrap_error = None
        return native_path
    os.makedirs(native_dir, exist_ok=True)
    package_path = os.path.join(cache_root, f"{package_lower}.{version_lower}.nupkg")
    try:
        _diag_log("bootstrap_linux_native_dependency:start", url=download_url, target_dir=native_dir)
        if not os.path.exists(package_path):
            with urllib.request.urlopen(download_url, timeout=30) as response, open(package_path, "wb") as handle:
                shutil.copyfileobj(response, handle)
        with zipfile.ZipFile(package_path) as archive:
            with archive.open("runtimes/linux-x64/native/libSkiaSharp.so") as source, open(native_path, "wb") as target:
                shutil.copyfileobj(source, target)
        runtime_host.last_native_bootstrap_error = None
        _diag_log("bootstrap_linux_native_dependency:done", native_path=native_path)
        return native_path if os.path.exists(native_path) else None
    except Exception as exc:
        runtime_host.last_native_bootstrap_error = str(exc)
        _diag_log("bootstrap_linux_native_dependency:failed", error=str(exc), url=download_url)
        return None


def resolve_linux_native_path(runtime_host) -> str:
    if os.name == "nt":
        return os.path.join(runtime_host.native_dir, "libSkiaSharp.dll")
    for candidate_dir in _candidate_linux_native_dirs(runtime_host):
        candidate_path = os.path.join(candidate_dir, "libSkiaSharp.so")
        if os.path.exists(candidate_path):
            if getattr(runtime_host, "native_dir", "") != candidate_dir:
                runtime_host.native_dir = candidate_dir
                os.environ["ASPOSE_NATIVE_DIR"] = candidate_dir
            return candidate_path
    bootstrapped_path = _bootstrap_linux_native_dependency(runtime_host)
    if bootstrapped_path:
        bootstrapped_dir = os.path.dirname(bootstrapped_path)
        runtime_host.native_dir = bootstrapped_dir
        os.environ["ASPOSE_NATIVE_DIR"] = bootstrapped_dir
        return bootstrapped_path
    return os.path.join(runtime_host.native_dir, "libSkiaSharp.so")


def ensure_linux_native_available(runtime_host) -> None:
    if os.name == "nt":
        return
    native_path = resolve_linux_native_path(runtime_host)
    if not os.path.exists(native_path):
        detail = getattr(runtime_host, "last_native_bootstrap_error", None)
        if detail:
            raise RuntimeError(f"Missing Linux native dependency: {native_path}; bootstrap failed: {detail}")
        raise RuntimeError(f"Missing Linux native dependency: {native_path}")
    try:
        _diag_log("load_linux_native_dependency:start", native_path=native_path)
        ctypes.CDLL(native_path, mode=getattr(ctypes, "RTLD_GLOBAL", 0))
        _diag_log("load_linux_native_dependency:done", native_path=native_path)
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
    native_path = resolve_linux_native_path(runtime_host)
    if not os.path.exists(native_path):
        return
    probe_dirs = [runtime_host.managed_dir]
    runtime_dir = _latest_dotnet_runtime_dir()
    if runtime_dir:
        probe_dirs.append(runtime_dir)
    for probe_dir in probe_dirs:
        _ensure_native_probe_copy(native_path, probe_dir)


def load_dependencies(runtime_host, caller_globals: dict[str, object]) -> None:
    started = perf_counter()
    _diag_log(
        "load_dependencies:start",
        managed_dir=runtime_host.managed_dir,
        native_dir=runtime_host.native_dir,
        license_path=runtime_host.license_path,
        system=runtime_host.system,
    )
    ensure_linux_native_available(runtime_host)
    _diag_log("load_dependencies:after_native", elapsed_ms=round((perf_counter() - started) * 1000, 1), native_dir=runtime_host.native_dir)
    configure_local_dotnet(runtime_host)
    _diag_log("load_dependencies:after_dotnet_env", elapsed_ms=round((perf_counter() - started) * 1000, 1), dotnet_root=os.environ.get("DOTNET_ROOT", ""))
    prepare_native_probe_paths(runtime_host)
    _diag_log("load_dependencies:after_probe_paths", elapsed_ms=round((perf_counter() - started) * 1000, 1))

    if runtime_host.system == "windows" and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(runtime_host.managed_dir)
        if runtime_host.native_dir != runtime_host.managed_dir:
            os.add_dll_directory(runtime_host.native_dir)

    import pythonnet

    runtime_config = ensure_runtime_config(runtime_host)
    _diag_log("load_dependencies:pythonnet_load:start", runtime_config=runtime_config)
    pythonnet.load("coreclr", runtime_config=runtime_config)
    _diag_log("load_dependencies:pythonnet_load:done", elapsed_ms=round((perf_counter() - started) * 1000, 1))

    import clr

    _diag_log("load_dependencies:add_reference:start")
    clr.AddReference(os.path.join(runtime_host.managed_dir, "SkiaSharp.dll"))
    clr.AddReference(os.path.join(runtime_host.managed_dir, "Aspose.Words.dll"))
    clr.AddReference("System.Text.Encoding.CodePages")
    _diag_log("load_dependencies:add_reference:done", elapsed_ms=round((perf_counter() - started) * 1000, 1))

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
    _diag_log("load_dependencies:done", elapsed_ms=round((perf_counter() - started) * 1000, 1), license_loaded=runtime_host.license_loaded)


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
