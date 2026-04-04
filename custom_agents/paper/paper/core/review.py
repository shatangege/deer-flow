from __future__ import annotations

from typing import Any

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
    front_signature = front_matter_signature(final_structure)
    front_matter_warnings: list[dict[str, Any]] = []
    if rule_bundle.interpret.get("front_matter", {}).get("required") and not front_signature:
        front_matter_warnings.append({"kind": "front_matter_missing", "description": "front matter is missing after aggregation"})
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
