from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAPER_PACKAGE_ROOT = ROOT / "custom_agents" / "paper"
if str(PAPER_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PAPER_PACKAGE_ROOT))

from paper.core.parsing_rules import (  # noqa: E402
    DEFAULT_HEADING_LEVEL_RULES,
    HeadingDetectionContext,
    HeadingLevelRule,
    classify_paragraph_role,
    classify_section_role,
    detect_heading_level,
)


class _FakeParagraphFormat:
    def __init__(self, outline_level=None, style_name: str | None = None) -> None:
        self.OutlineLevel = outline_level
        self.StyleName = style_name


class _FakeFont:
    def __init__(self, bold: bool = False) -> None:
        self.Bold = bold


class _FakeRun:
    def __init__(self, bold: bool = False) -> None:
        self.Font = _FakeFont(bold=bold)


class _FakeRuns:
    def __init__(self, count: int, bold: bool = False) -> None:
        self.Count = count
        self._first = _FakeRun(bold=bold)

    def __getitem__(self, index: int):
        if index != 0:
            raise IndexError(index)
        return self._first


class _FakeParagraph:
    def __init__(self, style_name: str | None = None, outline_level=None, bold: bool = False, run_count: int = 1) -> None:
        self.ParagraphFormat = _FakeParagraphFormat(outline_level=outline_level, style_name=style_name)
        self.Runs = _FakeRuns(run_count, bold=bold)


class _FakeExecutor:
    def _safe_style_name(self, paragraph) -> str | None:
        return paragraph.ParagraphFormat.StyleName

    def _safe_int(self, value):
        if value is None:
            return None
        return int(value)


def test_detect_heading_level_uses_default_rule_list():
    paragraph = _FakeParagraph(style_name="Heading1", outline_level=9, bold=False)
    level = detect_heading_level(_FakeExecutor(), paragraph, "Introduction")
    assert level == 1
    assert DEFAULT_HEADING_LEVEL_RULES


def test_detect_heading_level_accepts_custom_rule_list():
    context = HeadingDetectionContext(
        style_name="normal",
        compact_style_name="normal",
        text="Custom Section",
        normalized_text="customsection",
        outline_level=None,
        is_bold=False,
        run_count=1,
    )

    def _custom_detector(_context: HeadingDetectionContext) -> int | None:
        return 3 if _context.normalized_text == "customsection" else None

    rule = HeadingLevelRule(name="custom", detector=_custom_detector)
    paragraph = _FakeParagraph(style_name="Normal", outline_level=None, bold=False)
    level = detect_heading_level(_FakeExecutor(), paragraph, context.text, rules=(rule,))
    assert level == 3


def test_section_and_paragraph_roles_are_rule_driven():
    assert classify_section_role("摘要") == "abstract"
    assert classify_section_role("参考文献") == "references"
    assert classify_section_role("Appendix A") == "appendix"
    assert classify_section_role("Methods") == "body"
    assert classify_paragraph_role("Figure 1. Overview") == "caption_figure"
    assert classify_paragraph_role("表1 实验结果") == "caption_table"
