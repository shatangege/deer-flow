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

When Deer Flow runs in Docker, the `formatter-paper` MCP should execute outside the Linux backend container, typically on a Windows host or Windows container.

Make sure the remote Windows formatter service has all of the following:

- `pythonnet` installed in the Python environment that launches `formatter_mcp_server.py`
- a usable Windows `.NET Desktop Runtime 8.x`
- Aspose runtime files available under `custom_agents/formatter_paper/lib/`
- if using containers, a Windows container base image rather than the Linux backend image

Recommended one-time validation command on the Windows formatter host:

```bash
uv run --project backend python custom_agents/formatter_paper/install.py
```

Use it to verify the Windows formatter environment. Deer Flow runtime containers should not rely on local Aspose startup.

For a Windows container deployment, build the dedicated image:

```bash
docker build -f custom_agents/formatter_paper/Dockerfile.windows -t formatter-paper-mcp:windows-ltsc2022 .
```

Then expose the HTTP MCP endpoint from that Windows container and point Deer Flow at it with:

```env
FORMATTER_PAPER_MCP_URL=http://host.docker.internal:8765/mcp
```

The Linux Deer Flow containers should not try to boot Aspose locally; they only need the remote formatter URL.

## Docker / Compose Recommendation

Use a split strategy:

- run a dedicated Windows formatter service with `formatter_mcp_server.py`
- or run the dedicated Windows container built from `custom_agents/formatter_paper/Dockerfile.windows`
- point Deer Flow containers to it via `FORMATTER_PAPER_MCP_URL`
- do not assume `/mnt/user-data/...` Linux virtual paths are visible to the remote service
- pass either downloadable URLs or base64 payloads to the remote tools
- consume returned `output_download_url` and optional `report_download_url`

This keeps Deer Flow unchanged while moving all Windows-specific Aspose runtime requirements out of the Linux backend image.

Current tool surface:

- `format_paper`: fast one-shot formatting pipeline
- `repair_paper_pagination`: one-shot formatting plus iterative page-stream pagination repair for heading/caption attachment
