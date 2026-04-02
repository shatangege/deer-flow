"""Path mapping helpers for MCP tool calls."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from langgraph.config import get_config

from deerflow.config.extensions_config import ExtensionsConfig, McpServerConfig
from deerflow.config.paths import VIRTUAL_PATH_PREFIX, get_paths

logger = logging.getLogger(__name__)

_USER_DATA_RELATIVE_ROOTS = ("uploads", "outputs", "workspace")
_WINDOWS_ABS_PREFIXES = tuple(f"{drive}:\\" for drive in "ABCDEFGHIJKLMNOPQRSTUVWXYZ") + tuple(
    f"{drive}:/" for drive in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)


def _mapping_get(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _extract_thread_id(runtime: Any) -> str | None:
    if runtime is None:
        return None

    context = _mapping_get(runtime, "context") or {}
    thread_id = _mapping_get(context, "thread_id")
    if thread_id:
        return str(thread_id)

    config = _mapping_get(runtime, "config") or {}
    configurable = _mapping_get(config, "configurable") or {}
    thread_id = _mapping_get(configurable, "thread_id")
    if thread_id:
        return str(thread_id)

    thread_id = _mapping_get(runtime, "thread_id")
    if thread_id:
        return str(thread_id)

    return None


def _extract_thread_id_from_mapping(mapping: Mapping[str, Any] | None) -> str | None:
    if not mapping:
        return None
    thread_id = mapping.get("thread_id")
    if thread_id:
        return str(thread_id)
    configurable = mapping.get("configurable")
    if isinstance(configurable, Mapping):
        thread_id = configurable.get("thread_id")
        if thread_id:
            return str(thread_id)
    context = mapping.get("context")
    if isinstance(context, Mapping):
        thread_id = context.get("thread_id")
        if thread_id:
            return str(thread_id)
    return None


def _extract_request_thread_id(request: Any) -> str | None:
    args = getattr(request, "args", None) or {}
    if isinstance(args, dict):
        thread_id = args.get("thread_id")
        if thread_id:
            return str(thread_id)

    for attr_name in ("context", "config", "metadata"):
        attr_value = getattr(request, attr_name, None)
        if isinstance(attr_value, Mapping):
            thread_id = _extract_thread_id_from_mapping(attr_value)
            if thread_id:
                return thread_id

    for attr_name in ("runtime", "tool_runtime"):
        runtime = getattr(request, attr_name, None)
        thread_id = _extract_thread_id(runtime)
        if thread_id:
            return thread_id

    if isinstance(request, Mapping):
        thread_id = _extract_thread_id_from_mapping(request)
        if thread_id:
            return thread_id

    try:
        current_config = get_config()
    except Exception:
        current_config = None
    thread_id = _extract_thread_id_from_mapping(current_config if isinstance(current_config, Mapping) else None)
    if thread_id:
        return thread_id

    return _extract_thread_id(getattr(request, "runtime", None))


def _is_absolute_path_like(value: str) -> bool:
    if not value:
        return False
    return os.path.isabs(value) or value.startswith(_WINDOWS_ABS_PREFIXES)


def _resolve_relative_user_data_path(thread_id: str, raw_path: str) -> Path:
    normalized = raw_path.replace("\\", "/").lstrip("/")
    first_segment = normalized.split("/", 1)[0]
    if first_segment not in _USER_DATA_RELATIVE_ROOTS:
        raise ValueError(
            f"Relative path '{raw_path}' must start with one of: {', '.join(_USER_DATA_RELATIVE_ROOTS)}"
        )

    base = get_paths().sandbox_user_data_dir(thread_id).resolve()
    candidate = (base / Path(normalized)).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("Access denied: path escapes thread user-data directory") from exc
    return candidate


def rewrite_path_argument(thread_id: str | None, raw_path: str) -> str:
    value = (raw_path or "").strip()
    if not value:
        return value

    if value.startswith(VIRTUAL_PATH_PREFIX):
        if not thread_id:
            raise ValueError("thread_id is required to resolve virtual MCP paths")
        return str(get_paths().resolve_virtual_path(thread_id, value))

    if _is_absolute_path_like(value):
        return value

    if not thread_id:
        raise ValueError("thread_id is required to resolve relative MCP paths")
    return str(_resolve_relative_user_data_path(thread_id, value))


def _path_requires_thread_id(raw_path: str) -> bool:
    value = (raw_path or "").strip()
    if not value:
        return False
    if value.startswith(VIRTUAL_PATH_PREFIX):
        return True
    return not _is_absolute_path_like(value)


def build_path_mapping_tool_interceptor(extensions_config: ExtensionsConfig) -> Any | None:
    """Build an MCP tool interceptor that rewrites virtual file paths to physical paths."""

    server_configs: dict[str, McpServerConfig] = {
        name: config
        for name, config in extensions_config.get_enabled_mcp_servers().items()
        if (config.path_mapping or "").strip() == "virtual_to_physical"
    }
    if not server_configs:
        return None

    async def path_mapping_interceptor(request: Any, handler: Any) -> Any:
        server_config = server_configs.get(request.server_name)
        if server_config is None:
            return await handler(request)

        path_arg_names = set(server_config.path_arg_names)
        updated_args = dict(request.args or {})
        changed = False
        needs_thread_id = False

        for arg_name, arg_value in list(updated_args.items()):
            if arg_name not in path_arg_names:
                continue
            if not isinstance(arg_value, str):
                continue
            raw = arg_value.strip()
            if _path_requires_thread_id(raw):
                needs_thread_id = True

        thread_id = _extract_request_thread_id(request)
        if needs_thread_id and not thread_id:
            logger.warning(
                "Missing thread_id for MCP path mapping: server=%s tool=%s arg_keys=%s request_attrs=%s",
                request.server_name,
                request.name,
                sorted(updated_args.keys()),
                sorted(attr for attr in ("args", "context", "config", "metadata", "runtime", "tool_runtime") if hasattr(request, attr)),
            )
            raise ValueError(
                f"MCP server '{request.server_name}' requires thread_id for virtual_to_physical path mapping"
            )

        for arg_name, arg_value in list(updated_args.items()):
            if arg_name not in path_arg_names:
                continue
            if not isinstance(arg_value, str):
                continue
            rewritten = rewrite_path_argument(thread_id, arg_value)
            if rewritten != arg_value:
                updated_args[arg_name] = rewritten
                changed = True

        if changed:
            logger.info(
                "Rewrote MCP path args for server=%s tool=%s thread_id=%s args=%s",
                request.server_name,
                request.name,
                thread_id,
                {name: updated_args.get(name) for name in path_arg_names if name in updated_args},
            )
            return await handler(request.override(args=updated_args))

        return await handler(request)

    return path_mapping_interceptor
