from __future__ import annotations


def apply_cell_profile(executor, cell, cell_profile, document):
    if cell_profile.get("vertical_alignment") is not None:
        executor.set_enum_property(cell.CellFormat, "VerticalAlignment", cell_profile.get("vertical_alignment"))
    for attr_name, key in (
        ("LeftPadding", "left_padding"),
        ("RightPadding", "right_padding"),
        ("TopPadding", "top_padding"),
        ("BottomPadding", "bottom_padding"),
        ("Width", "width"),
    ):
        value = cell_profile.get(key)
        if value is not None:
            try:
                setattr(cell.CellFormat, attr_name, float(value))
            except Exception:
                pass
    if (cell_profile.get("paragraph_format") or cell_profile.get("font")) and cell.FirstParagraph is not None:
        for p_idx in range(cell.Paragraphs.Count):
            paragraph_profile = {
                "style_name": None,
                "paragraph_format": cell_profile.get("paragraph_format"),
                "font": cell_profile.get("font"),
            }
            executor.apply_paragraph_profile(cell.Paragraphs[p_idx], paragraph_profile, document)


def apply_table_row_profile(executor, row, row_profile, document, force_heading_format=None):
    if row is None or not row_profile:
        return
    if force_heading_format is not None:
        try:
            row.RowFormat.HeadingFormat = bool(force_heading_format)
        except Exception:
            pass
    elif row_profile.get("heading_format") is not None:
        try:
            row.RowFormat.HeadingFormat = bool(row_profile["heading_format"])
        except Exception:
            pass
    for attr_name, key in (
        ("Height", "height"),
        ("AllowBreakAcrossPages", "allow_break_across_pages"),
    ):
        value = row_profile.get(key)
        if value is not None:
            try:
                if attr_name == "Height":
                    row.RowFormat.Height = float(value)
                else:
                    row.RowFormat.AllowBreakAcrossPages = bool(value)
            except Exception:
                pass
    for cell_idx, cell_profile in enumerate(row_profile.get("cells", [])):
        if cell_idx >= row.Cells.Count:
            break
        apply_cell_profile(executor, row.Cells[cell_idx], cell_profile, document)


def apply_table_borders(executor, table, borders_profile):
    if not borders_profile:
        return
    try:
        table_borders = getattr(table, "Borders", None)
        if table_borders is None:
            return
        for name, border_data in borders_profile.items():
            try:
                border = table_borders[name.capitalize()]
                executor.set_enum_property(border, "LineStyle", border_data.get("line_style"))
                if border_data.get("line_width") is not None:
                    border.LineWidth = float(border_data["line_width"])
            except Exception:
                pass
    except Exception:
        pass


def measure_table_width(_executor, table):
    try:
        max_width = 0.0
        for row_idx in range(table.Rows.Count):
            row = table.Rows[row_idx]
            row_width = 0.0
            for cell_idx in range(row.Cells.Count):
                row_width += float(getattr(row.Cells[cell_idx].CellFormat, "Width", 0.0) or 0.0)
            max_width = max(max_width, row_width)
        return max_width
    except Exception:
        return 0.0


def clear_table_cell_width_constraints(executor, table):
    try:
        for row_idx in range(table.Rows.Count):
            row = table.Rows[row_idx]
            for cell_idx in range(row.Cells.Count):
                cell = row.Cells[cell_idx]
                try:
                    cell.CellFormat.PreferredWidth = executor.PreferredWidth.FromPercent(0)
                except Exception:
                    pass
    except Exception:
        pass


def scale_table_cells_to_width(_executor, table, target_width):
    current_width = measure_table_width(_executor, table)
    if current_width <= 0:
        return
    scale = target_width / current_width
    for row_idx in range(table.Rows.Count):
        row = table.Rows[row_idx]
        for cell_idx in range(row.Cells.Count):
            cell = row.Cells[cell_idx]
            try:
                old_w = float(getattr(cell.CellFormat, "Width", 0.0) or 0.0)
            except Exception:
                old_w = 0.0
            if old_w > 0:
                try:
                    cell.CellFormat.Width = old_w * scale
                except Exception:
                    pass


def apply_table_column_widths(executor, table, column_widths, target_width=None):
    if not column_widths or table.Rows.Count == 0:
        return False
    try:
        widths = [float(item or 0.0) for item in column_widths]
    except Exception:
        return False
    first_row = table.Rows[0]
    if first_row.Cells.Count != len(widths):
        return False
    widths_sum = sum(widths)
    if target_width and widths_sum > 0:
        scale = float(target_width) / float(widths_sum)
        widths = [width * scale for width in widths]
    for row_idx in range(table.Rows.Count):
        row = table.Rows[row_idx]
        if row.Cells.Count != len(widths):
            return False
        for cell_idx, width in enumerate(widths):
            cell = row.Cells[cell_idx]
            try:
                cell.CellFormat.Width = float(width)
            except Exception:
                pass
    return True


def force_table_fill_width(executor, table, target_width):
    if table.Rows.Count == 0:
        return
    col_count = table.Rows[0].Cells.Count
    if col_count <= 0:
        return
    widths = [float(target_width) / float(col_count)] * col_count
    apply_table_column_widths(executor, table, widths, target_width)


def fit_table_within_section_width(executor, table, section, preferred_width=None, preferred_width_type=None, column_widths=None):
    available_width = executor.section_content_width(section)
    if not available_width:
        return
    target_width = available_width
    clear_table_cell_width_constraints(executor, table)
    if apply_table_column_widths(executor, table, column_widths, target_width):
        return
    current_width = measure_table_width(executor, table)
    if current_width > available_width + 3:
        scale_table_cells_to_width(executor, table, available_width)
    elif current_width <= 0 or current_width < target_width * 0.8:
        force_table_fill_width(executor, table, target_width)


def ensure_table_spacing(_executor, table, table_profile):
    if not table:
        return
    try:
        prev_node = table.PreviousSibling
        next_node = table.NextSibling
        if prev_node and hasattr(prev_node, "ParagraphFormat"):
            prev_node.ParagraphFormat.SpaceAfter = max(float(prev_node.ParagraphFormat.SpaceAfter or 0), 6.0)
        if next_node and hasattr(next_node, "ParagraphFormat"):
            next_node.ParagraphFormat.SpaceBefore = max(float(next_node.ParagraphFormat.SpaceBefore or 0), 6.0)
    except Exception:
        pass


def apply_table_profile(executor, table, profile, document):
    if not profile:
        return
    style_name = profile.get("style_name")
    if style_name:
        try:
            table.StyleName = style_name
        except Exception:
            pass
    if profile.get("alignment") is not None:
        executor.set_enum_property(table, "Alignment", profile.get("alignment"))
    if profile.get("allow_auto_fit") is not None:
        try:
            table.AllowAutoFit = bool(profile["allow_auto_fit"])
        except Exception:
            pass
    apply_table_borders(executor, table, profile.get("borders"))
    apply_table_column_widths(executor, table, profile.get("column_widths"))
    header_row_profile = profile.get("header_row_profile")
    if header_row_profile and table.Rows.Count > 0:
        apply_table_row_profile(executor, table.Rows[0], header_row_profile, document, force_heading_format=True)
    body_row_profile = profile.get("body_row_profile")
    if body_row_profile and table.Rows.Count > 1:
        for row_idx in range(1, table.Rows.Count):
            apply_table_row_profile(executor, table.Rows[row_idx], body_row_profile, document)
