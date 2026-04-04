from __future__ import annotations

import re
from typing import Any

from ..models.contracts import DocumentBlock, OutlineItem
from .parsing_rules import classify_paragraph_role, classify_section_role
from .utils import normalize_title


_HEADING_NUMBER_RE = re.compile(r"^\s*((\d+(\.\d+)*)|([IVXLC]+)|([A-Z]))[\.\)\-、]+")


def classify_heading_role(text: str, normalized_text: str | None = None) -> str:
    del normalized_text
    return classify_section_role(text, default_role="body")


def iter_body_blocks(executor, document):
    for section_idx in range(document.Sections.Count):
        section = document.Sections[section_idx]
        body = section.Body
        nodes = body.GetChildNodes(executor.NodeType.Any, False)
        for node_idx in range(nodes.Count):
            yield section_idx, nodes[node_idx]


def _heading_pattern(text: str) -> str | None:
    match = _HEADING_NUMBER_RE.match(text or "")
    if not match:
        return None
    return match.group(1)


def _is_probable_toc(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return lowered in {"contents", "table of contents", "目录"}


def _is_probable_reference_heading(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return "参考文献" in (text or "") or lowered in {"references", "bibliography"}


def _is_probable_appendix_heading(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return lowered.startswith("appendix") or "附录" in (text or "")


def _is_probable_front_matter(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return lowered in {"abstract", "keywords", "acknowledgements", "acknowledgments"} or (text or "").strip() in {"摘要", "关键词", "致谢"}


def _candidate_from_outline_item(item: OutlineItem, section_role: str | None = None, paragraph_role: str | None = None) -> dict[str, Any]:
    title = item.title
    return {
        "id": item.id,
        "title": title,
        "normalized_title": item.normalized_title,
        "candidate_level": item.level,
        "level": item.level,
        "order": item.order,
        "source_paragraph_index": item.source_paragraph_index,
        "style_name": item.style_name,
        "page_index": item.page_index,
        "path": list(item.path),
        "numbering_pattern": _heading_pattern(title),
        "section_role": section_role or classify_heading_role(title, item.normalized_title),
        "paragraph_role": paragraph_role,
        "is_probable_front_matter": _is_probable_front_matter(title),
        "is_probable_caption": bool(paragraph_role and str(paragraph_role).startswith("caption")),
        "is_probable_toc": _is_probable_toc(title),
        "is_probable_reference_heading": _is_probable_reference_heading(title),
        "is_probable_appendix_heading": _is_probable_appendix_heading(title),
        "confidence": 0.9 if item.style_name else 0.7,
    }


def extract_outline_candidates(executor, docx_path: str) -> list[dict[str, Any]]:
    outline = extract_outline(executor, docx_path)
    structure = extract_structure(executor, docx_path, outline)
    blocks_by_paragraph = {
        block["paragraph_index"]: block
        for block in structure.get("blocks", [])
        if block.get("block_type") == "paragraph" and block.get("paragraph_index") is not None
    }
    return [
        _candidate_from_outline_item(
            item,
            section_role=(blocks_by_paragraph.get(item.source_paragraph_index) or {}).get("section_role"),
            paragraph_role=(blocks_by_paragraph.get(item.source_paragraph_index) or {}).get("paragraph_role"),
        )
        for item in outline
    ]


def extract_outline(executor, docx_path: str) -> list[OutlineItem]:
    document = executor.load_document(docx_path)
    collector = executor.LayoutCollector(document)
    document.UpdatePageLayout()
    outline: list[OutlineItem] = []
    heading_stack: list[OutlineItem] = []
    paragraph_index = 0

    for _, node in iter_body_blocks(executor, document):
        if node.NodeType != executor.NodeType.Paragraph:
            continue
        text = executor._node_text(node)
        if not text:
            paragraph_index += 1
            continue
        level = executor._detect_heading_level(node, text)
        if not level:
            paragraph_index += 1
            continue
        heading_stack = [item for item in heading_stack if item.level < level]
        item = OutlineItem(
            id=f"h{len(outline) + 1}",
            title=text,
            normalized_title=normalize_title(text),
            level=level,
            order=len(outline) + 1,
            source_paragraph_index=paragraph_index,
            style_name=executor._safe_style_name(node),
            page_index=executor._safe_int(collector.GetStartPageIndex(node)),
            path=[entry.title for entry in heading_stack] + [text],
        )
        outline.append(item)
        heading_stack.append(item)
        paragraph_index += 1
    return outline


def extract_paragraph_block(
    executor,
    paragraph,
    section_idx: int,
    paragraph_index: int,
    block_index: int,
    heading_info: OutlineItem | None,
    section_path: list[dict[str, Any]],
    page_index: int | None,
) -> DocumentBlock:
    text = executor._node_text(paragraph)
    normalized = normalize_title(text)
    return DocumentBlock(
        block_key=f"p:{paragraph_index}",
        block_type="paragraph",
        block_index=block_index,
        paragraph_index=paragraph_index,
        section_index=section_idx,
        text=text,
        normalized_text=normalized,
        style_name=executor._safe_style_name(paragraph),
        section_path=section_path,
        section_role=classify_heading_role(text, normalized) if heading_info else infer_section_role(section_path),
        paragraph_role=infer_paragraph_role(text),
        page_index=page_index,
        image_count=count_child_nodes(executor, paragraph, "Shape"),
        equation_count=0,
        metadata={"is_heading": heading_info is not None},
    )


def extract_table_block(
    executor,
    table,
    section_idx: int,
    table_index: int,
    block_index: int,
    section_path: list[dict[str, Any]],
    page_index: int | None,
) -> DocumentBlock:
    return DocumentBlock(
        block_key=f"t:{table_index}",
        block_type="table",
        block_index=block_index,
        table_index=table_index,
        section_index=section_idx,
        text="",
        normalized_text="",
        style_name=None,
        section_path=section_path,
        section_role=infer_section_role(section_path),
        paragraph_role=None,
        page_index=page_index,
        metadata={"row_count": executor._safe_int(table.Rows.Count), "cell_count": table.Rows[0].Cells.Count if table.Rows.Count else 0},
    )


def annotate_block_contexts(blocks: list[DocumentBlock]) -> list[DocumentBlock]:
    for block in blocks:
        block.metadata["has_section_path"] = bool(block.section_path)
        block.metadata["is_front_matter"] = not block.section_path
    return blocks


def extract_style_catalog(executor, document) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    try:
        for style in document.Styles:
            name = executor._clean_text(getattr(style, "Name", ""))
            if not name:
                continue
            result.append(
                {
                    "style_name": name,
                    "type": str(getattr(style, "Type", "")),
                    "font_name": str(getattr(style.Font, "Name", "")),
                    "font_size": float(getattr(style.Font, "Size", 0.0) or 0.0),
                    "bold": bool(getattr(style.Font, "Bold", False)),
                }
            )
    except Exception:
        pass
    return result


def extract_page_setup(_executor, section) -> dict[str, Any]:
    try:
        page_setup = section.PageSetup
        return {
            "page_width": float(page_setup.PageWidth),
            "page_height": float(page_setup.PageHeight),
            "left_margin": float(page_setup.LeftMargin),
            "right_margin": float(page_setup.RightMargin),
            "top_margin": float(page_setup.TopMargin),
            "bottom_margin": float(page_setup.BottomMargin),
            "text_columns_count": int(page_setup.TextColumns.Count),
        }
    except Exception:
        return {}


def extract_section_layout_summary(executor, section, section_index: int) -> dict[str, Any]:
    setup = extract_page_setup(executor, section)
    setup["section_index"] = section_index
    return setup


def extract_structure(executor, docx_path: str, outline: list[OutlineItem]) -> dict[str, Any]:
    document = executor.load_document(docx_path)
    collector = executor.LayoutCollector(document)
    document.UpdatePageLayout()
    outline_by_paragraph = {item.source_paragraph_index: item for item in outline if item.source_paragraph_index is not None}
    blocks: list[DocumentBlock] = []
    paragraph_index = 0
    table_index = 0
    heading_stack: list[OutlineItem] = []
    for section_idx, node in iter_body_blocks(executor, document):
        page_index = executor._safe_int(collector.GetStartPageIndex(node))
        if node.NodeType == executor.NodeType.Paragraph:
            heading_item = outline_by_paragraph.get(paragraph_index)
            if heading_item:
                heading_stack = [item for item in heading_stack if item.level < heading_item.level]
                heading_stack.append(heading_item)
            section_path = [
                {
                    "id": item.id,
                    "level": item.level,
                    "order": item.order,
                    "title": item.title,
                    "normalized_title": item.normalized_title,
                }
                for item in heading_stack
            ]
            blocks.append(
                extract_paragraph_block(
                    executor,
                    node,
                    section_idx,
                    paragraph_index,
                    len(blocks),
                    heading_item,
                    section_path,
                    page_index,
                )
            )
            paragraph_index += 1
        elif node.NodeType == executor.NodeType.Table:
            section_path = [
                {
                    "id": item.id,
                    "level": item.level,
                    "order": item.order,
                    "title": item.title,
                    "normalized_title": item.normalized_title,
                }
                for item in heading_stack
            ]
            blocks.append(extract_table_block(executor, node, section_idx, table_index, len(blocks), section_path, page_index))
            table_index += 1
    blocks = annotate_block_contexts(blocks)
    return {
        "generated_at": executor._now(),
        "source_docx": docx_path,
        "page_setup": [extract_page_setup(executor, document.Sections[idx]) for idx in range(document.Sections.Count)],
        "section_layouts": [extract_section_layout_summary(executor, document.Sections[idx], idx) for idx in range(document.Sections.Count)],
        "document_styles": extract_style_catalog(executor, document),
        "statistics": build_structure_statistics(blocks),
        "blocks": [item.to_dict() for item in blocks],
    }


def build_structure_statistics(blocks: list[DocumentBlock]) -> dict[str, Any]:
    return {
        "block_count": len(blocks),
        "paragraph_count": len([item for item in blocks if item.block_type == "paragraph"]),
        "table_count": len([item for item in blocks if item.block_type == "table"]),
        "image_count": sum(item.image_count for item in blocks if item.block_type == "paragraph"),
        "equation_count": sum(item.equation_count for item in blocks if item.block_type == "paragraph"),
    }


def infer_paragraph_role(text: str) -> str | None:
    return classify_paragraph_role(text)


def infer_section_role(section_path: list[dict[str, Any]]) -> str | None:
    if not section_path:
        return "front_matter"
    return classify_section_role(section_path[-1].get("title", ""), default_role="body")


def count_child_nodes(executor, paragraph, node_type_name: str) -> int:
    node_type = getattr(executor.NodeType, node_type_name, None)
    if node_type is None:
        return 0
    try:
        return int(paragraph.GetChildNodes(node_type, True).Count)
    except Exception:
        return 0
