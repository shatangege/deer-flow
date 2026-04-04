# Paper Agent

`paper` is an independent paper-formatting agent module for Deer Flow.

It implements a 5-agent pipeline:

- `TemplateRuleAgent`
- `FlowSchedulerAgent`
- `SectionProcessorAgent`
- `AsposeExecutionAgent`
- `AggregationReviewAgent`

The module is intentionally self-contained while reusing the same Aspose runtime
conventions used elsewhere in the repo: `pythonnet`, `.NET 8`, managed/native
asset split, and license loading.

## Entry Points

- `python custom_agents/paper/convert.py`
- `python custom_agents/paper/paper_mcp_server.py`

The MCP server runs as a streamable HTTP service by default using:

- `PAPER_HTTP_HOST`
- `PAPER_HTTP_PORT`
- `PAPER_HTTP_PATH`

The MCP surface is split into two layers:

- High-level paper workflow tools for full formatting pipelines
- Low-level Aspose execution tools for extraction, section rewriting, styling, validation, and merge operations

## Container Build

```bash
docker build -f custom_agents/paper/Dockerfile -t paper-agent-mcp:linux-dotnet8-python312 .
```

The paper container uses these Aspose runtime conventions:

- `ASPOSE_MANAGED_DIR`
- `ASPOSE_NATIVE_DIR`
- `ASPOSE_LICENSE_PATH`

Managed Aspose runtime files live under `custom_agents/paper/lib/`.
The optional local `.NET` runtime bootstrap lives under `custom_agents/paper/.dotnet/`.
Linux native assets such as `libSkiaSharp.so` are still baked into the container image.

## Commands

- `template-rules`
- `split-sections`
- `process-section`
- `aggregate`
- `pipeline`

## Notes

- Input/output format is `.docx -> .docx`
- Template outline is the source of truth
- `SectionProcessorAgent` performs content organization/minimal completion, style formatting, and section-level review
