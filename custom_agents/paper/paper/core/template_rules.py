from __future__ import annotations

from typing import Any

from ..models.contracts import RuleBundle


def build_rule_bundle(template_docx_path: str, template_outline, template_structure: dict[str, Any], style_profile: dict[str, Any]) -> RuleBundle:
    role_slots = infer_role_slots(template_structure)
    interpret = build_template_interpret(template_outline, template_structure)
    section_element_style_map = build_section_element_style_map(template_outline, style_profile)
    return RuleBundle(
        template_docx_path=template_docx_path,
        template_outline=template_outline,
        target_outline=list(template_outline),
        heading_levels={item.normalized_title: item.level for item in template_outline},
        style_profile=style_profile,
        required_sections=[item.normalized_title for item in template_outline],
        template_structure_summary=template_structure.get("statistics", {}),
        layout_profile={
            "page_setup": template_structure.get("page_setup", []),
            "section_layouts": template_structure.get("section_layouts", []),
        },
        section_styles=build_section_styles(template_outline, style_profile),
        section_element_style_map=section_element_style_map,
        role_slots=role_slots,
        interpret=interpret,
        mapping_rules={
            "match_strategy": "normalized_title_then_order",
            "strict_template_alignment": True,
            "style_resolution_order": [
                "section_element_style_map",
                "role_slots",
                "style_profile_defaults",
            ],
        },
    )


def infer_role_slots(template_structure: dict[str, Any]) -> dict[str, Any]:
    role_slots: dict[str, Any] = {}
    for block in template_structure.get("blocks", []):
        section_role = block.get("section_role")
        paragraph_role = block.get("paragraph_role")
        if section_role and section_role not in role_slots:
            role_slots[section_role] = {
                "style_name": block.get("style_name"),
                "block_type": block.get("block_type"),
                "paragraph_index": block.get("paragraph_index"),
                "table_index": block.get("table_index"),
                "section_path": block.get("section_path", []),
            }
        paragraph_key = f"paragraph:{paragraph_role}" if paragraph_role else None
        if paragraph_key and paragraph_key not in role_slots:
            role_slots[paragraph_key] = {
                "style_name": block.get("style_name"),
                "block_type": block.get("block_type"),
                "paragraph_index": block.get("paragraph_index"),
                "section_path": block.get("section_path", []),
            }
    return role_slots


def build_template_interpret(template_outline, template_structure: dict[str, Any]) -> dict[str, Any]:
    front_matter_titles = [item.title for item in template_outline if item.level == 1][:3]
    outline_titles = [item.title for item in template_outline]
    references_required = any(
        ("参考文献" in title) or ("reference" in title.lower()) or ("bibliography" in title.lower())
        for title in outline_titles
    )
    return {
        "front_matter": {
            "expected_titles": front_matter_titles,
            "required": bool(front_matter_titles),
            "profiles": ((template_structure.get("style_profile") or {}).get("front_matter_profiles") or {}),
        },
        "references": {
            "hanging_indent": 21.0,
            "required": references_required,
            "profile": (template_structure.get("reference_profile") or {}),
        },
        "section_count": len(template_outline),
        "layout_complexity": len(template_structure.get("section_layouts", [])),
    }


def build_section_styles(template_outline, style_profile: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    heading_styles = style_profile.get("heading_profiles") or style_profile.get("heading_styles", {})
    for item in template_outline:
        result.append(
            {
                "normalized_title": item.normalized_title,
                "title": item.title,
                "level": item.level,
                "order": item.order,
                "profile": heading_styles.get(str(item.level), {}),
            }
        )
    return result


def _detect_section_role(item) -> str:
    lowered = item.title.lower()
    if "参考文献" in item.title or lowered in {"references", "bibliography"}:
        return "references"
    if "appendix" in lowered or "附录" in item.title:
        return "appendix"
    if item.order <= 3 and (
        any(token in lowered for token in ("abstract", "keywords"))
        or any(token in item.title for token in ("摘要", "关键词"))
    ):
        return "front_matter"
    return "body"


def build_section_element_style_map(template_outline, style_profile: dict[str, Any]) -> dict[str, Any]:
    heading_styles = style_profile.get("heading_profiles") or style_profile.get("heading_styles", {})
    body_profile = (style_profile.get("body_profiles") or {}).get("default") or style_profile.get("body_style", {})
    caption_profiles = style_profile.get("caption_profiles") or {}
    reference_profile = style_profile.get("reference_profile") or {}
    front_matter_profiles = style_profile.get("front_matter_profiles") or {}
    table_profiles = style_profile.get("table_profiles") or {}
    default_table_profile = next(iter(table_profiles.values()), {})
    section_layout_profiles = style_profile.get("section_layout_profiles") or []
    ordered_front_profiles = front_matter_profiles.get("ordered") or []
    result: dict[str, Any] = {}
    for item in template_outline:
        section_role = _detect_section_role(item)
        body_row_cells = ((default_table_profile or {}).get("body_row_profile") or {}).get("cells") or []
        table_cell_profile = body_row_cells[0] if body_row_cells else {}
        element_styles = {
            "heading": heading_styles.get(str(item.level), {}),
            "subheading_level_2": heading_styles.get("2", heading_styles.get(str(item.level), {})),
            "subheading_level_3": heading_styles.get("3", heading_styles.get(str(item.level), {})),
            "body_first_paragraph": body_profile,
            "body_paragraph": body_profile,
            "figure_caption": caption_profiles.get("caption_figure", caption_profiles.get("caption", {})),
            "table_caption": caption_profiles.get("caption_table", caption_profiles.get("caption", {})),
            "reference_item": reference_profile or body_profile,
            "table": default_table_profile,
            "table_header_row": (default_table_profile or {}).get("header_row_profile", {}),
            "table_body_row": (default_table_profile or {}).get("body_row_profile", {}),
            "table_cell": table_cell_profile,
            "section_layout": section_layout_profiles[min(item.order - 1, len(section_layout_profiles) - 1)] if section_layout_profiles else {},
        }
        if section_role == "front_matter":
            element_styles.update(
                {
                    "front_matter_title": ordered_front_profiles[0] if len(ordered_front_profiles) > 0 else front_matter_profiles.get("default", {}),
                    "front_matter_author_block": ordered_front_profiles[1] if len(ordered_front_profiles) > 1 else front_matter_profiles.get("default", {}),
                    "front_matter_abstract": ordered_front_profiles[1] if len(ordered_front_profiles) > 1 else front_matter_profiles.get("default", {}),
                    "front_matter_keywords": ordered_front_profiles[2] if len(ordered_front_profiles) > 2 else front_matter_profiles.get("default", {}),
                }
            )
        result[item.normalized_title] = {
            "section_id": item.id,
            "normalized_title": item.normalized_title,
            "title": item.title,
            "order": item.order,
            "level": item.level,
            "section_role": section_role,
            "element_styles": element_styles,
        }
    return result


def pre_format_check(section_blocks: list[dict[str, Any]], rule_bundle: RuleBundle) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if not section_blocks:
        issues.append({"kind": "missing_content", "description": "section has no source blocks"})
    table_count = len([item for item in section_blocks if item.get("block_type") == "table"])
    if table_count >= 3:
        issues.append({"kind": "table_density", "description": "section contains many tables"})
    return {
        "risk_level": "high" if issues else "low",
        "issues": issues,
        "style_overrides": {},
        "required_sections": rule_bundle.required_sections,
    }
