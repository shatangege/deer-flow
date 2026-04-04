from __future__ import annotations

from .text import replace_paragraph_text


def _front_profile_for_index(front_matter_profiles, index: int):
    if not isinstance(front_matter_profiles, dict):
        return None
    ordered = front_matter_profiles.get("ordered", [])
    if 0 <= index < len(ordered):
        return ordered[index]
    return front_matter_profiles.get("default")


def render_front_matter_from_template(
    executor,
    result_document,
    target_section,
    template_document,
    template_structure,
    source_front_items,
    template_paragraph_nodes,
    front_matter_profiles=None,
):
    front_items = source_front_items or []
    blocks = [block for block in (template_structure.get("blocks") or []) if not block.get("section_path")]
    for index, block in enumerate(blocks[: len(front_items)]):
        paragraph_node = template_paragraph_nodes.get(block.get("paragraph_index")) if isinstance(template_paragraph_nodes, dict) else None
        if paragraph_node is None:
            continue
        imported_node = result_document.ImportNode(paragraph_node, True, executor.ImportFormatMode.UseDestinationStyles)
        target_section.Body.AppendChild(imported_node)
        replacement_text = front_items[min(len(front_items) - 1, index)].get("text", "")
        profile = _front_profile_for_index(front_matter_profiles, index)
        replace_paragraph_text(executor, imported_node, replacement_text, result_document, profile=profile)
