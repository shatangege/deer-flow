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

For normal formatting, prefer the repaired high-level path:

- `run_paper_pipeline_with_repair`

Use the plain `run_paper_pipeline` path when you explicitly want a single-pass run without the follow-up repair cycle.

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
- `pipeline-repair`

## Repair Cycle Outputs

The repaired high-level path returns these extra fields in addition to the normal pipeline result:

- `repair_attempted`
  - `true` when one automatic repair cycle was executed after the first aggregate review
  - `false` when no repair was needed or no safe repair scope was selected
- `repair_scope`
  - `none`: no follow-up repair run happened
  - `single_section`: only one or more flagged sections were reprocessed
  - `merge_only`: only aggregation/layout normalization was rerun
  - `mapping`: section mapping and downstream section processing were rerun
  - `global`: the full pipeline was rerun once
- `recommended_next_step`
  - high-level guidance for the caller about the next preferred action
  - common values include `no_repair_needed`, `repair_sections_then_reaggregate`, `repair_mapping_then_reprocess_sections`, and `rerun_merge_and_layout_normalization`

When consuming pipeline results from code or MCP:

- use `outline_pass` and `missing_sections` as the first hard gate
- use `repair_attempted` and `repair_scope` to understand whether the returned output already includes one repair pass
- use `recommended_next_step` and `repair_candidates` to decide whether to escalate to staged debugging or another controlled retry

## Notes

- Input/output format is `.docx -> .docx`
- Template outline is the source of truth
- `SectionProcessorAgent` performs content organization/minimal completion, style formatting, and section-level review
