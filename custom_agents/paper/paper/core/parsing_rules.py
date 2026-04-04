from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .utils import normalize_title


@dataclass(frozen=True, slots=True)
class HeadingDetectionContext:
    style_name: str
    compact_style_name: str
    text: str
    normalized_text: str
    outline_level: int | None
    is_bold: bool
    run_count: int


@dataclass(frozen=True, slots=True)
class HeadingLevelRule:
    name: str
    detector: Callable[[HeadingDetectionContext], int | None]


@dataclass(frozen=True, slots=True)
class TextRoleRule:
    name: str
    role: str
    predicate: Callable[[str, str], bool]


def _style_heading_rule(context: HeadingDetectionContext) -> int | None:
    for level in range(1, 10):
        if (
            f"heading {level}" in context.style_name
            or f"title {level}" in context.style_name
            or f"heading{level}" in context.compact_style_name
            or f"title{level}" in context.compact_style_name
        ):
            return level
    return None


def _outline_level_rule(context: HeadingDetectionContext) -> int | None:
    if context.outline_level is None:
        return None
    if 0 <= context.outline_level <= 8:
        return context.outline_level + 1
    return None


def _bold_short_text_rule(context: HeadingDetectionContext) -> int | None:
    if context.run_count > 0 and context.is_bold and len(context.text) <= 80:
        return 1
    return None


def _short_heading_like_text_rule(context: HeadingDetectionContext) -> int | None:
    words = [part for part in context.text.replace(":", " ").split() if part]
    if not context.normalized_text:
        return None
    if len(context.text) > 80 or len(words) > 12:
        return None
    if any(mark in context.text for mark in (".", "!", "?", ";", "。", "；", "：", "，")):
        return None
    if context.text.strip() == context.text.strip().title():
        return 1
    return None


DEFAULT_HEADING_LEVEL_RULES: tuple[HeadingLevelRule, ...] = (
    HeadingLevelRule(name="style-name", detector=_style_heading_rule),
    HeadingLevelRule(name="outline-level", detector=_outline_level_rule),
    HeadingLevelRule(name="bold-short-text", detector=_bold_short_text_rule),
    HeadingLevelRule(name="short-heading-like-text", detector=_short_heading_like_text_rule),
)


def _contains_any(*keywords: str) -> Callable[[str, str], bool]:
    def predicate(_text: str, normalized_text: str) -> bool:
        return any(keyword in normalized_text for keyword in keywords)

    return predicate


def _starts_with_any(*prefixes: str) -> Callable[[str, str], bool]:
    def predicate(_text: str, normalized_text: str) -> bool:
        return any(normalized_text.startswith(prefix) for prefix in prefixes)

    return predicate


DEFAULT_SECTION_ROLE_RULES: tuple[TextRoleRule, ...] = (
    TextRoleRule(name="abstract", role="abstract", predicate=_contains_any("abstract", "摘要")),
    TextRoleRule(name="references", role="references", predicate=_contains_any("reference", "references", "bibliography", "参考文献")),
    TextRoleRule(name="appendix", role="appendix", predicate=_contains_any("appendix", "附录")),
)


DEFAULT_PARAGRAPH_ROLE_RULES: tuple[TextRoleRule, ...] = (
    TextRoleRule(name="figure-caption", role="caption_figure", predicate=_starts_with_any("figure", "fig", "图")),
    TextRoleRule(name="table-caption", role="caption_table", predicate=_starts_with_any("table", "表")),
    TextRoleRule(name="reference-heading", role="reference_heading", predicate=_contains_any("references", "reference", "bibliography", "参考文献")),
)


def build_heading_detection_context(executor, paragraph, text: str) -> HeadingDetectionContext:
    style_name = str(executor._safe_style_name(paragraph) or "").lower()
    compact_style_name = style_name.replace(" ", "").replace("-", "").replace("_", "")
    try:
        outline_level = executor._safe_int(paragraph.ParagraphFormat.OutlineLevel)
    except Exception:
        outline_level = None
    try:
        is_bold = bool(paragraph.Runs.Count > 0 and paragraph.Runs[0].Font.Bold)
    except Exception:
        is_bold = False
    try:
        run_count = int(paragraph.Runs.Count)
    except Exception:
        run_count = 0
    return HeadingDetectionContext(
        style_name=style_name,
        compact_style_name=compact_style_name,
        text=text,
        normalized_text=normalize_title(text),
        outline_level=outline_level,
        is_bold=is_bold,
        run_count=run_count,
    )


def detect_heading_level(executor, paragraph, text: str, rules: tuple[HeadingLevelRule, ...] = DEFAULT_HEADING_LEVEL_RULES) -> int | None:
    context = build_heading_detection_context(executor, paragraph, text)
    for rule in rules:
        level = rule.detector(context)
        if level is not None:
            return level
    return None


def classify_text_role(text: str, rules: tuple[TextRoleRule, ...], default_role: str | None = None) -> str | None:
    normalized_text = normalize_title(text)
    for rule in rules:
        if rule.predicate(text, normalized_text):
            return rule.role
    return default_role


def classify_section_role(text: str, default_role: str = "body") -> str:
    return classify_text_role(text, DEFAULT_SECTION_ROLE_RULES, default_role=default_role) or default_role


def classify_paragraph_role(text: str) -> str | None:
    return classify_text_role(text, DEFAULT_PARAGRAPH_ROLE_RULES, default_role=None)
