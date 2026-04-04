from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models.contracts import AggregateReport, RuleBundle, SectionChunk, SectionResult
from .artifacts import PipelineArtifacts, build_pipeline_artifacts
from .execution import (
    AggregationReviewAgent,
    AsposeExecutionAgent,
    FlowSchedulerAgent,
    SectionProcessorAgent,
    TemplateRuleAgent,
)
from .utils import read_json, write_json


class PaperPipelineService:
    def __init__(self, executor: AsposeExecutionAgent | None = None) -> None:
        self.executor = executor or AsposeExecutionAgent()
        self.template_rule_agent = TemplateRuleAgent(self.executor)
        self.flow_scheduler_agent = FlowSchedulerAgent(self.executor)
        self.section_processor_agent = SectionProcessorAgent(self.executor)
        self.aggregation_review_agent = AggregationReviewAgent(self.executor)

    def extract_template_rules(self, template_docx_path: str, output_json_path: str | None = None) -> RuleBundle:
        rules, _, _ = self.template_rule_agent.run(template_docx_path)
        if output_json_path:
            write_json(output_json_path, rules.to_dict())
        return rules

    def split_sections(self, source_docx_path: str, rules: RuleBundle | str, output_json_path: str) -> list[SectionChunk]:
        loaded_rules = self._load_rules(rules)
        split_root = str(Path(output_json_path).expanduser().resolve().parent / "sections")
        chunks, _, _ = self.flow_scheduler_agent.run(source_docx_path, loaded_rules, split_root)
        write_json(output_json_path, {"sections": [chunk.to_dict() for chunk in chunks]})
        return chunks

    def process_section(
        self,
        section_chunk: SectionChunk | str,
        rules: RuleBundle | str,
        output_docx_path: str,
        output_json_path: str | None = None,
    ) -> SectionResult:
        chunk = self._load_chunk(section_chunk)
        loaded_rules = self._load_rules(rules)
        result = self.section_processor_agent.run(chunk, loaded_rules, output_docx_path)
        if output_json_path:
            write_json(output_json_path, result.to_dict())
        return result

    def aggregate_sections(
        self,
        section_results: list[SectionResult] | str,
        rules: RuleBundle | str,
        final_docx_path: str,
        report_json_path: str | None = None,
    ) -> AggregateReport:
        loaded_results = self._load_results(section_results)
        loaded_rules = self._load_rules(rules)
        _, report = self.aggregation_review_agent.run(loaded_results, loaded_rules, final_docx_path)
        if report_json_path:
            write_json(report_json_path, report.to_dict())
        return report

    def run_pipeline(
        self,
        source_docx_path: str,
        template_docx_path: str,
        final_docx_path: str,
        report_json_path: str | None = None,
    ) -> dict[str, Any]:
        artifacts = build_pipeline_artifacts(source_docx_path, template_docx_path, final_docx_path)
        Path(artifacts.workspace).mkdir(parents=True, exist_ok=True)
        Path(artifacts.processed_sections_dir).mkdir(parents=True, exist_ok=True)

        rules, _, _ = self.template_rule_agent.run(template_docx_path)
        write_json(artifacts.template_rules, rules.to_dict())
        write_json(
            artifacts.template_outline_candidates,
            {
                "outline_generation_mode": rules.outline_generation_mode,
                "outline_confirmation_notes": rules.outline_confirmation_notes,
                "outline_candidates": rules.outline_candidates_summary,
            },
        )

        source_outline = self.executor.extract_outline(source_docx_path)
        write_json(artifacts.source_outline, {"outline": [item.to_dict() for item in source_outline]})
        source_structure = self.executor.extract_structure(source_docx_path, outline=source_outline)
        write_json(artifacts.source_structure, source_structure)

        chunks, _, _ = self.flow_scheduler_agent.run(source_docx_path, rules, str(Path(artifacts.workspace) / "sections"))
        write_json(artifacts.section_chunks, {"sections": [chunk.to_dict() for chunk in chunks]})

        results: list[SectionResult] = []
        for index, chunk in enumerate(chunks, start=1):
            section_docx = Path(artifacts.processed_sections_dir) / f"{index:03d}-{chunk.template_section_id}.docx"
            section_json = Path(artifacts.processed_sections_dir) / f"{index:03d}-{chunk.template_section_id}.json"
            results.append(self.process_section(chunk, rules, str(section_docx), str(section_json)))

        write_json(artifacts.section_results, {"results": [result.to_dict() for result in results]})

        effective_report_path = report_json_path or artifacts.aggregate_report
        report = self.aggregate_sections(results, rules, artifacts.final_docx, effective_report_path)
        return {
            "success": report.outline_pass,
            "final_docx_path": report.final_docx_path,
            "report_json_path": effective_report_path,
            "artifacts_dir": artifacts.workspace,
            "outline_pass": report.outline_pass,
            "section_count": len(results),
            "missing_sections": report.missing_sections,
            "style_warnings": report.style_warnings,
            "layout_warnings": report.layout_warnings,
            "front_matter_warnings": report.front_matter_warnings,
        }

    def _load_rules(self, rules: RuleBundle | str) -> RuleBundle:
        if isinstance(rules, RuleBundle):
            return rules
        return RuleBundle.from_dict(read_json(rules))

    def _load_chunk(self, section_chunk: SectionChunk | str) -> SectionChunk:
        if isinstance(section_chunk, SectionChunk):
            return section_chunk
        payload = read_json(section_chunk)
        if "sections" in payload:
            raise ValueError("Expected a single section chunk JSON, got a section list payload.")
        return SectionChunk.from_dict(payload)

    def _load_results(self, section_results: list[SectionResult] | str) -> list[SectionResult]:
        if isinstance(section_results, list):
            return section_results
        payload = read_json(section_results)
        return [SectionResult.from_dict(item) for item in payload.get("results", [])]
