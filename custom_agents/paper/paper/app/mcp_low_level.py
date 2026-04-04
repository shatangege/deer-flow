from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..core.execution import AsposeExecutionAgent
from ..core.utils import read_json, write_json
from ..models.contracts import OutlineItem, RuleBundle, SectionChunk


class PaperLowLevelMcpService:
    def __init__(self, executor: AsposeExecutionAgent | None = None) -> None:
        self.executor = executor or AsposeExecutionAgent()

    def load_document(self, docx_path: str) -> dict[str, Any]:
        document = self.executor.load_document(docx_path)
        return {
            "docx_path": str(Path(docx_path).expanduser().resolve()),
            "file_size": Path(docx_path).expanduser().resolve().stat().st_size,
            "section_count": self.executor._safe_int(document.Sections.Count) or 0,
            "has_license_path": bool(os.getenv("ASPOSE_LICENSE_PATH") or self.executor.license_path),
        }

    def extract_outline(self, docx_path: str, output_json_path: str | None = None) -> dict[str, Any]:
        outline = self.executor.extract_outline(docx_path)
        payload = {"outline": [item.to_dict() for item in outline]}
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def extract_outline_candidates(self, docx_path: str, output_json_path: str | None = None) -> dict[str, Any]:
        candidates = self.executor.extract_outline_candidates(docx_path)
        payload = {"outline_candidates": candidates}
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def extract_structure(
        self,
        docx_path: str,
        output_json_path: str | None = None,
        outline_json_path: str | None = None,
    ) -> dict[str, Any]:
        outline = self._load_outline(outline_json_path) if outline_json_path else None
        payload = self.executor.extract_structure(docx_path, outline=outline)
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def extract_style_profile(
        self,
        docx_path: str,
        output_json_path: str | None = None,
        outline_json_path: str | None = None,
    ) -> dict[str, Any]:
        outline = self._load_outline(outline_json_path) if outline_json_path else self.executor.extract_outline(docx_path)
        payload = self.executor.extract_style_profile(docx_path, outline)
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def split_to_section_docs(
        self,
        source_docx_path: str,
        output_dir: str,
        output_json_path: str | None = None,
        outline_json_path: str | None = None,
    ) -> dict[str, Any]:
        outline = self._load_outline(outline_json_path) if outline_json_path else self.executor.extract_outline(source_docx_path)
        mapping = self.executor.split_to_section_docs(source_docx_path, outline, output_dir)
        payload = {
            "section_docx_map": mapping,
            "outline": [item.to_dict() for item in outline],
        }
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def rewrite_section_content(
        self,
        section_chunk_json_path: str,
        rules_json_path: str,
        output_docx_path: str,
        output_json_path: str | None = None,
    ) -> dict[str, Any]:
        chunk = self._load_chunk(section_chunk_json_path)
        rules = self._load_rules(rules_json_path)
        section_output_docx_path, content_actions, section_statistics_before = self.executor.rewrite_section_content(
            chunk,
            rules,
            output_docx_path,
        )
        payload = {
            "chunk_id": chunk.chunk_id,
            "section_output_docx_path": section_output_docx_path,
            "content_actions": content_actions,
            "section_statistics_before": section_statistics_before,
        }
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def apply_section_styles(
        self,
        input_docx_path: str,
        section_chunk_json_path: str,
        rules_json_path: str,
        output_docx_path: str,
        output_json_path: str | None = None,
    ) -> dict[str, Any]:
        chunk = self._load_chunk(section_chunk_json_path)
        rules = self._load_rules(rules_json_path)
        input_path = Path(input_docx_path).expanduser().resolve()
        output_path = Path(output_docx_path).expanduser().resolve()
        if input_path != output_path:
            output_path.write_bytes(input_path.read_bytes())
        section_output_docx_path, style_actions, applied_style_slots = self.executor.apply_section_styles(str(output_path), chunk, rules)
        payload = {
            "chunk_id": chunk.chunk_id,
            "section_output_docx_path": section_output_docx_path,
            "style_actions": style_actions,
            "applied_style_slots": applied_style_slots,
        }
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def validate_section_layout(
        self,
        input_docx_path: str,
        section_chunk_json_path: str,
        rules_json_path: str,
        output_json_path: str | None = None,
    ) -> dict[str, Any]:
        chunk = self._load_chunk(section_chunk_json_path)
        rules = self._load_rules(rules_json_path)
        validation_issues, section_statistics_after, remaining_risks = self.executor.validate_section_layout(input_docx_path, chunk, rules)
        payload = {
            "chunk_id": chunk.chunk_id,
            "validation_issues": validation_issues,
            "section_statistics_after": section_statistics_after,
            "remaining_risks": remaining_risks,
            "section_pass": not validation_issues,
        }
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def merge_section_docs(
        self,
        ordered_section_docx_paths: list[str],
        output_docx_path: str,
        template_docx_path: str | None = None,
        output_json_path: str | None = None,
    ) -> dict[str, Any]:
        final_docx_path = self.executor.merge_section_docs(
            ordered_section_docx_paths,
            output_docx_path,
            template_docx_path=template_docx_path,
        )
        payload = {
            "final_docx_path": final_docx_path,
            "section_count": len(ordered_section_docx_paths),
            "template_docx_path": template_docx_path,
        }
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def normalize_section_flow(
        self,
        input_docx_path: str,
        output_docx_path: str,
        output_json_path: str | None = None,
    ) -> dict[str, Any]:
        normalized_docx_path = self.executor.normalize_section_flow(input_docx_path, output_docx_path)
        payload = {
            "normalized_docx_path": normalized_docx_path,
        }
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def validate_outline_alignment(self, docx_path: str, rules_json_path: str, output_json_path: str | None = None) -> dict[str, Any]:
        rules = self._load_rules(rules_json_path)
        outline_pass, missing_sections = self.executor.validate_outline_alignment(docx_path, rules)
        payload = {
            "docx_path": str(Path(docx_path).expanduser().resolve()),
            "outline_pass": outline_pass,
            "missing_sections": missing_sections,
        }
        if output_json_path:
            write_json(output_json_path, payload)
        return payload

    def _load_outline(self, outline_json_path: str) -> list[OutlineItem]:
        payload = read_json(outline_json_path)
        return [OutlineItem(**item) for item in payload.get("outline", [])]

    def _load_rules(self, rules_json_path: str) -> RuleBundle:
        return RuleBundle.from_dict(read_json(rules_json_path))

    def _load_chunk(self, section_chunk_json_path: str) -> SectionChunk:
        payload = read_json(section_chunk_json_path)
        return SectionChunk.from_dict(payload)
