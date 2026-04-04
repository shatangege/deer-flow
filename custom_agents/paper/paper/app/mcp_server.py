from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..core.orchestrator import PaperPipelineService
from .mcp_low_level import PaperLowLevelMcpService
from .shared_paths import resolve_existing_file, resolve_output_file


SERVER_NAME = "paper"
SERVER_VERSION = "0.2.0"
HTTP_HOST = os.getenv("PAPER_HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("PAPER_HTTP_PORT", os.getenv("PORT", "8766")))
HTTP_PATH = os.getenv("PAPER_HTTP_PATH", "/mcp")

app = FastMCP(
    name=SERVER_NAME,
    host=HTTP_HOST,
    port=HTTP_PORT,
    streamable_http_path=HTTP_PATH,
)


def _log(message: str, **fields: object) -> None:
    payload = {"message": message, **fields}
    sys.stderr.write(f"[paper-mcp] {json.dumps(payload, ensure_ascii=False)}\n")
    sys.stderr.flush()


def _result(payload: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    return {
        "isError": is_error,
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "structuredContent": payload,
    }


def _service() -> PaperPipelineService:
    return PaperPipelineService()


def _low_level_service() -> PaperLowLevelMcpService:
    return PaperLowLevelMcpService()


@app.tool(name="extract_paper_template_rules", description="Extract template outline and style rules for the paper pipeline.")
def extract_paper_template_rules(template_docx_path: str, output_json_path: str, thread_id: str | None = None) -> dict[str, Any]:
    try:
        template_path = resolve_existing_file("template_docx_path", template_docx_path, thread_id)
        output_path = resolve_output_file(output_json_path, thread_id)
        rules = _service().extract_template_rules(str(template_path), str(output_path))
        return _result({"success": True, "rules_json_path": str(output_path), "rule_bundle": rules.to_dict()})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="load_document", description="Load a paper document through Aspose and return lightweight metadata.")
def load_document(docx_path: str, thread_id: str | None = None) -> dict[str, Any]:
    try:
        resolved_path = resolve_existing_file("docx_path", docx_path, thread_id)
        payload = _low_level_service().load_document(str(resolved_path))
        return _result({"success": True, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="extract_outline", description="Extract a document outline using the low-level Aspose execution layer.")
def extract_outline(docx_path: str, output_json_path: str | None = None, thread_id: str | None = None) -> dict[str, Any]:
    try:
        resolved_path = resolve_existing_file("docx_path", docx_path, thread_id)
        output_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        payload = _low_level_service().extract_outline(str(resolved_path), str(output_path) if output_path else None)
        return _result({"success": True, "output_json_path": str(output_path) if output_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="extract_outline_candidates", description="Extract outline candidates using the low-level Aspose execution layer.")
def extract_outline_candidates(docx_path: str, output_json_path: str | None = None, thread_id: str | None = None) -> dict[str, Any]:
    try:
        resolved_path = resolve_existing_file("docx_path", docx_path, thread_id)
        output_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        payload = _low_level_service().extract_outline_candidates(str(resolved_path), str(output_path) if output_path else None)
        return _result({"success": True, "output_json_path": str(output_path) if output_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="extract_structure", description="Extract a document structure payload using the low-level Aspose execution layer.")
def extract_structure(
    docx_path: str,
    output_json_path: str | None = None,
    outline_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        resolved_path = resolve_existing_file("docx_path", docx_path, thread_id)
        output_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        outline_path = resolve_existing_file("outline_json_path", outline_json_path, thread_id) if outline_json_path else None
        payload = _low_level_service().extract_structure(
            str(resolved_path),
            str(output_path) if output_path else None,
            str(outline_path) if outline_path else None,
        )
        return _result({"success": True, "output_json_path": str(output_path) if output_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="extract_style_profile", description="Extract a style profile using the low-level Aspose execution layer.")
def extract_style_profile(
    docx_path: str,
    output_json_path: str | None = None,
    outline_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        resolved_path = resolve_existing_file("docx_path", docx_path, thread_id)
        output_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        outline_path = resolve_existing_file("outline_json_path", outline_json_path, thread_id) if outline_json_path else None
        payload = _low_level_service().extract_style_profile(
            str(resolved_path),
            str(output_path) if output_path else None,
            str(outline_path) if outline_path else None,
        )
        return _result({"success": True, "output_json_path": str(output_path) if output_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="split_to_section_docs", description="Split a source paper into per-section documents using the low-level Aspose execution layer.")
def split_to_section_docs(
    source_docx_path: str,
    output_dir: str,
    output_json_path: str | None = None,
    outline_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        source_path = resolve_existing_file("source_docx_path", source_docx_path, thread_id)
        output_dir_path = resolve_output_file(str(Path(output_dir) / ".keep"), thread_id).parent
        output_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        outline_path = resolve_existing_file("outline_json_path", outline_json_path, thread_id) if outline_json_path else None
        payload = _low_level_service().split_to_section_docs(
            str(source_path),
            str(output_dir_path),
            str(output_path) if output_path else None,
            str(outline_path) if outline_path else None,
        )
        return _result(
            {
                "success": True,
                "output_dir": str(output_dir_path),
                "output_json_path": str(output_path) if output_path else None,
                **payload,
            }
        )
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="rewrite_section_content", description="Rewrite one section content payload using the low-level Aspose execution layer.")
def rewrite_section_content(
    section_chunk_json_path: str,
    rules_json_path: str,
    output_docx_path: str,
    output_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        chunk_path = resolve_existing_file("section_chunk_json_path", section_chunk_json_path, thread_id)
        rules_path = resolve_existing_file("rules_json_path", rules_json_path, thread_id)
        output_path = resolve_output_file(output_docx_path, thread_id)
        result_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        payload = _low_level_service().rewrite_section_content(
            str(chunk_path),
            str(rules_path),
            str(output_path),
            str(result_path) if result_path else None,
        )
        return _result({"success": True, "output_json_path": str(result_path) if result_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="apply_section_styles", description="Apply section styles using the low-level Aspose execution layer.")
def apply_section_styles(
    input_docx_path: str,
    section_chunk_json_path: str,
    rules_json_path: str,
    output_docx_path: str,
    output_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        input_path = resolve_existing_file("input_docx_path", input_docx_path, thread_id)
        chunk_path = resolve_existing_file("section_chunk_json_path", section_chunk_json_path, thread_id)
        rules_path = resolve_existing_file("rules_json_path", rules_json_path, thread_id)
        output_path = resolve_output_file(output_docx_path, thread_id)
        result_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        payload = _low_level_service().apply_section_styles(
            str(input_path),
            str(chunk_path),
            str(rules_path),
            str(output_path),
            str(result_path) if result_path else None,
        )
        return _result({"success": True, "output_json_path": str(result_path) if result_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="validate_section_layout", description="Validate section layout using the low-level Aspose execution layer.")
def validate_section_layout(
    input_docx_path: str,
    section_chunk_json_path: str,
    rules_json_path: str,
    output_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        input_path = resolve_existing_file("input_docx_path", input_docx_path, thread_id)
        chunk_path = resolve_existing_file("section_chunk_json_path", section_chunk_json_path, thread_id)
        rules_path = resolve_existing_file("rules_json_path", rules_json_path, thread_id)
        result_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        payload = _low_level_service().validate_section_layout(
            str(input_path),
            str(chunk_path),
            str(rules_path),
            str(result_path) if result_path else None,
        )
        return _result({"success": True, "output_json_path": str(result_path) if result_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="merge_section_docs", description="Merge processed section documents using the low-level Aspose execution layer.")
def merge_section_docs(
    ordered_section_docx_paths: list[str],
    output_docx_path: str,
    template_docx_path: str | None = None,
    output_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        resolved_paths = [str(resolve_existing_file("ordered_section_docx_paths", item, thread_id)) for item in ordered_section_docx_paths]
        output_path = resolve_output_file(output_docx_path, thread_id)
        template_path = resolve_existing_file("template_docx_path", template_docx_path, thread_id) if template_docx_path else None
        result_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        payload = _low_level_service().merge_section_docs(
            resolved_paths,
            str(output_path),
            str(template_path) if template_path else None,
            str(result_path) if result_path else None,
        )
        return _result({"success": True, "output_json_path": str(result_path) if result_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="normalize_section_flow", description="Normalize section starts and pagination flow using the low-level Aspose execution layer.")
def normalize_section_flow(
    input_docx_path: str,
    output_docx_path: str,
    output_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        input_path = resolve_existing_file("input_docx_path", input_docx_path, thread_id)
        output_path = resolve_output_file(output_docx_path, thread_id)
        result_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        payload = _low_level_service().normalize_section_flow(
            str(input_path),
            str(output_path),
            str(result_path) if result_path else None,
        )
        return _result({"success": True, "output_json_path": str(result_path) if result_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="validate_outline_alignment", description="Validate outline alignment against a rule bundle using the low-level Aspose execution layer.")
def validate_outline_alignment(
    docx_path: str,
    rules_json_path: str,
    output_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        resolved_path = resolve_existing_file("docx_path", docx_path, thread_id)
        rules_path = resolve_existing_file("rules_json_path", rules_json_path, thread_id)
        result_path = resolve_output_file(output_json_path, thread_id) if output_json_path else None
        payload = _low_level_service().validate_outline_alignment(
            str(resolved_path),
            str(rules_path),
            str(result_path) if result_path else None,
        )
        return _result({"success": True, "output_json_path": str(result_path) if result_path else None, **payload})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="split_paper_sections", description="Split a source paper into template-aligned section chunks.")
def split_paper_sections(source_docx_path: str, rules_json_path: str, output_json_path: str, thread_id: str | None = None) -> dict[str, Any]:
    try:
        source_path = resolve_existing_file("source_docx_path", source_docx_path, thread_id)
        rules_path = resolve_existing_file("rules_json_path", rules_json_path, thread_id)
        output_path = resolve_output_file(output_json_path, thread_id)
        sections = _service().split_sections(str(source_path), str(rules_path), str(output_path))
        return _result({"success": True, "sections_json_path": str(output_path), "sections": [item.to_dict() for item in sections]})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="process_paper_section", description="Process one paper section with content organization, minimal completion, styling, and section-level review.")
def process_paper_section(
    section_chunk_json_path: str,
    rules_json_path: str,
    output_docx_path: str,
    result_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        chunk_path = resolve_existing_file("section_chunk_json_path", section_chunk_json_path, thread_id)
        rules_path = resolve_existing_file("rules_json_path", rules_json_path, thread_id)
        output_path = resolve_output_file(output_docx_path, thread_id)
        result_path = resolve_output_file(result_json_path, thread_id) if result_json_path else None
        result = _service().process_section(str(chunk_path), str(rules_path), str(output_path), str(result_path) if result_path else None)
        return _result({"success": True, **result.to_dict()})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="aggregate_paper_sections", description="Aggregate processed paper sections into the final template-aligned paper.")
def aggregate_paper_sections(
    section_results_json_path: str,
    rules_json_path: str,
    final_docx_path: str,
    report_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        section_results_path = resolve_existing_file("section_results_json_path", section_results_json_path, thread_id)
        rules_path = resolve_existing_file("rules_json_path", rules_json_path, thread_id)
        final_path = resolve_output_file(final_docx_path, thread_id)
        report_path = resolve_output_file(report_json_path, thread_id) if report_json_path else None
        report = _service().aggregate_sections(
            str(section_results_path),
            str(rules_path),
            str(final_path),
            str(report_path) if report_path else None,
        )
        return _result({"success": True, **report.to_dict()})
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


@app.tool(name="run_paper_pipeline", description="Run the full paper pipeline from source docx + template docx to final formatted paper.")
def run_paper_pipeline(
    source_docx_path: str,
    template_docx_path: str,
    final_docx_path: str,
    report_json_path: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    try:
        source_path = resolve_existing_file("source_docx_path", source_docx_path, thread_id)
        template_path = resolve_existing_file("template_docx_path", template_docx_path, thread_id)
        final_path = resolve_output_file(final_docx_path, thread_id)
        report_path = resolve_output_file(report_json_path, thread_id) if report_json_path else None
        result = _service().run_pipeline(
            str(source_path),
            str(template_path),
            str(final_path),
            str(report_path) if report_path else None,
        )
        return _result(result, is_error=not result.get("success", False))
    except Exception as exc:
        return _result({"success": False, "error": str(exc)}, is_error=True)


def main() -> int:
    _log(
        "server_start",
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        cwd=os.getcwd(),
        host=HTTP_HOST,
        port=HTTP_PORT,
        path=HTTP_PATH,
    )
    try:
        app.run(transport="streamable-http")
    finally:
        _log("server_stop")
    return 0
