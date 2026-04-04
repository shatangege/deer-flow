# Paper Format Expert Integration

This integration now uses the `paper` service as the active Aspose-backed paper formatting MCP.

## Placement

The active runtime is split into three parts:

1. Paper capability: `custom_agents/paper/`
2. Independent HTTP MCP service: `custom_agents/paper/paper_mcp_server.py`
3. User-facing orchestration: Deer Flow `paper-*` subagents and the optional `paper-format-expert` skill

Deer Flow resolves the formatter through `PAPER_MCP_URL` in `extensions_config.json`.

## Active Runtime Model

- `custom_agents/paper/` contains the active Aspose-backed paper pipeline.
- `paper` MCP is a remote HTTP service instead of a backend-local stdio subprocess.
- Deer Flow routes paper work through the `paper-*` built-in subagents and the `paper` MCP toolset.
- The active runtime path is `paper` only. Any older formatter implementation is legacy-only and not part of the default compose or extension path.

## Install Or Refresh

From the repository root, ensure the following are present and enabled:

- `mcpServers.paper.enabled: true`
- `skills.paper-format-expert.enabled: true`

After changing `extensions_config.json`, Deer Flow should reload the enabled extensions. If your environment does not auto-reload, restart Deer Flow once.

## Docker Runtime Prerequisites

When Deer Flow runs in Docker, the `paper` MCP executes as its own Linux service container instead of inside `gateway` or `langgraph`.

Make sure the `paper` service has all of the following:

- Python 3.12
- `pythonnet` in the same Python environment that launches `paper_mcp_server.py`
- a usable Linux `.NET 8` runtime with `Microsoft.NETCore.App`
- Aspose managed runtime files under `ASPOSE_MANAGED_DIR`
- Linux native assets under `ASPOSE_NATIVE_DIR`, especially `libSkiaSharp.so`

This integration keeps the Python bridge model:

- `paper_mcp_server.py` starts the HTTP MCP service
- `paper/core/runtime.py` calls Aspose .NET DLLs through `pythonnet.load("coreclr", ...)`
- Linux managed DLLs and native `.so` files are intentionally split so host mounts cannot overwrite the image-baked native assets

For container deployment, build the dedicated Linux image:

```bash
docker build -f custom_agents/paper/Dockerfile -t paper-agent-mcp:linux-dotnet8-python312 .
```

Then point Deer Flow at it with:

```env
PAPER_MCP_URL=http://paper:8766/mcp
```

The Deer Flow backend containers should not boot Aspose locally; they only need the `paper` service URL.

Minimum runtime validation inside the `paper` container:

```bash
python --version
dotnet --list-runtimes
python -c "import pythonnet; print('pythonnet ok')"
ls /opt/paper-agent/native/libSkiaSharp.so
ldd /opt/paper-agent/native/libSkiaSharp.so
```

## Docker / Compose Recommendation

Use a split strategy:

- run a dedicated `paper` service with `paper_mcp_server.py`
- or run the dedicated Linux container built from `custom_agents/paper/Dockerfile`
- point Deer Flow containers to it via `PAPER_MCP_URL`
- mount `/mnt/skills`, `/app/skills`, and `THREADS_ROOT=/mnt/threads` on the `paper` container
- prefer concrete shared paths such as `/mnt/threads/<id>/user-data/uploads/...`, `/mnt/threads/<id>/user-data/workspace/...`, and `/mnt/threads/<id>/user-data/outputs/...`

This keeps Deer Flow unchanged while moving all Aspose runtime requirements out of the backend image and into the dedicated `paper` service.

## Compose Mounts

| Need | Compose (dev/prod) | Used by |
|------|--------------------|--------|
| `custom_agents/paper/lib/*.dll` → `/opt/paper-agent/managed/*` | bind mounts (read-only) | Managed Aspose runtime assets for the active `paper` service |
| `custom_agents/paper/lib/Aspose.Total.NET.lic` → `/opt/paper-agent/license/Aspose.Total.NET.lic` | bind mount (read-only) | License activation |
| `backend/.deer-flow` → `/app/backend/.deer-flow` | bind mount (read-write) | Thread data and output workspace |
| `skills/` → `/app/skills` and `/mnt/skills` | bind mounts (read-only) | Same host tree as gateway and sandbox |
| `backend/.deer-flow/threads` → `/mnt/threads` | bind mount (read-write) | `THREADS_ROOT` for app-side path mapping |
| `DEER_FLOW_HOME=/app/backend/.deer-flow` | env on `paper`; also set on `gateway` / `langgraph` | Same logical data root used by Deer Flow path resolution |

To verify the `paper` container after `docker compose ... up`, run [verify-paper-mounts.sh](/d:/workspace2/deer-flow/docker/verify-paper-mounts.sh) from the `docker/` directory.

## Active Tool Surface

- `run_paper_pipeline`
- `extract_paper_template_rules`
- `split_paper_sections`
- `process_paper_section`
- `aggregate_paper_sections`
