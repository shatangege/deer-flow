from __future__ import annotations

from typing import Any

from ..models.contracts import RepairPlan
from .utils import normalize_title


def summarize_outline_titles(outline_payload: list[dict[str, Any]]) -> list[str]:
    return [item.get("normalized_title", "") for item in outline_payload]


def summarize_structure(structure_payload: dict[str, Any]) -> dict[str, Any]:
    return dict(structure_payload.get("statistics", {}))


def front_matter_signature(structure_payload: dict[str, Any]) -> str:
    blocks = structure_payload.get("blocks", [])
    front_blocks = [item for item in blocks if item.get("section_role") == "front_matter" or item.get("metadata", {}).get("is_front_matter")]
    return " ".join(item.get("normalized_text", "") for item in front_blocks if item.get("normalized_text"))


def collect_table_width_issues(executor, docx_path: str) -> list[dict[str, Any]]:
    structure = executor.extract_structure(docx_path)
    issues: list[dict[str, Any]] = []
    available_width = None
    section_layouts = structure.get("section_layouts", [])
    if section_layouts:
        layout = section_layouts[0]
        try:
            available_width = float(layout["page_width"]) - float(layout["left_margin"]) - float(layout["right_margin"])
        except Exception:
            available_width = None
    if not available_width:
        return issues
    for block in structure.get("blocks", []):
        if block.get("block_type") != "table":
            continue
        cell_count = int((block.get("metadata") or {}).get("cell_count") or 0)
        if cell_count >= 6:
            issues.append({"kind": "table_width_risk", "block_key": block.get("block_key"), "description": "table may overflow page width"})
    return issues


def collect_font_consistency_issues(structure_payload: dict[str, Any], expected_body_style: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected_style_name = expected_body_style.get("style_name")
    if not expected_style_name:
        return issues
    for block in structure_payload.get("blocks", []):
        if block.get("block_type") != "paragraph":
            continue
        style_name = block.get("style_name")
        if style_name and style_name != expected_style_name and not block.get("metadata", {}).get("is_heading"):
            issues.append({"kind": "font_consistency", "block_key": block.get("block_key"), "description": "paragraph style differs from template body style"})
            if len(issues) >= 12:
                break
    return issues


def compare_layout_against_template(template_layout_profile: dict[str, Any], formatted_structure: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    template_layouts = template_layout_profile.get("section_layouts", [])
    formatted_layouts = formatted_structure.get("section_layouts", [])
    if len(formatted_layouts) < len(template_layouts):
        issues.append({"kind": "layout_section_count", "description": "formatted document has fewer sections than template"})
    if template_layouts and formatted_layouts:
        template_first = template_layouts[0]
        formatted_first = formatted_layouts[0]
        for key in ("left_margin", "right_margin", "top_margin", "bottom_margin", "text_columns_count"):
            if template_first.get(key) != formatted_first.get(key):
                issues.append({"kind": "layout_mismatch", "field": key, "description": f"formatted {key} does not match template"})
    return issues


def collect_section_break_warnings(template_layout_profile: dict[str, Any], formatted_structure: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    template_count = len(template_layout_profile.get("section_layouts", []))
    formatted_count = len(formatted_structure.get("section_layouts", []))
    if formatted_count > template_count and template_count > 0:
        warnings.append(
            {
                "kind": "unexpected_section_growth",
                "description": "formatted document has more sections than template, which may indicate hard merge boundaries",
                "template_section_count": template_count,
                "formatted_section_count": formatted_count,
            }
        )
    return warnings


def collect_excess_blank_space_warnings(structure_payload: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    blank_run = 0
    max_blank_run = 0
    for block in structure_payload.get("blocks", []):
        if block.get("block_type") != "paragraph":
            blank_run = 0
            continue
        if not block.get("normalized_text"):
            blank_run += 1
            max_blank_run = max(max_blank_run, blank_run)
        else:
            blank_run = 0
    if max_blank_run >= 3:
        warnings.append(
            {
                "kind": "excess_blank_paragraphs",
                "description": "multiple consecutive blank paragraphs may be inflating pagination",
                "max_consecutive_blank_paragraphs": max_blank_run,
            }
        )
    return warnings


def collect_pagination_warnings(section_results, template_layout_profile: dict[str, Any], formatted_structure: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    expected_sections = len(section_results)
    formatted_sections = len(formatted_structure.get("section_layouts", []))
    if formatted_sections > max(expected_sections, 1):
        warnings.append(
            {
                "kind": "pagination_section_expansion",
                "description": "merged output created more layout sections than processed fragments",
                "processed_section_count": expected_sections,
                "formatted_section_count": formatted_sections,
            }
        )
    if template_layout_profile.get("section_layouts") and formatted_sections > len(template_layout_profile.get("section_layouts", [])):
        warnings.append(
            {
                "kind": "pagination_template_mismatch",
                "description": "merged output contains extra layout sections beyond template structure",
            }
        )
    return warnings


def collect_section_style_mismatches(rule_bundle, section_results) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    section_style_mismatches: list[dict[str, Any]] = []
    element_style_mismatches: list[dict[str, Any]] = []
    for result in section_results:
        section_spec = rule_bundle.section_element_style_map.get(normalize_title(result.template_section_title or ""))
        if not section_spec:
            continue
        expected_slots = {key for key, value in (section_spec.get("element_styles") or {}).items() if value}
        applied_slots = set(result.applied_style_slots or [])
        missing_slots = sorted(expected_slots - applied_slots)
        if missing_slots:
            section_style_mismatches.append(
                {
                    "section_title": result.template_section_title,
                    "missing_style_slots": missing_slots,
                }
            )
            for slot in missing_slots:
                element_style_mismatches.append(
                    {
                        "section_title": result.template_section_title,
                        "element_slot": slot,
                        "description": "expected template element style was not applied during section processing",
                    }
                )
    return section_style_mismatches, element_style_mismatches


def collect_content_integrity_warnings(section_results) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    warnings: list[dict[str, Any]] = []
    unmapped_source_blocks: list[str] = []
    all_consumed: list[str] = []
    for result in section_results:
        all_consumed.extend(result.consumed_source_block_keys or [])
        if result.unmapped_source_block_keys:
            warnings.append(
                {
                    "kind": "unmapped_source_blocks",
                    "section_title": result.template_section_title,
                    "unmapped_source_block_keys": list(result.unmapped_source_block_keys),
                }
            )
            unmapped_source_blocks.extend(result.unmapped_source_block_keys)
        if not result.content_integrity_pass:
            warnings.append(
                {
                    "kind": "content_integrity_failed",
                    "section_title": result.template_section_title,
                    "description": "section processing reported unmapped source content",
                }
            )
    seen: set[str] = set()
    duplicate_mapped_blocks: list[str] = []
    for key in all_consumed:
        if key in seen and key not in duplicate_mapped_blocks:
            duplicate_mapped_blocks.append(key)
        seen.add(key)
    if duplicate_mapped_blocks:
        warnings.append(
            {
                "kind": "duplicate_mapped_blocks",
                "duplicate_mapped_blocks": duplicate_mapped_blocks,
            }
        )
    return warnings, sorted(set(unmapped_source_blocks)), duplicate_mapped_blocks


def collect_block_mapping_warnings(section_results) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for result in section_results:
        if result.block_mapping_warnings:
            warnings.extend(result.block_mapping_warnings)
        summary = result.block_mapping_summary or {}
        if summary.get("empty_mapping") and result.consumed_source_block_keys:
            warnings.append(
                {
                    "kind": "block_mapping_summary_conflict",
                    "section_title": result.template_section_title,
                    "description": "block mapping summary reported empty mapping despite consumed source blocks",
                }
            )
    return warnings


def collect_mapping_warnings(section_results) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    append_sections = [result.template_section_title for result in section_results if result.source_mapping_kind == "source_only_append"]
    if append_sections:
        warnings.append(
            {
                "kind": "source_only_appended_sections",
                "sections": append_sections,
                "description": "some source sections could not map to template chapters and were appended to target outline",
            }
        )
    return warnings


def build_repair_candidates(
    *,
    missing_sections: list[str],
    section_style_mismatches: list[dict[str, Any]],
    layout_warnings: list[dict[str, Any]],
    pagination_warnings: list[dict[str, Any]],
    section_break_warnings: list[dict[str, Any]],
    content_integrity_warnings: list[dict[str, Any]],
    block_mapping_warnings: list[dict[str, Any]],
    mapping_warnings: list[dict[str, Any]],
) -> tuple[list[RepairPlan], str]:
    plans: list[RepairPlan] = []
    for title in missing_sections:
        plans.append(
            RepairPlan(
                issue_kind="missing_section",
                owner_agent="FlowSchedulerAgent",
                target_section_title=title,
                repair_action="rebuild_target_outline",
                reason="template-required section is missing in final output",
                retry_scope="target_outline",
            )
        )
    for mismatch in section_style_mismatches:
        plans.append(
            RepairPlan(
                issue_kind="section_style_mismatch",
                owner_agent="SectionProcessorAgent",
                target_section_title=mismatch.get("section_title"),
                repair_action="reapply_section_styles",
                reason="expected chapter element style slots were not applied",
                retry_scope="single_section",
            )
        )
    if content_integrity_warnings or block_mapping_warnings or mapping_warnings:
        plans.append(
            RepairPlan(
                issue_kind="content_mapping_issue",
                owner_agent="FlowSchedulerAgent",
                repair_action="remap_section_blocks",
                reason="source blocks appear unmapped, duplicated, or weakly attached to target sections",
                retry_scope="mapping",
            )
        )
    if layout_warnings or pagination_warnings or section_break_warnings:
        plans.append(
            RepairPlan(
                issue_kind="layout_or_pagination_issue",
                owner_agent="AggregationReviewAgent",
                repair_action="normalize_section_flow",
                reason="merged document layout or pagination drifted from template expectations",
                retry_scope="merge_only",
            )
        )
    if not plans:
        return [], "no_repair_needed"
    if any(plan.retry_scope == "mapping" for plan in plans):
        return plans, "repair_mapping_then_reprocess_sections"
    if any(plan.retry_scope == "single_section" for plan in plans):
        return plans, "repair_sections_then_reaggregate"
    if any(plan.retry_scope == "merge_only" for plan in plans):
        return plans, "rerun_merge_and_layout_normalization"
    return plans, "rerun_target_outline_and_aggregate"


def build_aggregate_report(executor, final_docx_path: str, rule_bundle, section_results) -> dict[str, Any]:
    final_outline = executor.extract_outline(final_docx_path)
    final_structure = executor.extract_structure(final_docx_path, outline=final_outline)
    outline_pass, missing_sections = executor.validate_outline_alignment(final_docx_path, rule_bundle)
    style_warnings = collect_font_consistency_issues(final_structure, rule_bundle.style_profile.get("body_style", {}))
    layout_warnings = compare_layout_against_template(rule_bundle.layout_profile, final_structure)
    layout_warnings.extend(collect_table_width_issues(executor, final_docx_path))
    section_break_warnings = collect_section_break_warnings(rule_bundle.layout_profile, final_structure)
    excess_blank_space_warnings = collect_excess_blank_space_warnings(final_structure)
    pagination_warnings = collect_pagination_warnings(section_results, rule_bundle.layout_profile, final_structure)
    section_style_mismatches, element_style_mismatches = collect_section_style_mismatches(rule_bundle, section_results)
    content_integrity_warnings, unmapped_source_blocks, duplicate_mapped_blocks = collect_content_integrity_warnings(section_results)
    block_mapping_warnings = collect_block_mapping_warnings(section_results)
    mapping_warnings = collect_mapping_warnings(section_results)
    front_signature = front_matter_signature(final_structure)
    front_matter_warnings: list[dict[str, Any]] = []
    if rule_bundle.interpret.get("front_matter", {}).get("required") and not front_signature:
        front_matter_warnings.append({"kind": "front_matter_missing", "description": "front matter is missing after aggregation"})
    repair_candidates, recommended_next_step = build_repair_candidates(
        missing_sections=missing_sections,
        section_style_mismatches=section_style_mismatches,
        layout_warnings=layout_warnings,
        pagination_warnings=pagination_warnings,
        section_break_warnings=section_break_warnings,
        content_integrity_warnings=content_integrity_warnings,
        block_mapping_warnings=block_mapping_warnings,
        mapping_warnings=mapping_warnings,
    )
    return {
        "final_docx_path": final_docx_path,
        "missing_sections": missing_sections,
        "reordered_sections": [],
        "style_warnings": style_warnings,
        "section_style_mismatches": section_style_mismatches,
        "element_style_mismatches": element_style_mismatches,
        "layout_warnings": layout_warnings,
        "pagination_warnings": pagination_warnings,
        "section_break_warnings": section_break_warnings,
        "excess_blank_space_warnings": excess_blank_space_warnings,
        "front_matter_warnings": front_matter_warnings,
        "content_integrity_warnings": content_integrity_warnings,
        "block_mapping_warnings": block_mapping_warnings,
        "unmapped_source_blocks": unmapped_source_blocks,
        "duplicate_mapped_blocks": duplicate_mapped_blocks,
        "mapping_warnings": mapping_warnings,
        "repair_candidates": [item.to_dict() for item in repair_candidates],
        "recommended_next_step": recommended_next_step,
        "outline_pass": outline_pass,
        "processing_stats": {
            "section_count": len(section_results),
            "section_count_before_merge": len(section_results),
            "section_count_after_merge": len(final_structure.get("section_layouts", [])),
            "passed_sections": len([item for item in section_results if item.section_pass]),
            "structure_statistics": summarize_structure(final_structure),
            "outline_titles": summarize_outline_titles([item.to_dict() for item in final_outline]),
        },
    }
