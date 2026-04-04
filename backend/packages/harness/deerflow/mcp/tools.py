"""Load MCP tools using langchain-mcp-adapters."""

import asyncio
import atexit
import concurrent.futures
import logging
import os
import time
from collections.abc import Callable
from typing import Annotated, Any

from langgraph.config import get_config
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, InjectedToolArg

from deerflow.config.extensions_config import ExtensionsConfig
from deerflow.mcp.client import build_servers_config
from deerflow.mcp.oauth import build_oauth_tool_interceptor, get_initial_oauth_headers
from deerflow.mcp.path_mapping import build_path_mapping_tool_interceptor

logger = logging.getLogger(__name__)
_DEFAULT_MCP_INIT_TIMEOUT_SECONDS = 20.0
_THREAD_ID_INJECTION_SERVER_PREFIXES = ("paper_",)

# Global thread pool for sync tool invocation in async environments
_SYNC_TOOL_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="mcp-sync-tool")

# Register shutdown hook for the global executor
atexit.register(lambda: _SYNC_TOOL_EXECUTOR.shutdown(wait=False))


def _make_sync_tool_wrapper(coro: Callable[..., Any], tool_name: str) -> Callable[..., Any]:
    """Build a synchronous wrapper for an asynchronous tool coroutine.

    Args:
        coro: The tool's asynchronous coroutine.
        tool_name: Name of the tool (for logging).

    Returns:
        A synchronous function that correctly handles nested event loops.
    """

    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        try:
            if loop is not None and loop.is_running():
                # Use global executor to avoid nested loop issues and improve performance
                future = _SYNC_TOOL_EXECUTOR.submit(asyncio.run, coro(*args, **kwargs))
                return future.result()
            else:
                return asyncio.run(coro(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error invoking MCP tool '{tool_name}' via sync wrapper: {e}", exc_info=True)
            raise

    return sync_wrapper


def _extract_thread_id(config: RunnableConfig | None, runtime: Any = None) -> str | None:
    configurable = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    thread_id = configurable.get("thread_id") if isinstance(configurable, dict) else None
    if thread_id:
        return str(thread_id)

    if runtime is not None:
        context = getattr(runtime, "context", None) or {}
        thread_id = context.get("thread_id") if isinstance(context, dict) else getattr(context, "thread_id", None)
        if thread_id:
            return str(thread_id)

        runtime_config = getattr(runtime, "config", None) or {}
        runtime_configurable = runtime_config.get("configurable", {}) if isinstance(runtime_config, dict) else getattr(runtime_config, "configurable", None)
        if isinstance(runtime_configurable, dict):
            thread_id = runtime_configurable.get("thread_id")
        else:
            thread_id = getattr(runtime_configurable, "thread_id", None)
        if thread_id:
            return str(thread_id)

        thread_id = getattr(runtime, "thread_id", None)
        if thread_id:
            return str(thread_id)

    try:
        current_config = get_config()
    except Exception:
        current_config = None
    current_configurable = (current_config or {}).get("configurable", {}) if isinstance(current_config, dict) else {}
    thread_id = current_configurable.get("thread_id") if isinstance(current_configurable, dict) else None
    if thread_id:
        return str(thread_id)

    return None


def _should_inject_thread_id(tool_name: str) -> bool:
    return any(tool_name.startswith(prefix) for prefix in _THREAD_ID_INJECTION_SERVER_PREFIXES)


def _wrap_tool_for_thread_id_injection(tool: BaseTool) -> None:
    if not _should_inject_thread_id(tool.name):
        return

    original_coro = getattr(tool, "coroutine", None)
    if original_coro is None:
        return

    async def wrapped_coro(
        *args: Any,
        config: Annotated[RunnableConfig | None, InjectedToolArg] = None,
        runtime: Any = None,
        **kwargs: Any,
    ) -> Any:
        if not kwargs.get("thread_id"):
            thread_id = _extract_thread_id(config, runtime)
            if thread_id:
                kwargs["thread_id"] = thread_id
                logger.info("Auto-injected thread_id for MCP tool %s: %s", tool.name, thread_id)
            else:
                logger.warning("Failed to auto-inject thread_id for MCP tool %s", tool.name)
        if runtime is not None and "runtime" not in kwargs:
            kwargs["runtime"] = runtime
        return await original_coro(*args, **kwargs)

    tool.coroutine = wrapped_coro
    tool.func = _make_sync_tool_wrapper(tool.coroutine, tool.name)


async def get_mcp_tools() -> list[BaseTool]:
    """Get all tools from enabled MCP servers.

    Returns:
        List of LangChain tools from all enabled MCP servers.
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("langchain-mcp-adapters not installed. Install it to enable MCP tools: pip install langchain-mcp-adapters")
        return []

    # NOTE: We use ExtensionsConfig.from_file() instead of get_extensions_config()
    # to always read the latest configuration from disk. This ensures that changes
    # made through the Gateway API (which runs in a separate process) are immediately
    # reflected when initializing MCP tools.
    extensions_config = ExtensionsConfig.from_file()
    servers_config = build_servers_config(extensions_config)

    if not servers_config:
        logger.info("No enabled MCP servers configured")
        return []

    try:
        # Create the multi-server MCP client
        logger.info(f"Initializing MCP client with {len(servers_config)} server(s)")
        logger.info("MCP server config keys: %s", {name: servers_config[name].get("transport") for name in servers_config})

        # Inject initial OAuth headers for server connections (tool discovery/session init)
        initial_oauth_headers = await get_initial_oauth_headers(extensions_config)
        for server_name, auth_header in initial_oauth_headers.items():
            if server_name not in servers_config:
                continue
            if servers_config[server_name].get("transport") in ("sse", "http"):
                existing_headers = dict(servers_config[server_name].get("headers", {}))
                existing_headers["Authorization"] = auth_header
                servers_config[server_name]["headers"] = existing_headers

        tool_interceptors = []
        path_mapping_interceptor = build_path_mapping_tool_interceptor(extensions_config)
        if path_mapping_interceptor is not None:
            tool_interceptors.append(path_mapping_interceptor)
        oauth_interceptor = build_oauth_tool_interceptor(extensions_config)
        if oauth_interceptor is not None:
            tool_interceptors.append(oauth_interceptor)

        client = MultiServerMCPClient(servers_config, tool_interceptors=tool_interceptors, tool_name_prefix=True)
        timeout_seconds = float(os.getenv("DEER_FLOW_MCP_INIT_TIMEOUT_SECONDS", str(_DEFAULT_MCP_INIT_TIMEOUT_SECONDS)))
        logger.info("Fetching MCP tools with timeout %.1fs", timeout_seconds)

        # Get all tools from all servers
        started_at = time.monotonic()
        tools = await asyncio.wait_for(client.get_tools(), timeout=timeout_seconds)
        elapsed = time.monotonic() - started_at
        logger.info(f"Successfully loaded {len(tools)} tool(s) from MCP servers in {elapsed:.2f}s")

        # Patch tools to support thread_id injection and sync invocation.
        for tool in tools:
            _wrap_tool_for_thread_id_injection(tool)
            if getattr(tool, "func", None) is None and getattr(tool, "coroutine", None) is not None:
                tool.func = _make_sync_tool_wrapper(tool.coroutine, tool.name)

        return tools

    except TimeoutError:
        logger.error(
            "Timed out while initializing MCP tools after %.1fs. "
            "This usually means a configured MCP server process did not complete initialize/tools/list handshake.",
            float(os.getenv("DEER_FLOW_MCP_INIT_TIMEOUT_SECONDS", str(_DEFAULT_MCP_INIT_TIMEOUT_SECONDS))),
            exc_info=True,
        )
        return []
    except Exception as e:
        logger.error(f"Failed to load MCP tools: {e}", exc_info=True)
        return []
