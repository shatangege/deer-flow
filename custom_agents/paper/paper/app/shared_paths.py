from __future__ import annotations

import os
import re
from pathlib import Path


VIRTUAL_USER_DATA_PREFIX = "/mnt/user-data"
SAFE_THREAD_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def normalize_filesystem_path_arg(raw: str, thread_id: str | None = None) -> str:
    value = (raw or "").strip()
    if not value.startswith(VIRTUAL_USER_DATA_PREFIX):
        return value
    threads_root = os.getenv("THREADS_ROOT", "").strip()
    resolved_thread_id = (thread_id or "").strip() or os.getenv("PAPER_THREAD_ID", "").strip()
    if not threads_root or not resolved_thread_id:
        raise ValueError(
            "Paths under /mnt/user-data require THREADS_ROOT and PAPER_THREAD_ID, or an explicit thread_id."
        )
    if not SAFE_THREAD_ID_RE.match(resolved_thread_id):
        raise ValueError("Invalid thread_id for virtual path resolution.")
    rel = value[len(VIRTUAL_USER_DATA_PREFIX) :].lstrip("/\\")
    base = (Path(threads_root) / resolved_thread_id / "user-data").resolve()
    resolved = (base / rel).resolve() if rel else base
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError("Path escapes user-data directory.") from exc
    return str(resolved)


def resolve_thread_user_data_path(thread_id: str, relative_path: str) -> Path:
    thread = (thread_id or "").strip()
    if not SAFE_THREAD_ID_RE.match(thread):
        raise ValueError("Invalid thread_id for shared path resolution.")
    rel = (relative_path or "").strip().lstrip("/\\")
    if not rel:
        raise ValueError("Relative path under thread user-data cannot be empty.")
    base = Path(os.getenv("THREADS_ROOT", "/mnt/threads")).expanduser().resolve() / thread / "user-data"
    base = base.resolve()
    resolved = (base / rel).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError("Thread-relative path escapes user-data directory.") from exc
    return resolved


def resolve_existing_file(label: str, raw: str, thread_id: str | None = None) -> Path:
    normalized = normalize_filesystem_path_arg(raw, thread_id)
    path = Path(normalized).expanduser()
    if not path.is_absolute() and thread_id:
        path = resolve_thread_user_data_path(thread_id, normalized)
    elif not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{label} is not an existing file: {path}")
    return path


def resolve_output_file(raw: str, thread_id: str | None = None) -> Path:
    normalized = normalize_filesystem_path_arg(raw, thread_id)
    path = Path(normalized).expanduser()
    if not path.is_absolute() and thread_id:
        path = resolve_thread_user_data_path(thread_id, normalized)
    elif not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
