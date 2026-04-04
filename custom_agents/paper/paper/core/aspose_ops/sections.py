from __future__ import annotations


def copy_template_styles(executor, result_document, template_path):
    try:
        result_document.CopyStylesFromTemplate(template_path)
    except Exception:
        pass


def copy_page_setup(executor, target_page_setup, template_page_setup):
    for attr_name in (
        "PageWidth",
        "PageHeight",
        "LeftMargin",
        "RightMargin",
        "TopMargin",
        "BottomMargin",
        "HeaderDistance",
        "FooterDistance",
    ):
        try:
            setattr(target_page_setup, attr_name, getattr(template_page_setup, attr_name))
        except Exception:
            pass


def sync_section_layout_from_template(executor, result_document, target_section, template_section):
    if not target_section or not template_section:
        return
    try:
        target_section.HeadersFooters.Clear()
    except Exception:
        pass
    for idx in range(template_section.HeadersFooters.Count):
        try:
            imported = result_document.ImportNode(
                template_section.HeadersFooters[idx],
                True,
                executor.ImportFormatMode.KeepSourceFormatting,
            )
            target_section.HeadersFooters.Add(imported)
        except Exception:
            continue
    copy_page_setup(executor, target_section.PageSetup, template_section.PageSetup)


def force_section_start_continuous(_executor, section):
    try:
        section.PageSetup.SectionStart = 0
    except Exception:
        pass


def clear_page_break_before(_executor, paragraph):
    try:
        paragraph.ParagraphFormat.PageBreakBefore = False
    except Exception:
        pass


def normalize_document_flow(executor, document):
    for section_idx in range(document.Sections.Count):
        section = document.Sections[section_idx]
        body = section.Body
        nodes = body.GetChildNodes(executor.NodeType.Any, False)
        for node_idx in range(nodes.Count):
            node = nodes[node_idx]
            if node.NodeType != executor.NodeType.Paragraph:
                continue
            clear_page_break_before(executor, node)
            try:
                text = executor._node_text(node)
            except Exception:
                text = ""
            try:
                if not text and node_idx > 0:
                    prev_node = nodes[node_idx - 1]
                    if prev_node.NodeType == executor.NodeType.Paragraph and not executor._node_text(prev_node):
                        node.Remove()
                        continue
            except Exception:
                pass
        ensure_section_has_terminal_paragraph(executor, section, document)


def normalize_section_starts_for_flow(executor, document):
    for idx in range(1, document.Sections.Count):
        force_section_start_continuous(executor, document.Sections[idx])
    normalize_document_flow(executor, document)


def resync_all_section_layouts_from_template(executor, result_document, template_document):
    if template_document.Sections.Count == 0 or result_document.Sections.Count == 0:
        return
    for idx in range(result_document.Sections.Count):
        template_section = template_document.Sections[min(idx, template_document.Sections.Count - 1)]
        target_section = result_document.Sections[idx]
        sync_section_layout_from_template(executor, result_document, target_section, template_section)


def clear_all_section_bodies(_executor, document):
    for idx in range(document.Sections.Count):
        document.Sections[idx].Body.RemoveAllChildren()


def clone_template_section(executor, result_document, template_document, template_index):
    template_index = min(template_index, template_document.Sections.Count - 1)
    imported_section = result_document.ImportNode(
        template_document.Sections[template_index],
        True,
        executor.ImportFormatMode.KeepSourceFormatting,
    )
    imported_section.Body.RemoveAllChildren()
    result_document.Sections.Add(imported_section)
    return result_document.Sections[result_document.Sections.Count - 1]


def get_target_section(executor, result_document, template_document, target_index):
    while target_index >= result_document.Sections.Count:
        clone_template_section(executor, result_document, template_document, result_document.Sections.Count - 1)
    return result_document.Sections[target_index]


def ensure_section_has_terminal_paragraph(executor, section, document):
    body = section.Body
    nodes = body.GetChildNodes(executor.NodeType.Any, False)
    if nodes.Count == 0:
        body.AppendParagraph("")
        return
    last_node = body.LastChild
    if last_node.NodeType != executor.NodeType.Paragraph:
        body.AppendParagraph("")


def remove_unused_sections(_executor, document, section_usage):
    for idx in range(document.Sections.Count - 1, -1, -1):
        if idx < len(section_usage) and section_usage[idx]:
            continue
        if document.Sections.Count <= 1:
            break
        document.Sections.RemoveAt(idx)
