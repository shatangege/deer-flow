from __future__ import annotations

from collections import Counter
from typing import Any

from ..models.contracts import DocumentBlock, RuleBundle, SectionChunk


def determine_pipeline_route(*, source_structure: dict[str, Any], rule_bundle: RuleBundle) -> dict[str, Any]:
    stats = source_structure.get("statistics") or {}
    block_count = int(stats.get("block_count") or 0)
    table_count = int(stats.get("table_count") or 0)
    image_count = int(stats.get("image_count") or 0)
    layout_complexity = len(rule_bundle.layout_profile.get("section_layouts", []))
    reasons: list[str] = []
    if block_count >= 120:
        reasons.append("long_document")
    if table_count >= 6:
        reasons.append("table_dense")
    if image_count >= 8:
        reasons.append("image_dense")
    if layout_complexity >= 6:
        reasons.append("layout_complex")
    if any(reason in reasons for reason in ("table_dense", "image_dense")):
        return {"route": "repair-heavy", "reasons": reasons}
    if reasons:
        return {"route": "staged", "reasons": reasons}
    return {"route": "fast", "reasons": ["fast_path_low_risk"]}


def build_section_chunks(
    *,
    source_docx_path: str,
    source_outline,
    source_structure: dict[str, Any],
    rule_bundle: RuleBundle,
    split_map: dict[str, str],
) -> list[SectionChunk]:
    route = determine_pipeline_route(source_structure=source_structure, rule_bundle=rule_bundle)
    blocks = list(source_structure.get("blocks", []))
    outline_by_title = {item.normalized_title: item for item in source_outline}
    outline_by_order = {item.order: item for item in source_outline}
    blocks_by_title = group_blocks_by_template_affinity(blocks)
    outline_mapping = list((rule_bundle.mapping_rules or {}).get("source_to_target_outline_map") or [])
    chunks: list[SectionChunk] = []
    target_outline = rule_bundle.target_outline or rule_bundle.template_outline
    assigned_keys: set[str] = set()
    for template_item in target_outline:
        target_mapping_record = next(
            (item for item in outline_mapping if item.get("target_normalized_title") == template_item.normalized_title),
            {},
        )
        matched_outline = outline_by_title.get(template_item.normalized_title) or outline_by_order.get(template_item.order)
        matched_blocks = blocks_by_title.get(template_item.normalized_title, [])
        section_role = matched_blocks[0].get("section_role") if matched_blocks else None
        section_style_slots = dict((rule_bundle.section_element_style_map.get(template_item.normalized_title) or {}).get("element_styles") or {})
        risk_flags = list(calculate_risk_flags(matched_blocks, matched_outline is None))
        assigned_source_blocks = [item.get("block_key") for item in matched_blocks if item.get("block_key")]
        block_mapping_summary, block_mapping_warnings = build_block_mapping_diagnostics(
            matched_blocks=matched_blocks,
            source_block_keys=[item.get("block_key") for item in matched_blocks if item.get("block_key")],
            assigned_source_blocks=assigned_source_blocks,
            missing_required_content=matched_outline is None,
            template_title=template_item.title,
        )
        preferred_section_start = None
        template_section_layouts = rule_bundle.layout_profile.get("section_layouts", [])
        if template_item.order - 1 < len(template_section_layouts):
            preferred_section_start = str(template_section_layouts[template_item.order - 1].get("section_start") or "")
        layout_flow_mode = "new_page" if template_item.level == 1 and template_item.order > 1 else "continuous"
        keep_with_next_hints = ["heading_to_first_body"] if template_item.level >= 1 else []
        source_block_indexes = [item.get("block_index") for item in matched_blocks if item.get("block_index") is not None]
        block_range = (
            min(source_block_indexes) if source_block_indexes else None,
            max(source_block_indexes) if source_block_indexes else None,
        )
        chunks.append(
            SectionChunk(
                chunk_id=f"chunk-{template_item.id}",
                template_section_id=template_item.id,
                template_title=template_item.title,
                normalized_template_title=template_item.normalized_title,
                level=template_item.level,
                order=template_item.order,
                source_docx_path=source_docx_path,
                source_section_docx_path=split_map.get(matched_outline.id) if matched_outline else None,
                source_heading_title=matched_outline.title if matched_outline else None,
                source_mapping_kind=target_mapping_record.get("match_kind"),
                target_mapping_record=target_mapping_record,
                source_excerpt=matched_blocks[0].get("text", "") if matched_blocks else "",
                source_paragraph_range=(
                    matched_outline.source_paragraph_index if matched_outline else None,
                    matched_outline.source_paragraph_index if matched_outline else None,
                ),
                source_block_range=block_range,
                source_block_keys=[item.get("block_key") for item in matched_blocks if item.get("block_key")],
                section_role=section_role,
                template_section_index=max(template_item.order - 1, 0),
                layout_flow_mode=layout_flow_mode,
                preferred_section_start=preferred_section_start or None,
                allow_page_break_before=bool(template_item.level == 1 and template_item.order > 1),
                keep_with_next_hints=keep_with_next_hints,
                target_element_style_slots=section_style_slots,
                assigned_source_blocks=assigned_source_blocks,
                style_slot_hints=list(section_style_slots.keys()),
                block_mapping_summary=block_mapping_summary,
                block_mapping_warnings=block_mapping_warnings,
                statistics=build_chunk_statistics(matched_blocks),
                missing_required_content=matched_outline is None,
                risk_flags=risk_flags,
                route=route["route"],
            )
        )
        assigned_keys.update(item.get("block_key") for item in matched_blocks if item.get("block_key"))
    all_source_keys = [item.get("block_key") for item in blocks if item.get("block_key")]
    unmapped_keys = [key for key in all_source_keys if key not in assigned_keys]
    for chunk in chunks:
        chunk.unmapped_source_block_keys = list(unmapped_keys)
    return chunks


def group_blocks_by_template_affinity(blocks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    current_key = ""
    for block in blocks:
        section_path = block.get("section_path") or []
        if section_path:
            current_key = section_path[-1].get("normalized_title", current_key)
        grouped.setdefault(current_key, []).append(block)
    return grouped


def calculate_risk_flags(blocks: list[dict[str, Any]], missing_required_source_section: bool) -> list[str]:
    risk_flags: list[str] = []
    if missing_required_source_section:
        risk_flags.append("missing_required_source_section")
    table_count = len([item for item in blocks if item.get("block_type") == "table"])
    caption_count = len([item for item in blocks if str(item.get("paragraph_role") or "").startswith("caption")])
    image_count = sum(int(item.get("image_count", 0) or 0) for item in blocks)
    roles = Counter(str(item.get("section_role") or "") for item in blocks if item.get("section_role"))
    if table_count >= 3:
        risk_flags.append("table_dense")
    if caption_count >= 2:
        risk_flags.append("caption_dense")
    if image_count >= 4:
        risk_flags.append("layout_complex")
    if roles.get("references"):
        risk_flags.append("reference_dense")
    if any(item.get("section_role") == "front_matter" for item in blocks):
        risk_flags.append("front_matter_mismatch")
    return risk_flags


def build_chunk_statistics(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "block_count": len(blocks),
        "paragraph_count": len([item for item in blocks if item.get("block_type") == "paragraph"]),
        "table_count": len([item for item in blocks if item.get("block_type") == "table"]),
        "image_count": sum(int(item.get("image_count", 0) or 0) for item in blocks),
    }


def build_block_mapping_diagnostics(
    *,
    matched_blocks: list[dict[str, Any]],
    source_block_keys: list[str],
    assigned_source_blocks: list[str],
    missing_required_content: bool,
    template_title: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_set = set(source_block_keys)
    assigned_counter = Counter(assigned_source_blocks)
    duplicate_assigned_blocks = sorted([key for key, count in assigned_counter.items() if key and count > 1])
    foreign_assigned_blocks = sorted([key for key in assigned_source_blocks if key and key not in source_set])
    block_type_counts = Counter(str(item.get("block_type") or "") for item in matched_blocks if item.get("block_type"))
    paragraph_role_counts = Counter(str(item.get("paragraph_role") or "") for item in matched_blocks if item.get("paragraph_role"))
    section_role_counts = Counter(str(item.get("section_role") or "") for item in matched_blocks if item.get("section_role"))
    summary = {
        "source_block_count": len(source_block_keys),
        "assigned_block_count": len(assigned_source_blocks),
        "unique_assigned_block_count": len(set(assigned_source_blocks)),
        "duplicate_assigned_blocks": duplicate_assigned_blocks,
        "foreign_assigned_blocks": foreign_assigned_blocks,
        "empty_mapping": bool(not assigned_source_blocks),
        "block_type_counts": dict(block_type_counts),
        "paragraph_role_counts": dict(paragraph_role_counts),
        "section_role_counts": dict(section_role_counts),
        "caption_block_count": sum(count for role, count in paragraph_role_counts.items() if role.startswith("caption")),
    }
    warnings: list[dict[str, Any]] = []
    if duplicate_assigned_blocks:
        warnings.append(
            {
                "kind": "duplicate_assigned_blocks_within_chunk",
                "section_title": template_title,
                "duplicate_assigned_blocks": duplicate_assigned_blocks,
            }
        )
    if foreign_assigned_blocks:
        warnings.append(
            {
                "kind": "foreign_assigned_blocks",
                "section_title": template_title,
                "foreign_assigned_blocks": foreign_assigned_blocks,
            }
        )
    if not assigned_source_blocks and not missing_required_content:
        warnings.append(
            {
                "kind": "empty_chunk_mapping",
                "section_title": template_title,
                "description": "section chunk did not retain any assigned source blocks",
            }
        )
    return summary, warnings
