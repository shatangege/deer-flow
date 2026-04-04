from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAPER_PACKAGE_ROOT = ROOT / "custom_agents" / "paper"
if str(PAPER_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PAPER_PACKAGE_ROOT))

from paper.app import mcp_server  # noqa: E402


def test_paper_mcp_registers_low_level_tools():
    tool_names = {tool.name for tool in mcp_server.app._tool_manager.list_tools()}
    expected = {
        "load_document",
        "extract_outline",
        "extract_outline_candidates",
        "extract_structure",
        "extract_style_profile",
        "split_to_section_docs",
        "rewrite_section_content",
        "apply_section_styles",
        "validate_section_layout",
        "merge_section_docs",
        "normalize_section_flow",
        "validate_outline_alignment",
        "extract_paper_template_rules",
        "split_paper_sections",
        "process_paper_section",
        "aggregate_paper_sections",
        "run_paper_pipeline",
        "run_paper_pipeline_with_repair",
    }
    assert expected.issubset(tool_names)


def test_low_level_extract_outline_handler_returns_structured_content(tmp_path: Path, monkeypatch):
    docx_path = tmp_path / "sample.docx"
    output_json_path = tmp_path / "outline.json"
    docx_path.write_text("placeholder", encoding="utf-8")

    class FakeLowLevelService:
        def extract_outline(self, docx_path: str, output_json_path: str | None = None):
            payload = {"outline": [{"id": "h1", "title": "Intro"}]}
            if output_json_path:
                Path(output_json_path).write_text(json.dumps(payload), encoding="utf-8")
            return payload

    monkeypatch.setattr(mcp_server, "_low_level_service", lambda: FakeLowLevelService())

    result = mcp_server.extract_outline(str(docx_path), str(output_json_path))

    assert result["isError"] is False
    assert result["structuredContent"]["success"] is True
    assert result["structuredContent"]["outline"][0]["title"] == "Intro"
    assert Path(output_json_path).exists()


def test_low_level_validate_outline_alignment_handler_surfaces_errors(tmp_path: Path, monkeypatch):
    docx_path = tmp_path / "sample.docx"
    rules_path = tmp_path / "rules.json"
    docx_path.write_text("placeholder", encoding="utf-8")
    rules_path.write_text("{}", encoding="utf-8")

    class FakeLowLevelService:
        def validate_outline_alignment(self, docx_path: str, rules_json_path: str, output_json_path: str | None = None):
            return {
                "docx_path": docx_path,
                "outline_pass": False,
                "missing_sections": ["Methods"],
            }

    monkeypatch.setattr(mcp_server, "_low_level_service", lambda: FakeLowLevelService())

    result = mcp_server.validate_outline_alignment(str(docx_path), str(rules_path))

    assert result["isError"] is False
    assert result["structuredContent"]["outline_pass"] is False
    assert result["structuredContent"]["missing_sections"] == ["Methods"]
