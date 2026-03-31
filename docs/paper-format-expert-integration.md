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

- `pythonnet` installed in the Python environment that launches `formatter_mcp_server.py`
- a usable Linux `.NET 8` runtime
- Aspose runtime files available under `custom_agents/formatter_paper/lib/`
- Linux native assets available under `custom_agents/formatter_paper/lib/`, especially `libSkiaSharp.so`

Recommended one-time validation command on the formatter host:

```bash
uv run --project backend python custom_agents/formatter_paper/install.py
```

Use it to verify the formatter environment. Deer Flow runtime containers should not rely on local Aspose startup.

For container deployment, build the dedicated Linux image:

```bash
docker build -f custom_agents/formatter_paper/Dockerfile -t formatter-paper-mcp:linux-dotnet8-python312 .
```

Then expose the HTTP MCP endpoint from that container and point Deer Flow at it with:

```env
FORMATTER_PAPER_MCP_URL=http://formatter-paper:8765/mcp
```

The Deer Flow backend containers should not try to boot Aspose locally; they only need the formatter service URL.

## Docker / Compose Recommendation

Use a split strategy:

- run a dedicated formatter service with `formatter_mcp_server.py`
- or run the dedicated Linux container built from `custom_agents/formatter_paper/Dockerfile`
- point Deer Flow containers to it via `FORMATTER_PAPER_MCP_URL`
- `/mnt/skills`, `/app/skills`, and **`THREADS_ROOT=/mnt/threads`** (host `backend/.deer-flow/threads`) are mounted on `formatter-paper`; use `/mnt/threads/<id>/user-data/...` or virtual `/mnt/user-data/...` with `FORMATTER_PAPER_THREAD_ID` set (see `formatter_mcp_server.py`)
- pass either downloadable URLs or base64 payloads to the remote tools
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

The **stdio** formatter MCP resolves virtual paths **inside the gateway process**. The **HTTP** formatter maps `/mnt/user-data/...` when **`THREADS_ROOT`** and **`FORMATTER_PAPER_THREAD_ID`** are set, or use concrete paths under **`/mnt/threads/<id>/user-data/...`**.

To verify the formatter container after `docker compose ... up`, run [`docker/verify-formatter-paper-mounts.sh`](../docker/verify-formatter-paper-mounts.sh) from the `docker/` directory (see also [HTTP_MCP.md](../custom_agents/formatter_paper/HTTP_MCP.md)).

Current tool surface:

- `format_paper`: fast one-shot formatting pipeline
- `repair_paper_pagination`: one-shot formatting plus iterative page-stream pagination repair for heading/caption attachment
