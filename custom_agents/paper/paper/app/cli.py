from __future__ import annotations

import argparse
import json
import sys

from ..core.orchestrator import PaperPipelineService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paper formatting pipeline")
    subparsers = parser.add_subparsers(dest="command")
    outline_mode_kwargs = {
        "choices": ["aspose_only", "aspose_plus_llm", "llm_only"],
        "default": "aspose_plus_llm",
        "help": "Outline recognition mode.",
    }

    template_rules = subparsers.add_parser("template-rules", help="Extract template rules")
    template_rules.add_argument("template_docx_path")
    template_rules.add_argument("output_json_path")
    template_rules.add_argument("--outline-mode", **outline_mode_kwargs)

    split_sections = subparsers.add_parser("split-sections", help="Split source paper into template-aligned sections")
    split_sections.add_argument("source_docx_path")
    split_sections.add_argument("rules_json_path")
    split_sections.add_argument("output_json_path")
    split_sections.add_argument("--outline-mode", **outline_mode_kwargs)

    process_section = subparsers.add_parser("process-section", help="Process one section chunk")
    process_section.add_argument("section_chunk_json_path")
    process_section.add_argument("rules_json_path")
    process_section.add_argument("output_docx_path")
    process_section.add_argument("--result-json-path")

    aggregate = subparsers.add_parser("aggregate", help="Aggregate processed sections into final paper")
    aggregate.add_argument("section_results_json_path")
    aggregate.add_argument("rules_json_path")
    aggregate.add_argument("final_docx_path")
    aggregate.add_argument("--report-json-path")

    pipeline = subparsers.add_parser("pipeline", help="Run the full paper pipeline in a single pass")
    pipeline.add_argument("source_docx_path")
    pipeline.add_argument("template_docx_path")
    pipeline.add_argument("final_docx_path")
    pipeline.add_argument("--report-json-path")
    pipeline.add_argument("--outline-mode", **outline_mode_kwargs)

    pipeline_repair = subparsers.add_parser("pipeline-repair", help="Run the full paper pipeline with one automatic repair cycle")
    pipeline_repair.add_argument("source_docx_path")
    pipeline_repair.add_argument("template_docx_path")
    pipeline_repair.add_argument("final_docx_path")
    pipeline_repair.add_argument("--report-json-path")
    pipeline_repair.add_argument("--outline-mode", **outline_mode_kwargs)

    return parser


def known_commands() -> set[str]:
    return {"template-rules", "split-sections", "process-section", "aggregate", "pipeline", "pipeline-repair"}


def dispatch_command(service: PaperPipelineService, args: argparse.Namespace):
    if args.command == "template-rules":
        result = service.extract_template_rules(args.template_docx_path, args.output_json_path, args.outline_mode)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return True
    if args.command == "split-sections":
        result = service.split_sections(args.source_docx_path, args.rules_json_path, args.output_json_path, args.outline_mode)
        print(json.dumps({"sections": [item.to_dict() for item in result]}, ensure_ascii=False, indent=2))
        return True
    if args.command == "process-section":
        result = service.process_section(
            args.section_chunk_json_path,
            args.rules_json_path,
            args.output_docx_path,
            args.result_json_path,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return True
    if args.command == "aggregate":
        result = service.aggregate_sections(
            args.section_results_json_path,
            args.rules_json_path,
            args.final_docx_path,
            args.report_json_path,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return True
    if args.command == "pipeline":
        result = service.run_pipeline(
            args.source_docx_path,
            args.template_docx_path,
            args.final_docx_path,
            args.report_json_path,
            args.outline_mode,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result["success"]
    if args.command == "pipeline-repair":
        result = service.run_pipeline_with_repair(
            args.source_docx_path,
            args.template_docx_path,
            args.final_docx_path,
            args.report_json_path,
            args.outline_mode,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result["success"]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    service = PaperPipelineService()
    result = dispatch_command(service, args)
    if result is None:
        parser.print_help()
        return 1
    return 0 if result else 1
