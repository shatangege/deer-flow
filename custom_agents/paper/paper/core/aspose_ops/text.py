from __future__ import annotations


def replace_paragraph_text(executor, paragraph, text, document, profile=None, preserve_whitespace=False):
    try:
        runs = paragraph.GetChildNodes(executor.NodeType.Run, True)
        for idx in range(runs.Count - 1, -1, -1):
            runs[idx].Remove()
    except Exception:
        pass

    rendered_text = text if preserve_whitespace else executor._clean_text(text)
    if not rendered_text:
        return

    run = executor.Run(document, rendered_text)
    paragraph.AppendChild(run)
    if profile and profile.get("font"):
        executor.apply_run_font(run, profile.get("font"), preserve_emphasis=False)


def meaningful_runs(executor, paragraph):
    result = []
    try:
        runs = paragraph.GetChildNodes(executor.NodeType.Run, True)
    except Exception:
        return result
    for idx in range(runs.Count):
        run = runs[idx]
        if executor._clean_text(getattr(run, "Text", "")):
            result.append(run)
    return result


def split_heading_text_parts(executor, text):
    rendered_text = executor._clean_text(text)
    if not rendered_text:
        return ("", "", "")
    return ("", rendered_text, "")


def replace_heading_text_with_template_runs(executor, paragraph, text, document, profile=None):
    meaningful = meaningful_runs(executor, paragraph)
    if len(meaningful) < 2:
        replace_paragraph_text(executor, paragraph, text, document, profile=profile)
        return False

    prefix, body, suffix = split_heading_text_parts(executor, text)
    if not body:
        replace_paragraph_text(executor, paragraph, text, document, profile=profile)
        return False

    segments = [prefix, body, suffix] if len(meaningful) >= 3 else [prefix, body + suffix]
    used_count = 0
    for idx, run in enumerate(meaningful):
        segment = segments[idx] if idx < len(segments) else ""
        if idx == 0 and not segment and len(segments) > 1:
            segment = segments[1]
            segments[1] = ""
        if segment:
            run.Text = segment
            used_count += 1
        else:
            run.Remove()
    if used_count == 0:
        replace_paragraph_text(executor, paragraph, text, document, profile=profile)
        return False
    return True
