from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models.contracts import AggregateReport, RepairPlan, RuleBundle, SectionChunk, SectionResult
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

    def extract_template_rules(self, template_docx_path: str, output_json_path: str | None = None, outline_mode: str = "aspose_plus_llm") -> RuleBundle:
        rules, _, _ = self.template_rule_agent.run(template_docx_path, outline_mode=outline_mode)
        if output_json_path:
            write_json(output_json_path, rules.to_dict())
        return rules

    def split_sections(self, source_docx_path: str, rules: RuleBundle | str, output_json_path: str, outline_mode: str | None = None) -> list[SectionChunk]:
        loaded_rules = self._load_rules(rules)
        split_root = str(Path(output_json_path).expanduser().resolve().parent / "sections")
        chunks, _, _ = self.flow_scheduler_agent.run(source_docx_path, loaded_rules, split_root, outline_mode=outline_mode)
        if isinstance(rules, str):
            write_json(rules, loaded_rules.to_dict())
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
        outline_mode: str = "aspose_plus_llm",
    ) -> dict[str, Any]:
        artifacts = build_pipeline_artifacts(source_docx_path, template_docx_path, final_docx_path)
        Path(artifacts.workspace).mkdir(parents=True, exist_ok=True)
        Path(artifacts.processed_sections_dir).mkdir(parents=True, exist_ok=True)
        effective_report_path = report_json_path or artifacts.aggregate_report
        state = self._run_pipeline_once(
            source_docx_path=source_docx_path,
            template_docx_path=template_docx_path,
            artifacts=artifacts,
            report_json_path=effective_report_path,
            outline_mode=outline_mode,
        )
        return self._pipeline_result_payload(state["report"], len(state["results"]), artifacts.workspace, effective_report_path, state["rules"])

    def run_pipeline_with_repair(
        self,
        source_docx_path: str,
        template_docx_path: str,
        final_docx_path: str,
        report_json_path: str | None = None,
        outline_mode: str = "aspose_plus_llm",
    ) -> dict[str, Any]:
        artifacts = build_pipeline_artifacts(source_docx_path, template_docx_path, final_docx_path)
        Path(artifacts.workspace).mkdir(parents=True, exist_ok=True)
        Path(artifacts.processed_sections_dir).mkdir(parents=True, exist_ok=True)
        effective_report_path = report_json_path or artifacts.aggregate_report
        state = self._run_pipeline_once(
            source_docx_path=source_docx_path,
            template_docx_path=template_docx_path,
            artifacts=artifacts,
            report_json_path=effective_report_path,
            outline_mode=outline_mode,
        )
        initial_report: AggregateReport = state["report"]
        repair_executed = False
        repaired_scope = "none"
        if initial_report.repair_candidates and initial_report.recommended_next_step != "no_repair_needed":
            repaired_scope = self._execute_repair_cycle(
                source_docx_path=source_docx_path,
                template_docx_path=template_docx_path,
                artifacts=artifacts,
                report=initial_report,
                state=state,
                report_json_path=effective_report_path,
                outline_mode=outline_mode,
            )
            repair_executed = repaired_scope != "none"
            if repair_executed:
                state = self._load_pipeline_state_from_artifacts(artifacts, effective_report_path)
        payload = self._pipeline_result_payload(state["report"], len(state["results"]), artifacts.workspace, effective_report_path, state["rules"])
        payload.update(
            {
                "repair_attempted": repair_executed,
                "repair_scope": repaired_scope,
            }
        )
        return payload

    def _pipeline_result_payload(
        self,
        report: AggregateReport,
        section_count: int,
        artifacts_dir: str,
        report_json_path: str,
        rules: RuleBundle | None = None,
    ) -> dict[str, Any]:
        payload = {
            "success": report.outline_pass,
            "final_docx_path": report.final_docx_path,
            "report_json_path": report_json_path,
            "artifacts_dir": artifacts_dir,
            "outline_pass": report.outline_pass,
            "section_count": section_count,
            "missing_sections": report.missing_sections,
            "style_warnings": report.style_warnings,
            "layout_warnings": report.layout_warnings,
            "front_matter_warnings": report.front_matter_warnings,
            "content_integrity_warnings": report.content_integrity_warnings,
            "unmapped_source_blocks": report.unmapped_source_blocks,
            "recommended_next_step": report.recommended_next_step,
            "repair_candidates": [item.to_dict() for item in report.repair_candidates],
        }
        if rules is not None:
            payload.update(
                {
                    "outline_mode": rules.outline_mode,
                    "effective_outline_mode": rules.effective_outline_mode,
                    "outline_generation_mode": rules.outline_generation_mode,
                    "template_outline_generation": dict(rules.template_outline_generation or {}),
                    "source_outline_generation": dict(rules.source_outline_generation or {}),
                }
            )
        return payload

    def _run_pipeline_once(
        self,
        *,
        source_docx_path: str,
        template_docx_path: str,
        artifacts: PipelineArtifacts,
        report_json_path: str,
        outline_mode: str,
    ) -> dict[str, Any]:
        rules, _, _ = self.template_rule_agent.run(template_docx_path, outline_mode=outline_mode)
        write_json(artifacts.template_rules, rules.to_dict())
        write_json(
            artifacts.template_outline_candidates,
            {
                "outline_mode": rules.outline_mode,
                "effective_outline_mode": rules.effective_outline_mode,
                "outline_generation_mode": rules.outline_generation_mode,
                "outline_confirmation_notes": rules.outline_confirmation_notes,
                "template_outline_generation": rules.template_outline_generation,
                "outline_candidates": rules.outline_candidates_summary,
            },
        )
        chunks, source_structure, _ = self.flow_scheduler_agent.run(
            source_docx_path,
            rules,
            str(Path(artifacts.workspace) / "sections"),
            outline_mode=outline_mode,
        )
        write_json(artifacts.template_rules, rules.to_dict())
        write_json(
            artifacts.source_outline,
            {
                "outline_mode": rules.outline_mode,
                "effective_outline_mode": (rules.source_outline_generation or {}).get("effective_outline_mode", rules.effective_outline_mode),
                "outline_generation_mode": (rules.source_outline_generation or {}).get("outline_generation_mode", "rules_only"),
                "source_outline_generation": rules.source_outline_generation,
                "outline": list((rules.source_outline_generation or {}).get("outline", [])),
            },
        )
        write_json(artifacts.source_structure, source_structure)
        write_json(artifacts.section_chunks, {"sections": [chunk.to_dict() for chunk in chunks]})
        results = self._process_chunks(chunks, rules, artifacts)
        report = self.aggregate_sections(results, rules, artifacts.final_docx, report_json_path)
        return {
            "rules": rules,
            "chunks": chunks,
            "results": results,
            "report": report,
        }

    def _process_chunks(self, chunks: list[SectionChunk], rules: RuleBundle, artifacts: PipelineArtifacts) -> list[SectionResult]:
        results: list[SectionResult] = []
        for index, chunk in enumerate(chunks, start=1):
            section_docx = Path(artifacts.processed_sections_dir) / f"{index:03d}-{chunk.template_section_id}.docx"
            section_json = Path(artifacts.processed_sections_dir) / f"{index:03d}-{chunk.template_section_id}.json"
            results.append(self.process_section(chunk, rules, str(section_docx), str(section_json)))
        write_json(artifacts.section_results, {"results": [result.to_dict() for result in results]})
        return results

    def _execute_repair_cycle(
        self,
        *,
        source_docx_path: str,
        template_docx_path: str,
        artifacts: PipelineArtifacts,
        report: AggregateReport,
        state: dict[str, Any],
        report_json_path: str,
        outline_mode: str,
    ) -> str:
        recommended = report.recommended_next_step
        if recommended == "repair_mapping_then_reprocess_sections":
            refreshed_rules = self.extract_template_rules(template_docx_path, artifacts.template_rules, outline_mode=outline_mode)
            chunks, _, _ = self.flow_scheduler_agent.run(source_docx_path, refreshed_rules, str(Path(artifacts.workspace) / "sections"), outline_mode=outline_mode)
            write_json(artifacts.template_rules, refreshed_rules.to_dict())
            write_json(artifacts.section_chunks, {"sections": [chunk.to_dict() for chunk in chunks]})
            results = self._process_chunks(chunks, refreshed_rules, artifacts)
            self.aggregate_sections(results, refreshed_rules, artifacts.final_docx, report_json_path)
            return "mapping"
        if recommended == "repair_sections_then_reaggregate":
            rules = state["rules"]
            chunks = state["chunks"]
            results = list(state["results"])
            target_titles = {plan.target_section_title for plan in report.repair_candidates if plan.retry_scope == "single_section" and plan.target_section_title}
            if not target_titles:
                target_titles = {chunk.template_title for chunk in chunks}
            result_by_chunk = {result.chunk_id: result for result in results}
            for index, chunk in enumerate(chunks, start=1):
                if chunk.template_title not in target_titles:
                    continue
                section_docx = Path(artifacts.processed_sections_dir) / f"{index:03d}-{chunk.template_section_id}.docx"
                section_json = Path(artifacts.processed_sections_dir) / f"{index:03d}-{chunk.template_section_id}.json"
                result_by_chunk[chunk.chunk_id] = self.process_section(chunk, rules, str(section_docx), str(section_json))
            refreshed_results = [result_by_chunk[chunk.chunk_id] for chunk in chunks]
            write_json(artifacts.section_results, {"results": [result.to_dict() for result in refreshed_results]})
            self.aggregate_sections(refreshed_results, rules, artifacts.final_docx, report_json_path)
            return "single_section"
        if recommended == "rerun_merge_and_layout_normalization":
            self.aggregate_sections(state["results"], state["rules"], artifacts.final_docx, report_json_path)
            return "merge_only"
        if recommended == "rerun_target_outline_and_aggregate":
            self._run_pipeline_once(
                source_docx_path=source_docx_path,
                template_docx_path=template_docx_path,
                artifacts=artifacts,
                report_json_path=report_json_path,
                outline_mode=outline_mode,
            )
            return "global"
        return "none"


    def _load_pipeline_state_from_artifacts(self, artifacts: PipelineArtifacts, report_json_path: str) -> dict[str, Any]:
        rules = self._load_rules(artifacts.template_rules)
        chunk_payload = read_json(artifacts.section_chunks)
        chunks = [SectionChunk.from_dict(item) for item in chunk_payload.get("sections", [])]
        results = self._load_results(artifacts.section_results)
        report_payload = read_json(report_json_path)
        return {
            "rules": rules,
            "chunks": chunks,
            "results": results,
            "report": AggregateReport(**report_payload),
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
