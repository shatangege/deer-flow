# Paper Format Expert Integration

This integration keeps the document formatter layered in three parts:

1. Base capability: `custom_agents/formatter_paper/`
2. Independent formatter service: `custom_agents/formatter_paper/formatter_mcp_server.py`
3. User-facing skill: `paper-format-expert`

## Placement

- Keep the formatter project under `custom_agents/formatter_paper/` (optional content; not part of Deer Flow core).
- Keep the standalone formatter HTTP MCP service under `custom_agents/formatter_paper/`.
- Keep the versioned skill template in `skills/custom/paper-format-expert/` (optional content; not part of Deer Flow core).
- No `backend/.deer-flow/agents` installation is required; orchestration is enabled via `extensions_config.json`.

Deer Flow resolves the formatter through `FORMATTER_PAPER_MCP_URL` in `extensions_config.json`.

## Why This Is Plug-In Friendly

- Deer Flow core flow is untouched.
- The formatter is exposed through `extensions_config.json` as a remote HTTP MCP server.
- The paper-format-expert skill is an optional orchestration layer, not a replacement for the default lead agent.
- The skill remains a fallback path, so the integration can degrade gracefully if MCP is unavailable.

## Install Or Refresh

This integration is intended to be enabled/disabled at runtime by updating `extensions_config.json`.

From the repository root, ensure the following are present (and enabled):

- `mcpServers.formatter-paper.enabled: true`
- `skills.paper-format-expert.enabled: true`

After changing `extensions_config.json`, Deer Flow should reload the enabled extensions (and MCP tools/skills) without requiring code changes. If your environment does not auto-reload, restart Deer Flow once to pick up the new config.

## Runtime Model

- `custom_agents/formatter_paper/` contains the low-level Aspose-backed capability and the standalone HTTP MCP service.
- `formatter-paper` MCP is now a remote HTTP service instead of a backend-local stdio subprocess.
- `paper-format-expert` is the orchestration layer that chooses when and how to call it.
- `smart_repair` remains an internal formatter capability; Deer Flow should not consume its planner/state objects directly.
- `formatter_pipeline_hooks.py` remains disabled-by-default and formatter-internal; Deer Flow integration should use explicit MCP tools rather than automatic hooks.

## Docker Runtime Prerequisites

When Deer Flow runs in Docker, the `formatter-paper` MCP should execute as its own Linux service container instead of inside the `gateway` or `langgraph` backend containers.

Make sure the formatter service has all of the following:

- Python 3.12
- `pythonnet` in the same Python environment that launches `formatter_mcp_server.py`
- a usable Linux `.NET 8` runtime with `Microsoft.NETCore.App`
- Aspose managed runtime files available under a managed assets directory
- Linux native assets available under a separate native assets directory, especially `libSkiaSharp.so`

This integration keeps the **Python bridge** model:

- `formatter_mcp_server.py` starts the HTTP MCP service
- `convert.py` / `formatter_runtime.py` call Aspose .NET DLLs through `pythonnet.load("coreclr", ...)`
- the Windows sample tutorial is only a Python/.NET invocation reference; its `Microsoft.WindowsDesktop.App` and `libSkiaSharp.dll` assumptions must not be copied into Linux
- on Linux, managed DLLs and native `.so` files are intentionally split so host mounts cannot overwrite the image-baked native assets

For container deployment, build the dedicated Linux image:

```bash
docker build -f custom_agents/formatter_paper/Dockerfile -t formatter-paper-mcp:linux-dotnet8-python312 .
```

Then expose the HTTP MCP endpoint from that container and point Deer Flow at it with:

```env
FORMATTER_PAPER_MCP_URL=http://formatter-paper:8765/mcp
```

The Deer Flow backend containers should not try to boot Aspose locally; they only need the formatter service URL.

Minimum runtime validation inside the formatter container:

```bash
python --version
dotnet --list-runtimes
python -c "import pythonnet; print('pythonnet ok')"
ls /opt/formatter-paper/native/libSkiaSharp.so
ldd /opt/formatter-paper/native/libSkiaSharp.so
```

Expected:

- Python is `3.12.x`
- `.NET 8` includes `Microsoft.NETCore.App`
- `pythonnet` imports cleanly
- `libSkiaSharp.so` exists and `ldd` reports no `not found`

## Docker / Compose Recommendation

Use a split strategy:

- run a dedicated formatter service with `formatter_mcp_server.py`
- or run the dedicated Linux container built from `custom_agents/formatter_paper/Dockerfile`
- point Deer Flow containers to it via `FORMATTER_PAPER_MCP_URL`
- `/mnt/skills`, `/app/skills`, and **`THREADS_ROOT=/mnt/threads`** (host `backend/.deer-flow/threads`) are mounted on `formatter-paper`; prefer concrete shared paths such as `/mnt/threads/<id>/user-data/uploads/...`, `/mnt/threads/<id>/user-data/workspace/...`, and `/mnt/threads/<id>/user-data/outputs/...` (see `formatter_mcp_server.py`)
- prefer shared filesystem paths to the remote tools; use downloadable URLs only when shared mounts are unavailable, and reserve base64 for small fallback payloads
- consume returned `output_download_url` and optional `report_download_url`

This keeps Deer Flow unchanged while moving all Aspose runtime requirements out of the backend image and into a dedicated Linux formatter service.

### Compose: formatter-paper mounts vs script behavior

| Need | Compose (dev/prod) | Used by |
|------|--------------------|--------|
| `custom_agents/formatter_paper/lib` → `ASPOSE_LIBS` | bind mount (read-only) | Aspose / Skia native loading; `runtimeconfig` may fall back to `/tmp` if `lib` is ro |
| `Aspose.Total.lic` at `/app/backend/Aspose.Total.lic` | bind mount (read-only) | License activation |
| `backend/.deer-flow` → `/app/backend/.deer-flow` | bind mount (read-write) | Thread data; HTTP tools can use `*_docx_path` or `/mnt/user-data/...` |
| `skills/` → `/app/skills` and `/mnt/skills` | bind mount (read-only) | Same host tree as gateway (`/app/skills`) and sandbox virtual skills path (`/mnt/skills`) |
| `backend/.deer-flow/threads` → `/mnt/threads` | bind mount (read-write) | **`THREADS_ROOT`** for app-side paths; optional `/mnt/user-data/...` mapping via `FORMATTER_PAPER_THREAD_ID` in formatter MCP |
| `DEER_FLOW_HOME=/app/backend/.deer-flow` | env on `formatter-paper`; dev compose also sets on `gateway` / `langgraph` | Same logical data root as [`get_paths().base_dir`](../backend/packages/harness/deerflow/config/paths.py) when resolving `/mnt/user-data/...` in the backend |

The **stdio** formatter MCP resolves virtual paths inside the gateway process. The **HTTP** formatter should primarily use concrete shared paths under **`/mnt/threads/<id>/user-data/...`**. Virtual `/mnt/user-data/...` mapping remains available only as a compatibility fallback when **`THREADS_ROOT`** and **`FORMATTER_PAPER_THREAD_ID`** are set.

To verify the formatter container after `docker compose ... up`, run [`docker/verify-formatter-paper-mounts.sh`](../docker/verify-formatter-paper-mounts.sh) from the `docker/` directory (see also [HTTP_MCP.md](../custom_agents/formatter_paper/HTTP_MCP.md)).

Current tool surface:

- `format_paper`: fast one-shot formatting pipeline
- `repair_paper_pagination`: one-shot formatting plus iterative page-stream pagination repair for heading/caption attachment
