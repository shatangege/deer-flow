# Paper Format Expert Integration

This integration keeps the document formatter layered in three parts:

1. Base capability: `custom_agents/formatter_paper/`
2. Deer Flow bridge: `backend/packages/harness/deerflow/mcp_custom/formatter_paper.py`
3. User-facing skill: `paper-format-expert`

## Placement

- Keep the formatter project under `custom_agents/formatter_paper/` (optional content; not part of Deer Flow core).
- Keep the MCP bridge in the Deer Flow backend package.
- Keep the versioned skill template in `skills/custom/paper-format-expert/` (optional content; not part of Deer Flow core).
- No `backend/.deer-flow/agents` installation is required; orchestration is enabled via `extensions_config.json`.

The MCP server resolves the formatter via `FORMATTER_PAPER_ROOT` in `extensions_config.json` (defaults to `../custom_agents/formatter_paper` relative to the backend working directory).

## Why This Is Plug-In Friendly

- Deer Flow core flow is untouched.
- The formatter is exposed through `extensions_config.json` as an MCP server.
- The paper-format-expert skill is an optional orchestration layer, not a replacement for the default lead agent.
- The skill remains a fallback path, so the integration can degrade gracefully if MCP is unavailable.

## Install Or Refresh

This integration is intended to be enabled/disabled at runtime by updating `extensions_config.json`.

From the repository root, ensure the following are present (and enabled):

- `mcpServers.formatter-paper.enabled: true`
- `skills.paper-format-expert.enabled: true`

After changing `extensions_config.json`, Deer Flow should reload the enabled extensions (and MCP tools/skills) without requiring code changes. If your environment does not auto-reload, restart Deer Flow once to pick up the new config.

## Runtime Model

- `custom_agents/formatter_paper/` is the low-level Aspose-backed capability.
- `formatter-paper` MCP exposes that capability as a tool.
- `paper-format-expert` is the orchestration layer that chooses when and how to call it.
