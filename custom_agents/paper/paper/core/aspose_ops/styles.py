from __future__ import annotations


def set_enum_property(executor, obj, attr_name, payload):
    if not payload:
        return
    raw_value = payload.get("value") if isinstance(payload, dict) else payload
    if raw_value is None:
        return
    try:
        property_info = obj.GetType().GetProperty(attr_name)
        if property_info is not None:
            enum_value = executor.SystemModule.Enum.ToObject(property_info.PropertyType, int(raw_value))
            property_info.SetValue(obj, enum_value, None)
            return
        setattr(obj, attr_name, raw_value)
    except Exception:
        pass


def set_color_property(executor, obj, attr_name, color_payload):
    if not color_payload:
        return
    try:
        color = executor.SystemDrawingModule.Color.FromArgb(
            int(color_payload.get("a", 255)),
            int(color_payload.get("r", 0)),
            int(color_payload.get("g", 0)),
            int(color_payload.get("b", 0)),
        )
        setattr(obj, attr_name, color)
    except Exception:
        pass


def apply_run_font(executor, run, font_payload, preserve_emphasis=False):
    if not font_payload:
        return
    try:
        run.Font.ClearFormatting()
    except Exception:
        pass
    if font_payload.get("name"):
        run.Font.Name = font_payload["name"]
    if font_payload.get("size") is not None:
        run.Font.Size = float(font_payload["size"])
    if font_payload.get("name_far_east"):
        run.Font.NameFarEast = font_payload["name_far_east"]
    set_color_property(executor, run.Font, "Color", font_payload.get("color"))
    if font_payload.get("underline") is not None:
        set_enum_property(executor, run.Font, "Underline", font_payload.get("underline"))
    if font_payload.get("superscript") is not None:
        try:
            run.Font.Superscript = bool(font_payload["superscript"])
        except Exception:
            pass
    if font_payload.get("subscript") is not None:
        try:
            run.Font.Subscript = bool(font_payload["subscript"])
        except Exception:
            pass
    if not preserve_emphasis:
        if font_payload.get("bold") is not None:
            run.Font.Bold = bool(font_payload["bold"])
        if font_payload.get("italic") is not None:
            run.Font.Italic = bool(font_payload["italic"])


def apply_paragraph_profile(executor, paragraph, profile, document, is_heading=False, preserve_existing_run_fonts=False):
    if not profile:
        return
    try:
        paragraph.ParagraphFormat.ClearFormatting()
    except Exception:
        pass
    style_name = profile.get("style_name")
    if style_name:
        try:
            paragraph.ParagraphFormat.StyleName = style_name
        except Exception:
            pass

    paragraph_format = profile.get("paragraph_format") or profile
    for attr_name, key in (
        ("LeftIndent", "left_indent"),
        ("RightIndent", "right_indent"),
        ("FirstLineIndent", "first_line_indent"),
        ("SpaceBefore", "space_before"),
        ("SpaceAfter", "space_after"),
        ("LineSpacing", "line_spacing"),
        ("LineSpacingRule", "line_spacing_rule"),
    ):
        value = paragraph_format.get(key)
        if value is not None:
            try:
                if attr_name == "LineSpacingRule":
                    set_enum_property(executor, paragraph.ParagraphFormat, attr_name, value)
                else:
                    setattr(paragraph.ParagraphFormat, attr_name, float(value))
            except Exception:
                pass
    set_enum_property(executor, paragraph.ParagraphFormat, "Alignment", paragraph_format.get("alignment"))
    for attr_name, key in (
        ("KeepTogether", "keep_together"),
        ("KeepWithNext", "keep_with_next"),
        ("PageBreakBefore", "page_break_before"),
        ("WidowControl", "widow_control"),
    ):
        value = paragraph_format.get(key)
        if value is not None:
            try:
                setattr(paragraph.ParagraphFormat, attr_name, bool(value))
            except Exception:
                pass
    if preserve_existing_run_fonts:
        return
    try:
        runs = paragraph.GetChildNodes(executor.NodeType.Run, True)
    except Exception:
        return
    font_payload = profile.get("font") or {}
    for idx in range(runs.Count):
        run = runs[idx]
        if not executor._clean_text(getattr(run, "Text", "")):
            continue
        apply_run_font(executor, run, font_payload, preserve_emphasis=False)


def normalize_reference_item_paragraph(executor, paragraph, template_interpret_data=None):
    try:
        paragraph.ListFormat.RemoveNumbers()
    except Exception:
        pass
    hanging_indent = None
    if isinstance(template_interpret_data, dict):
        hanging_indent = (((template_interpret_data.get("references") or {}).get("hanging_indent")))
        reference_profile = (((template_interpret_data.get("references") or {}).get("profile")) or {})
        if reference_profile:
            apply_paragraph_profile(executor, paragraph, reference_profile, paragraph.Document if hasattr(paragraph, "Document") else None)
    try:
        if hanging_indent is not None:
            hanging_indent = abs(float(hanging_indent))
            paragraph.ParagraphFormat.LeftIndent = hanging_indent
            paragraph.ParagraphFormat.FirstLineIndent = -hanging_indent
    except Exception:
        pass


def apply_image_profile(executor, paragraph, image_profile):
    if not image_profile:
        return
    try:
        shapes = paragraph.GetChildNodes(executor.NodeType.Shape, True)
    except Exception:
        return
    for idx in range(shapes.Count):
        shape = shapes[idx]
        try:
            if not shape.HasImage:
                continue
        except Exception:
            continue
        if image_profile.get("width") is not None:
            try:
                shape.Width = float(image_profile["width"])
            except Exception:
                pass
        if image_profile.get("height") is not None:
            try:
                shape.Height = float(image_profile["height"])
            except Exception:
                pass


def fix_behind_text_shapes(executor, paragraph):
    try:
        shapes = paragraph.GetChildNodes(executor.NodeType.Shape, True)
    except Exception:
        return
    for idx in range(shapes.Count):
        shape = shapes[idx]
        try:
            if bool(shape.BehindText):
                shape.BehindText = False
        except Exception:
            pass
        try:
            shape.AllowOverlap = False
        except Exception:
            pass
