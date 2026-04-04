from __future__ import annotations

from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def convert_script_path() -> Path:
    return package_root() / "convert.py"


def service_data_dir() -> Path:
    return package_root() / ".service-data"


def aspose_lib_dir() -> Path:
    return (package_root() / "lib").resolve()
