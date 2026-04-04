from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAPER_PACKAGE_ROOT = ROOT / "custom_agents" / "paper"
if str(PAPER_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PAPER_PACKAGE_ROOT))

from paper.core.orchestrator import PaperPipelineService
from paper.models.contracts import OutlineItem


class FakeExecutor:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path

    def extract_outline_candidates(self, docx_path: str):
        name = Path(docx_path).name
        if "template" in name:
            return [
                {
                    "id": "h1",
                    "title": "Introduction",
                    "normalized_title": "introduction",
                    "candidate_level": 1,
                    "level": 1,
                    "order": 1,
                    "source_paragraph_index": 0,
                    "style_name": "Heading 1",
                    "page_index": 1,
                    "path": ["Introduction"],
                    "section_role": "body",
                    "paragraph_role": None,
                    "is_probable_caption": False,
                    "is_probable_toc": False,
                },
                {
                    "id": "h2",
                    "title": "Methods",
                    "normalized_title": "methods",
                    "candidate_level": 1,
                    "level": 1,
                    "order": 2,
                    "source_paragraph_index": 3,
                    "style_name": "Heading 1",
                    "page_index": 2,
                    "path": ["Methods"],
                    "section_role": "body",
                    "paragraph_role": None,
                    "is_probable_caption": False,
                    "is_probable_toc": False,
                },
            ]
        return []

    def extract_outline(self, docx_path: str):
        name = Path(docx_path).name
        if "template" in name:
            return [
                OutlineItem(id="h1", title="Introduction", normalized_title="introduction", level=1, order=1, source_paragraph_index=0),
                OutlineItem(id="h2", title="Methods", normalized_title="methods", level=1, order=2, source_paragraph_index=3),
            ]
        return [
            OutlineItem(id="s1", title="Introduction", normalized_title="introduction", level=1, order=1, source_paragraph_index=0),
        ]

    def extract_style_profile(self, docx_path: str, outline):
        return {
            "heading_styles": {"1": {"style_name": "Heading 1"}},
            "body_style": {"style_name": "Body Text"},
            "caption_style": {"style_name": "Caption"},
            "body_profiles": {"default": {"style_name": "Body Text"}},
            "heading_profiles": {"1": {"style_name": "Heading 1"}},
            "caption_profiles": {"caption": {"style_name": "Caption"}},
            "reference_profile": {"style_name": "References"},
            "front_matter_profiles": {"ordered": [{"style_name": "Front Title"}], "default": {"style_name": "Front Body"}},
            "table_profiles": {"default": {"style_name": "Table Grid", "header_row_profile": {}, "body_row_profile": {}}},
            "section_layout_profiles": [{"section_index": 0, "page_width": 595.0}],
            "style_catalog": [],
        }

    def extract_structure(self, docx_path: str, outline=None):
        name = Path(docx_path).name
        if "template" in name:
            blocks = [
                {
                    "block_key": "p:0",
                    "block_type": "paragraph",
                    "block_index": 0,
                    "paragraph_index": 0,
                    "text": "Introduction",
                    "normalized_text": "introduction",
                    "style_name": "Heading 1",
                    "section_path": [{"normalized_title": "introduction", "title": "Introduction"}],
                    "section_role": "body",
                    "paragraph_role": None,
                    "metadata": {},
                },
                {
                    "block_key": "p:1",
                    "block_type": "paragraph",
                    "block_index": 1,
                    "paragraph_index": 1,
                    "text": "Methods",
                    "normalized_text": "methods",
                    "style_name": "Heading 1",
                    "section_path": [{"normalized_title": "methods", "title": "Methods"}],
                    "section_role": "body",
                    "paragraph_role": None,
                    "metadata": {},
                },
            ]
        else:
            blocks = [
                {
                    "block_key": "p:0",
                    "block_type": "paragraph",
                    "block_index": 0,
                    "paragraph_index": 0,
                    "text": "Introduction",
                    "normalized_text": "introduction",
                    "style_name": "Heading 1",
                    "section_path": [{"normalized_title": "introduction", "title": "Introduction"}],
                    "section_role": "body",
                    "paragraph_role": None,
                    "metadata": {},
                }
            ]
        return {
            "statistics": {
                "block_count": len(blocks),
                "paragraph_count": len(blocks),
                "table_count": 0,
                "image_count": 0,
            },
            "blocks": blocks,
            "page_setup": [{"page_width": 595.0, "left_margin": 90.0, "right_margin": 90.0}],
            "section_layouts": [{"section_index": 0, "page_width": 595.0, "left_margin": 90.0, "right_margin": 90.0}],
            "document_styles": [],
        }

    def split_to_section_docs(self, source_docx_path: str, source_outline, output_dir: str):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        mapping = {}
        for item in source_outline:
            path = Path(output_dir) / f"{item.id}.docx"
            path.write_text(item.title, encoding="utf-8")
            mapping[item.id] = str(path)
        return mapping

    def rewrite_section_content(self, chunk, rules, output_docx_path: str):
        output = Path(output_docx_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(chunk.template_title, encoding="utf-8")
        if chunk.missing_required_content:
            return str(output), ["create_placeholder_section"], dict(chunk.statistics)
        return str(output), ["import_source_blocks:1"], dict(chunk.statistics)

    def apply_section_styles(self, section_docx_path: str, chunk, rules):
        return section_docx_path, ["apply_heading_style", "apply_body_style"], ["heading", "body_paragraph"]

    def validate_section_layout(self, section_docx_path: str, chunk, rules):
        return [], {"block_count": 1, "paragraph_count": 1, "table_count": 0, "image_count": 0}, list(chunk.risk_flags)

    def merge_section_docs(self, ordered_section_paths, output_docx_path: str, template_docx_path: str | None = None):
        output = Path(output_docx_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(Path(path).read_text(encoding="utf-8") for path in ordered_section_paths), encoding="utf-8")
        return str(output)

    def validate_outline_alignment(self, docx_path: str, rules):
        return True, []


def test_split_sections_preserves_template_coverage(tmp_path: Path):
    service = PaperPipelineService(executor=FakeExecutor(tmp_path))
    source = tmp_path / "source.docx"
    template = tmp_path / "template.docx"
    source.write_text("source", encoding="utf-8")
    template.write_text("template", encoding="utf-8")

    rules = service.extract_template_rules(str(template))
    chunks = service.split_sections(str(source), rules, str(tmp_path / "sections.json"))

    assert len(chunks) == 2
    assert chunks[0].template_title == "Introduction"
    assert chunks[1].template_title == "Methods"
    assert chunks[1].missing_required_content is True
    assert chunks[1].source_block_keys == []
    assert chunks[0].template_section_index == 0
    assert chunks[0].layout_flow_mode in {"continuous", "new_page"}
    assert isinstance(chunks[0].keep_with_next_hints, list)
    assert "heading" in chunks[0].target_element_style_slots


def test_run_pipeline_produces_final_report(tmp_path: Path):
    service = PaperPipelineService(executor=FakeExecutor(tmp_path))
    source = tmp_path / "source.docx"
    template = tmp_path / "template.docx"
    final = tmp_path / "final.docx"
    report = tmp_path / "report.json"
    source.write_text("source", encoding="utf-8")
    template.write_text("template", encoding="utf-8")

    result = service.run_pipeline(str(source), str(template), str(final), str(report))

    assert result["success"] is True
    assert result["section_count"] == 2
    assert Path(result["final_docx_path"]).exists()
    assert report.exists()
    assert "artifacts_dir" in result
    report_payload = json.loads(report.read_text(encoding="utf-8"))
    assert "pagination_warnings" in report_payload
    assert "section_break_warnings" in report_payload
    assert "excess_blank_space_warnings" in report_payload
    assert report_payload["processing_stats"]["section_count_before_merge"] == 2


def test_extract_template_rules_records_outline_generation_metadata(tmp_path: Path):
    service = PaperPipelineService(executor=FakeExecutor(tmp_path))
    template = tmp_path / "template.docx"
    template.write_text("template", encoding="utf-8")

    rules = service.extract_template_rules(str(template))

    assert rules.outline_generation_mode == "rules_only"
    assert rules.outline_confirmation_notes
    assert len(rules.outline_candidates_summary) == 2
    assert "introduction" in rules.section_element_style_map
    assert "heading" in rules.section_element_style_map["introduction"]["element_styles"]


def test_extract_template_rules_uses_llm_confirmation_when_available(tmp_path: Path):
    class LlmExecutor(FakeExecutor):
        def confirm_outline_with_llm(self, template_docx_path: str, outline_candidates, provisional_outline):
            return {
                "confirmed_outline": [
                    {
                        "id": "h2",
                        "title": "Methods",
                        "level": 1,
                        "source_paragraph_index": 3,
                    }
                ]
            }

    service = PaperPipelineService(executor=LlmExecutor(tmp_path))
    template = tmp_path / "template.docx"
    template.write_text("template", encoding="utf-8")

    rules = service.extract_template_rules(str(template))

    assert rules.outline_generation_mode == "rules_plus_llm"
    assert [item.title for item in rules.template_outline] == ["Methods"]
