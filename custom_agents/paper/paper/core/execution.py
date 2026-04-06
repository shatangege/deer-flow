from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from . import extraction
from .aspose_ops.front_matter import render_front_matter_from_template
from .aspose_ops.sections import (
    clear_all_section_bodies,
    copy_template_styles,
    get_target_section,
    normalize_section_starts_for_flow,
    remove_unused_sections,
    resync_all_section_layouts_from_template,
    sync_section_layout_from_template,
)
from .aspose_ops.styles import (
    apply_image_profile,
    apply_paragraph_profile,
    apply_run_font,
    fix_behind_text_shapes,
    normalize_reference_item_paragraph,
    set_color_property,
    set_enum_property,
)
from .aspose_ops.tables import apply_table_profile, ensure_table_spacing, fit_table_within_section_width
from .aspose_ops.text import replace_heading_text_with_template_runs, replace_paragraph_text
from .pathing import aspose_lib_dir, package_root
from .review import build_aggregate_report
from .runtime import load_dependencies, now
from .scheduling import build_section_chunks
from .template_rules import build_rule_bundle, pre_format_check
from .utils import normalize_title
from ..models.contracts import AggregateReport, OutlineItem, RuleBundle, SectionChunk, SectionResult


class PaperRuntimeError(RuntimeError):
    pass


OUTLINE_MODE_ASPOSE_ONLY = "aspose_only"
OUTLINE_MODE_ASPOSE_PLUS_LLM = "aspose_plus_llm"
OUTLINE_MODE_LLM_ONLY = "llm_only"
DEFAULT_OUTLINE_MODE = OUTLINE_MODE_ASPOSE_PLUS_LLM
VALID_OUTLINE_MODES = {
    OUTLINE_MODE_ASPOSE_ONLY,
    OUTLINE_MODE_ASPOSE_PLUS_LLM,
    OUTLINE_MODE_LLM_ONLY,
}


def _diag_enabled() -> bool:
    return os.environ.get("PAPER_ASPOSE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _diag_log(message: str, **fields: object) -> None:
    if not _diag_enabled():
        return
    payload = {"message": message, **fields}
    sys.stderr.write(f"[paper-execution] {payload}\n")
    sys.stderr.flush()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def normalize_outline_mode(value: str | None) -> str:
    normalized = str(value or DEFAULT_OUTLINE_MODE).strip().lower().replace("-", "_")
    if normalized not in VALID_OUTLINE_MODES:
        return DEFAULT_OUTLINE_MODE
    return normalized


def _resolve_existing_path(*candidates: Path) -> Path:
    for candidate in candidates:
        expanded = candidate.expanduser()
        if expanded.exists():
            return expanded.resolve()
    return candidates[0].expanduser().resolve()


def _resolve_existing_native_dir(*candidates: Path) -> Path:
    native_name = "libSkiaSharp.dll" if os.name == "nt" else "libSkiaSharp.so"
    for candidate in candidates:
        expanded = candidate.expanduser()
        if expanded.is_file():
            if expanded.name == native_name:
                return expanded.parent.resolve()
            continue
        if expanded.is_dir() and (expanded / native_name).exists():
            return expanded.resolve()
    return _resolve_existing_path(*candidates)


def _resolve_managed_dir(lib_dir: Path) -> Path:
    env_value = os.getenv("ASPOSE_MANAGED_DIR", "").strip()
    if env_value:
        return _resolve_existing_path(Path(env_value), lib_dir)
    return _resolve_existing_path(
        Path("/opt/paper-agent/managed"),
        lib_dir,
    )


def _resolve_native_dir(lib_dir: Path, managed_dir: Path) -> Path:
    env_value = os.getenv("ASPOSE_NATIVE_DIR", "").strip()
    if env_value:
        return _resolve_existing_native_dir(Path(env_value), Path("/opt/paper-agent/native"), managed_dir, lib_dir)
    return _resolve_existing_native_dir(
        Path("/opt/paper-agent/native"),
        managed_dir,
        lib_dir,
        Path("/app/custom_agents/paper/lib"),
        Path(package_root()) / ".dotnet" / "shared" / "Microsoft.NETCore.App",
    )


def _resolve_license_path(lib_dir: Path) -> Path:
    env_value = os.getenv("ASPOSE_LICENSE_PATH", "").strip()
    default_license = lib_dir / "Aspose.Total.NET.lic"
    if env_value:
        return _resolve_existing_path(Path(env_value), default_license)
    return _resolve_existing_path(
        Path("/opt/paper-agent/license/Aspose.Total.NET.lic"),
        default_license,
    )


@dataclass(slots=True)
class _RuntimeHost:
    script_dir: str
    managed_dir: str
    native_dir: str
    license_path: str
    system: str
    license_loaded: bool = False
    SystemModule: Any | None = None
    SystemDrawingModule: Any | None = None
    License: Any | None = None
    Document: Any | None = None
    LayoutCollector: Any | None = None
    NodeType: Any | None = None
    SaveFormat: Any | None = None
    ImportFormatMode: Any | None = None
    Run: Any | None = None
    Paragraph: Any | None = None


class AsposeExecutionAgent:
    _runtime_ready = False
    _runtime_exports: dict[str, Any] = {}
    _preferred_width: Any | None = None
    _license_loaded = False

    def __init__(self) -> None:
        lib_dir = Path(aspose_lib_dir())
        managed_dir = _resolve_managed_dir(lib_dir)
        native_dir = _resolve_native_dir(lib_dir, managed_dir)
        license_path = _resolve_license_path(lib_dir)
        self.script_dir = str(package_root())
        self.managed_dir = str(managed_dir)
        self.native_dir = str(native_dir)
        self.license_path = str(license_path)
        self.system = "windows" if os.name == "nt" else "linux"
        self._ensure_runtime()

        self.apply_run_font = lambda run, payload, preserve_emphasis=False: apply_run_font(self, run, payload, preserve_emphasis)
        self.apply_paragraph_profile = lambda paragraph, profile, document, is_heading=False, preserve_existing_run_fonts=False: apply_paragraph_profile(
            self, paragraph, profile, document, is_heading=is_heading, preserve_existing_run_fonts=preserve_existing_run_fonts
        )
        self.normalize_reference_item_paragraph = lambda paragraph, interpret=None: normalize_reference_item_paragraph(self, paragraph, interpret)
        self.apply_image_profile = lambda paragraph, profile: apply_image_profile(self, paragraph, profile)
        self.fix_behind_text_shapes = lambda paragraph: fix_behind_text_shapes(self, paragraph)
        self.set_enum_property = lambda obj, attr_name, payload: set_enum_property(self, obj, attr_name, payload)
        self.set_color_property = lambda obj, attr_name, payload: set_color_property(self, obj, attr_name, payload)
        self.replace_paragraph_text = lambda paragraph, text, document, profile=None, preserve_whitespace=False: replace_paragraph_text(
            self, paragraph, text, document, profile=profile, preserve_whitespace=preserve_whitespace
        )
        self.replace_heading_text_with_template_runs = lambda paragraph, text, document, profile=None: replace_heading_text_with_template_runs(
            self, paragraph, text, document, profile=profile
        )
        self.apply_table_profile = lambda table, profile, document: apply_table_profile(self, table, profile, document)
        self.fit_table_within_section_width = lambda table, section, preferred_width=None, preferred_width_type=None, column_widths=None: fit_table_within_section_width(
            self, table, section, preferred_width=preferred_width, preferred_width_type=preferred_width_type, column_widths=column_widths
        )
        self.ensure_table_spacing = lambda table, profile: ensure_table_spacing(self, table, profile)

    def _ensure_runtime(self) -> None:
        if AsposeExecutionAgent._runtime_ready:
            self._bind_cached_runtime()
            return
        started = perf_counter()
        _diag_log("ensure_runtime:start", managed_dir=self.managed_dir, native_dir=self.native_dir)
        host = _RuntimeHost(
            script_dir=self.script_dir,
            managed_dir=self.managed_dir,
            native_dir=self.native_dir,
            license_path=self.license_path,
            system=self.system,
        )
        try:
            load_dependencies(host, globals())
        except Exception as exc:
            _diag_log("ensure_runtime:failed", error=str(exc), elapsed_ms=round((perf_counter() - started) * 1000, 1))
            raise PaperRuntimeError(str(exc)) from exc
        try:
            from Aspose.Words.Tables import PreferredWidth
        except Exception:
            PreferredWidth = None
        AsposeExecutionAgent._runtime_exports = {
            attr: getattr(host, attr)
            for attr in ("SystemModule", "SystemDrawingModule", "License", "Document", "LayoutCollector", "NodeType", "SaveFormat", "ImportFormatMode", "Run", "Paragraph")
        }
        AsposeExecutionAgent._preferred_width = PreferredWidth
        AsposeExecutionAgent._license_loaded = host.license_loaded
        self._bind_cached_runtime()
        AsposeExecutionAgent._runtime_ready = True
        _diag_log("ensure_runtime:done", elapsed_ms=round((perf_counter() - started) * 1000, 1), license_loaded=host.license_loaded)

    def _bind_cached_runtime(self) -> None:
        for attr, value in AsposeExecutionAgent._runtime_exports.items():
            setattr(self, attr, value)
        self.PreferredWidth = AsposeExecutionAgent._preferred_width
        self.license_loaded = AsposeExecutionAgent._license_loaded

    def _outline_llm_settings(self) -> dict[str, str] | None:
        api_key = (os.getenv("PAPER_OUTLINE_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
        model = (os.getenv("PAPER_OUTLINE_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()
        base_url = (os.getenv("PAPER_OUTLINE_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
        if not api_key or not model:
            return None
        return {
            "api_key": api_key,
            "model": model,
            "base_url": base_url,
        }

    def _build_outline_confirmation_prompt(
        self,
        template_docx_path: str,
        outline_candidates: list[dict[str, Any]],
        provisional_outline: list[OutlineItem],
    ) -> str:
        candidate_payload = [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "normalized_title": item.get("normalized_title"),
                "candidate_level": item.get("candidate_level"),
                "level": item.get("level"),
                "source_paragraph_index": item.get("source_paragraph_index"),
                "style_name": item.get("style_name"),
                "page_index": item.get("page_index"),
                "section_role": item.get("section_role"),
                "paragraph_role": item.get("paragraph_role"),
                "is_probable_caption": item.get("is_probable_caption"),
                "is_probable_toc": item.get("is_probable_toc"),
                "is_probable_appendix_heading": item.get("is_probable_appendix_heading"),
                "path": item.get("path"),
            }
            for item in outline_candidates[:200]
        ]
        provisional_payload = [
            {
                "id": item.id,
                "title": item.title,
                "normalized_title": item.normalized_title,
                "level": item.level,
                "order": item.order,
                "source_paragraph_index": item.source_paragraph_index,
                "style_name": item.style_name,
                "page_index": item.page_index,
                "path": item.path,
            }
            for item in provisional_outline[:100]
        ]
        return (
            "You are repairing a paper template outline extracted from a DOCX.\n"
            "Your job is to return the true section outline, removing false positives like captions, tables of contents, running headers, and decorative text.\n"
            "Prefer conservative corrections. Keep real section order. Preserve ids from candidates or provisional items when possible.\n"
            "Return JSON only with shape: {\"confirmed_outline\":[{\"id\":\"...\",\"title\":\"...\",\"level\":1,\"source_paragraph_index\":0}]}\n"
            "Do not include markdown fences.\n\n"
            f"template_docx_path: {template_docx_path}\n"
            f"outline_candidates: {_json_dumps(candidate_payload)}\n"
            f"provisional_outline: {_json_dumps(provisional_payload)}\n"
        )

    def _extract_json_object(self, text: str) -> dict[str, Any] | None:
        payload = (text or "").strip()
        if not payload:
            return None
        try:
            parsed = json.loads(payload)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            snippet = payload[start : end + 1]
            try:
                parsed = json.loads(snippet)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None

    def confirm_outline_with_llm(
        self,
        template_docx_path: str,
        outline_candidates: list[dict[str, Any]],
        provisional_outline: list[OutlineItem],
    ) -> dict[str, Any] | None:
        settings = self._outline_llm_settings()
        if not settings or not outline_candidates:
            _diag_log("confirm_outline_with_llm:skip", reason="missing_settings_or_candidates")
            return None
        prompt = self._build_outline_confirmation_prompt(template_docx_path, outline_candidates, provisional_outline)
        request_payload = {
            "model": settings["model"],
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You correct DOCX outline extraction results. Output strict JSON only.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }
        request_url = f"{settings['base_url']}/chat/completions"
        started = perf_counter()
        _diag_log("confirm_outline_with_llm:start", model=settings["model"], base_url=settings["base_url"])
        try:
            request = urllib.request.Request(
                request_url,
                data=_json_dumps(request_payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings['api_key']}",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            _diag_log(
                "confirm_outline_with_llm:http_error",
                status=exc.code,
                error=detail[:1000],
                elapsed_ms=round((perf_counter() - started) * 1000, 1),
            )
            return None
        except Exception as exc:
            _diag_log("confirm_outline_with_llm:failed", error=str(exc), elapsed_ms=round((perf_counter() - started) * 1000, 1))
            return None
        try:
            response_payload = json.loads(raw)
        except Exception:
            _diag_log("confirm_outline_with_llm:invalid_json", raw_preview=raw[:1000], elapsed_ms=round((perf_counter() - started) * 1000, 1))
            return None
        content = ""
        try:
            choice = (response_payload.get("choices") or [])[0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
        except Exception:
            content = ""
        parsed = self._extract_json_object(content)
        if not parsed:
            _diag_log("confirm_outline_with_llm:unparseable_content", content_preview=str(content)[:1000], elapsed_ms=round((perf_counter() - started) * 1000, 1))
            return None
        confirmed_count = len(parsed.get("confirmed_outline", [])) if isinstance(parsed, dict) else 0
        _diag_log("confirm_outline_with_llm:done", confirmed_count=confirmed_count, elapsed_ms=round((perf_counter() - started) * 1000, 1))
        return parsed

    def _now(self) -> str:
        return now()

    def _clean_text(self, value: Any) -> str:
        return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())

    def _node_text(self, node) -> str:
        try:
            node_range = getattr(node, "Range", None)
            if node_range is not None:
                return self._clean_text(getattr(node_range, "Text", ""))
        except Exception:
            pass
        try:
            to_string = getattr(node, "ToString", None)
            if callable(to_string):
                return self._clean_text(to_string())
        except Exception:
            pass
        return ""

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except Exception:
            return None

    def _safe_style_name(self, paragraph) -> str | None:
        try:
            return self._clean_text(paragraph.ParagraphFormat.StyleName)
        except Exception:
            return None

    def section_content_width(self, section) -> float | None:
        try:
            setup = section.PageSetup
            return float(setup.PageWidth) - float(setup.LeftMargin) - float(setup.RightMargin)
        except Exception:
            return None

    def _detect_heading_level(self, paragraph, text: str) -> int | None:
        style_name = (self._safe_style_name(paragraph) or "").lower()
        for level in range(1, 10):
            if f"heading {level}" in style_name or f"heading{level}" in style_name:
                return level
        outline_level = None
        try:
            outline_level = int(paragraph.ParagraphFormat.OutlineLevel)
        except Exception:
            outline_level = None
        if outline_level is not None and 0 <= outline_level <= 8:
            return outline_level + 1
        lowered = text.strip().lower()
        if lowered and len(lowered) <= 80 and any(ch.isdigit() for ch in lowered[:6]):
            return 1
        return None

    def _color_payload(self, color) -> dict[str, Any] | None:
        try:
            return {"a": int(color.A), "r": int(color.R), "g": int(color.G), "b": int(color.B)}
        except Exception:
            return None

    def _enum_payload(self, value) -> dict[str, Any] | None:
        try:
            return {"value": int(value)}
        except Exception:
            return None

    def load_document(self, docx_path: str):
        path = str(Path(docx_path).expanduser().resolve())
        if not Path(path).exists():
            raise FileNotFoundError(path)
        started = perf_counter()
        _diag_log("load_document:start", docx_path=path)
        document = self.Document(path)
        _diag_log("load_document:done", docx_path=path, elapsed_ms=round((perf_counter() - started) * 1000, 1))
        return document

    def extract_outline(self, docx_path: str) -> list[OutlineItem]:
        return extraction.extract_outline(self, docx_path)

    def extract_outline_candidates(self, docx_path: str) -> list[dict[str, Any]]:
        return extraction.extract_outline_candidates(self, docx_path)

    def extract_structure(self, docx_path: str, outline: list[OutlineItem] | None = None) -> dict[str, Any]:
        effective_outline = outline if outline is not None else self.extract_outline(docx_path)
        return extraction.extract_structure(self, docx_path, effective_outline)

    def _extract_run_font_profile(self, run) -> dict[str, Any]:
        try:
            font = run.Font
            return {
                "name": self._clean_text(getattr(font, "Name", "")) or None,
                "name_far_east": self._clean_text(getattr(font, "NameFarEast", "")) or None,
                "size": float(getattr(font, "Size", 0.0) or 0.0) or None,
                "bold": bool(getattr(font, "Bold", False)),
                "italic": bool(getattr(font, "Italic", False)),
                "underline": self._enum_payload(getattr(font, "Underline", None)),
                "superscript": bool(getattr(font, "Superscript", False)),
                "subscript": bool(getattr(font, "Subscript", False)),
                "color": self._color_payload(getattr(font, "Color", None)),
            }
        except Exception:
            return {}

    def _extract_paragraph_format_profile(self, paragraph) -> dict[str, Any]:
        try:
            fmt = paragraph.ParagraphFormat
            return {
                "alignment": self._enum_payload(getattr(fmt, "Alignment", None)),
                "left_indent": float(getattr(fmt, "LeftIndent", 0.0) or 0.0),
                "right_indent": float(getattr(fmt, "RightIndent", 0.0) or 0.0),
                "first_line_indent": float(getattr(fmt, "FirstLineIndent", 0.0) or 0.0),
                "space_before": float(getattr(fmt, "SpaceBefore", 0.0) or 0.0),
                "space_after": float(getattr(fmt, "SpaceAfter", 0.0) or 0.0),
                "line_spacing": float(getattr(fmt, "LineSpacing", 0.0) or 0.0),
                "line_spacing_rule": self._enum_payload(getattr(fmt, "LineSpacingRule", None)),
                "keep_together": bool(getattr(fmt, "KeepTogether", False)),
                "keep_with_next": bool(getattr(fmt, "KeepWithNext", False)),
                "page_break_before": bool(getattr(fmt, "PageBreakBefore", False)),
                "widow_control": bool(getattr(fmt, "WidowControl", False)),
            }
        except Exception:
            return {}

    def _paragraph_profile_from_node(self, paragraph) -> dict[str, Any]:
        runs = []
        try:
            run_nodes = paragraph.GetChildNodes(self.NodeType.Run, True)
            for idx in range(run_nodes.Count):
                text = getattr(run_nodes[idx], "Text", "")
                if self._clean_text(text):
                    runs.append({"text": text, "font": self._extract_run_font_profile(run_nodes[idx])})
        except Exception:
            pass
        font = runs[0]["font"] if runs else {}
        return {
            "style_name": self._safe_style_name(paragraph),
            "paragraph_format": self._extract_paragraph_format_profile(paragraph),
            "font": font,
            "runs": runs,
        }

    def _table_cell_profile_from_node(self, cell) -> dict[str, Any]:
        paragraph_profile = self._paragraph_profile_from_node(cell.FirstParagraph) if getattr(cell, "FirstParagraph", None) is not None else {}
        try:
            fmt = cell.CellFormat
            return {
                "vertical_alignment": self._enum_payload(getattr(fmt, "VerticalAlignment", None)),
                "left_padding": float(getattr(fmt, "LeftPadding", 0.0) or 0.0),
                "right_padding": float(getattr(fmt, "RightPadding", 0.0) or 0.0),
                "top_padding": float(getattr(fmt, "TopPadding", 0.0) or 0.0),
                "bottom_padding": float(getattr(fmt, "BottomPadding", 0.0) or 0.0),
                "width": float(getattr(fmt, "Width", 0.0) or 0.0) or None,
                "paragraph_format": paragraph_profile.get("paragraph_format"),
                "font": paragraph_profile.get("font"),
            }
        except Exception:
            return {}

    def _table_row_profile_from_node(self, row) -> dict[str, Any]:
        cells = []
        try:
            for idx in range(row.Cells.Count):
                cells.append(self._table_cell_profile_from_node(row.Cells[idx]))
            return {
                "heading_format": bool(getattr(row.RowFormat, "HeadingFormat", False)),
                "height": float(getattr(row.RowFormat, "Height", 0.0) or 0.0) or None,
                "allow_break_across_pages": bool(getattr(row.RowFormat, "AllowBreakAcrossPages", True)),
                "cells": cells,
            }
        except Exception:
            return {"cells": cells}

    def _table_profile_from_node(self, table) -> dict[str, Any]:
        column_widths: list[float] = []
        if getattr(table, "Rows", None) is not None and table.Rows.Count:
            try:
                for idx in range(table.Rows[0].Cells.Count):
                    column_widths.append(float(getattr(table.Rows[0].Cells[idx].CellFormat, "Width", 0.0) or 0.0))
            except Exception:
                column_widths = []
        return {
            "style_name": self._clean_text(getattr(table, "StyleName", "")) or None,
            "alignment": self._enum_payload(getattr(table, "Alignment", None)),
            "allow_auto_fit": bool(getattr(table, "AllowAutoFit", True)),
            "column_widths": column_widths,
            "header_row_profile": self._table_row_profile_from_node(table.Rows[0]) if getattr(table, "Rows", None) is not None and table.Rows.Count else {},
            "body_row_profile": self._table_row_profile_from_node(table.Rows[1]) if getattr(table, "Rows", None) is not None and table.Rows.Count > 1 else {},
        }

    def extract_style_profile(self, docx_path: str, outline: list[OutlineItem]) -> dict[str, Any]:
        document = self.load_document(docx_path)
        structure = self.extract_structure(docx_path, outline=outline)
        paragraph_nodes: dict[int, Any] = {}
        table_nodes: dict[int, Any] = {}
        p_idx = 0
        t_idx = 0
        for _, node in extraction.iter_body_blocks(self, document):
            if node.NodeType == self.NodeType.Paragraph:
                paragraph_nodes[p_idx] = node
                p_idx += 1
            elif node.NodeType == self.NodeType.Table:
                table_nodes[t_idx] = node
                t_idx += 1

        heading_profiles: dict[str, Any] = {}
        body_profiles: dict[str, Any] = {}
        caption_profiles: dict[str, Any] = {}
        front_matter_ordered: list[dict[str, Any]] = []
        reference_profile: dict[str, Any] = {}
        table_profiles: dict[str, Any] = {}
        for block in structure.get("blocks", []):
            if block.get("block_type") == "paragraph":
                node = paragraph_nodes.get(block.get("paragraph_index"))
                if node is None:
                    continue
                profile = self._paragraph_profile_from_node(node)
                if block.get("metadata", {}).get("is_heading"):
                    level = self._detect_heading_level(node, block.get("text", "")) or 1
                    heading_profiles.setdefault(str(level), profile)
                role = block.get("paragraph_role")
                if role and str(role).startswith("caption"):
                    caption_profiles.setdefault(role, profile)
                elif block.get("section_role") == "front_matter":
                    front_matter_ordered.append(profile)
                elif block.get("section_role") == "references":
                    reference_profile = reference_profile or profile
                else:
                    body_profiles.setdefault("default", profile)
            elif block.get("block_type") == "table":
                node = table_nodes.get(block.get("table_index"))
                if node is not None and "default" not in table_profiles:
                    table_profiles["default"] = self._table_profile_from_node(node)

        return {
            "heading_profiles": heading_profiles,
            "heading_styles": heading_profiles,
            "body_profiles": body_profiles,
            "body_style": body_profiles.get("default", {}),
            "caption_profiles": caption_profiles,
            "caption_style": caption_profiles.get("caption", next(iter(caption_profiles.values()), {})),
            "reference_profile": reference_profile,
            "front_matter_profiles": {"ordered": front_matter_ordered, "default": front_matter_ordered[0] if front_matter_ordered else {}},
            "table_profiles": table_profiles,
            "section_layout_profiles": structure.get("section_layouts", []),
            "style_catalog": structure.get("document_styles", []),
        }

    def extract_section_document(self, source_docx_path: str, outline: list[OutlineItem], item: OutlineItem, output_docx_path: str) -> str:
        source_document = self.load_document(source_docx_path)
        result_document = self.Document()
        result_document.RemoveAllChildren()
        result_document.EnsureMinimum()
        result_section = result_document.FirstSection
        start_para = item.source_paragraph_index or 0
        next_items = [entry for entry in outline if (entry.source_paragraph_index or -1) > start_para]
        end_para = min((entry.source_paragraph_index for entry in next_items if entry.source_paragraph_index is not None), default=10**9)
        paragraph_index = 0
        for _, node in extraction.iter_body_blocks(self, source_document):
            if node.NodeType == self.NodeType.Paragraph:
                if start_para <= paragraph_index < end_para:
                    imported = result_document.ImportNode(node, True, self.ImportFormatMode.KeepSourceFormatting)
                    result_section.Body.AppendChild(imported)
                paragraph_index += 1
            elif node.NodeType == self.NodeType.Table and start_para <= paragraph_index < end_para:
                imported = result_document.ImportNode(node, True, self.ImportFormatMode.KeepSourceFormatting)
                result_section.Body.AppendChild(imported)
        Path(output_docx_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        result_document.Save(str(Path(output_docx_path).expanduser().resolve()))
        return str(Path(output_docx_path).expanduser().resolve())

    def split_to_section_docs(self, source_docx_path: str, source_outline: list[OutlineItem], output_dir: str) -> dict[str, str]:
        output_root = Path(output_dir).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        mapping: dict[str, str] = {}
        for item in source_outline:
            mapping[item.id] = self.extract_section_document(source_docx_path, source_outline, item, str(output_root / f"{item.id}.docx"))
        return mapping

    def _build_section_document_from_template(self, chunk: SectionChunk, rules: RuleBundle):
        template_path = Path(rules.template_docx_path).expanduser().resolve()
        if not template_path.exists():
            document = self.Document()
            document.RemoveAllChildren()
            document.EnsureMinimum()
            return document, document.FirstSection
        template_document = self.load_document(str(template_path))
        result_document = self.Document(str(template_path))
        clear_all_section_bodies(self, result_document)
        target_index = chunk.template_section_index if chunk.template_section_index is not None else max(chunk.order - 1, 0)
        target_index = max(int(target_index), 0)
        target_section = get_target_section(self, result_document, template_document, target_index)
        sync_section_layout_from_template(
            self,
            result_document,
            target_section,
            template_document.Sections[min(target_index, template_document.Sections.Count - 1)],
        )
        section_usage = [False] * result_document.Sections.Count
        section_usage[target_index] = True
        remove_unused_sections(self, result_document, section_usage)
        target_section = result_document.Sections[0]
        copy_template_styles(self, result_document, str(template_path))
        return result_document, target_section

    def rewrite_section_content(self, chunk: SectionChunk, rules: RuleBundle, output_docx_path: str) -> tuple[str, list[str], dict[str, Any]]:
        output_path = Path(output_docx_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document, section = self._build_section_document_from_template(chunk, rules)
        content_actions: list[str] = []
        if chunk.source_section_docx_path and Path(chunk.source_section_docx_path).exists():
            source_section_doc = self.load_document(chunk.source_section_docx_path)
            src_section = source_section_doc.FirstSection
            nodes = src_section.Body.GetChildNodes(self.NodeType.Any, False)
            for idx in range(nodes.Count):
                imported = document.ImportNode(nodes[idx], True, self.ImportFormatMode.UseDestinationStyles)
                section.Body.AppendChild(imported)
            content_actions.append(f"import_source_blocks:{len(chunk.source_block_keys)}")
        else:
            heading = section.Body.FirstParagraph or section.Body.AppendParagraph("")
            heading_profile = (chunk.target_element_style_slots or {}).get("heading") or rules.style_profile.get("heading_profiles", {}).get(str(chunk.level), {})
            self.apply_paragraph_profile(heading, heading_profile, document, is_heading=True)
            self.replace_paragraph_text(heading, chunk.template_title, document, profile=heading_profile)
            body = section.Body.AppendParagraph("")
            body_profile = (chunk.target_element_style_slots or {}).get("body_paragraph") or rules.style_profile.get("body_style", {})
            self.apply_paragraph_profile(body, body_profile, document)
            self.replace_paragraph_text(body, f"[Placeholder for {chunk.template_title}]", document, profile=body_profile)
            content_actions.append("create_placeholder_section")
        document.Save(str(output_path))
        return str(output_path), content_actions, dict(chunk.statistics)

    def _resolve_front_matter_slot_name(self, chunk: SectionChunk, block_index: int) -> str | None:
        ordered = ["front_matter_title", "front_matter_abstract", "front_matter_keywords"]
        if chunk.section_role == "front_matter" and block_index < len(ordered):
            return ordered[block_index]
        return None

    def _table_style_slots(self, slot_map: dict[str, Any]) -> list[str]:
        return [name for name in ("table", "table_header_row", "table_body_row", "table_cell") if slot_map.get(name)]

    def _resolve_paragraph_slot_name(self, text: str, para_index: int, chunk: SectionChunk, slot_map: dict[str, Any]) -> str:
        normalized = normalize_title(text)
        if para_index == 0 and slot_map.get("heading"):
            return "heading"
        if chunk.section_role == "front_matter":
            if any(token in normalized for token in ("keyword", "关键词")) and slot_map.get("front_matter_keywords"):
                return "front_matter_keywords"
            if any(token in normalized for token in ("abstract", "摘要")) and slot_map.get("front_matter_abstract"):
                return "front_matter_abstract"
            if para_index == 1 and slot_map.get("front_matter_author_block"):
                return "front_matter_author_block"
            return self._resolve_front_matter_slot_name(chunk, para_index) or "body_paragraph"
        if "reference" in (chunk.section_role or "") and slot_map.get("reference_item"):
            return "reference_item"
        if any(token in normalized for token in ("table", "tab", "表")) and "caption" in normalized and slot_map.get("table_caption"):
            return "table_caption"
        if any(token in normalized for token in ("figure", "fig", "图")) and "caption" in normalized and slot_map.get("figure_caption"):
            return "figure_caption"
        if para_index == 1 and slot_map.get("body_first_paragraph"):
            return "body_first_paragraph"
        return "body_paragraph"

    def apply_section_styles(self, section_docx_path: str, chunk: SectionChunk, rules: RuleBundle) -> tuple[str, list[str], list[str]]:
        document = self.load_document(section_docx_path)
        slot_map = dict(chunk.target_element_style_slots or {})
        style_actions: list[str] = []
        applied_style_slots: list[str] = []
        for section_idx in range(document.Sections.Count):
            section = document.Sections[section_idx]
            if slot_map.get("section_layout") and "section_layout" not in applied_style_slots:
                style_actions.append("apply_section_layout")
                applied_style_slots.append("section_layout")
            nodes = section.Body.GetChildNodes(self.NodeType.Any, False)
            para_count = 0
            for node_idx in range(nodes.Count):
                node = nodes[node_idx]
                if node.NodeType == self.NodeType.Paragraph:
                    text = self._node_text(node)
                    slot_name = self._resolve_paragraph_slot_name(text, para_count, chunk, slot_map)
                    profile = slot_map.get(slot_name) or rules.style_profile.get("body_style", {})
                    self.apply_paragraph_profile(node, profile, document, is_heading=(slot_name == "heading"))
                    if slot_name == "heading":
                        self.replace_heading_text_with_template_runs(node, chunk.template_title, document, profile=profile)
                    if slot_name == "reference_item":
                        self.normalize_reference_item_paragraph(node, rules.interpret)
                    self.fix_behind_text_shapes(node)
                    self.apply_image_profile(node, {})
                    if slot_name and slot_name not in applied_style_slots and profile:
                        applied_style_slots.append(slot_name)
                    style_actions.append(f"apply_{slot_name or 'paragraph'}")
                    para_count += 1
                elif node.NodeType == self.NodeType.Table:
                    table_profile = slot_map.get("table") or next(iter((rules.style_profile.get("table_profiles") or {}).values()), {})
                    self.apply_table_profile(node, table_profile, document)
                    self.fit_table_within_section_width(node, section, column_widths=table_profile.get("column_widths"))
                    self.ensure_table_spacing(node, table_profile)
                    for table_slot in self._table_style_slots(slot_map):
                        if table_slot not in applied_style_slots:
                            applied_style_slots.append(table_slot)
                    style_actions.append("apply_table")
        document.Save(str(Path(section_docx_path).expanduser().resolve()))
        return str(Path(section_docx_path).expanduser().resolve()), style_actions, applied_style_slots

    def validate_section_layout(self, section_docx_path: str, chunk: SectionChunk, rules: RuleBundle) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
        structure = self.extract_structure(section_docx_path)
        issues = list((pre_format_check(structure.get("blocks", []), rules) or {}).get("issues", []))
        if chunk.missing_required_content:
            issues.append({"kind": "missing_required_content", "description": "template section required placeholder content"})
        return issues, structure.get("statistics", {}), list(chunk.risk_flags)

    def merge_section_docs(self, ordered_section_paths: list[str], output_docx_path: str, template_docx_path: str | None = None) -> str:
        output_path = Path(output_docx_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if template_docx_path:
            template_document = self.load_document(template_docx_path)
            result_document = self.Document(template_docx_path)
            clear_all_section_bodies(self, result_document)
            section_usage = [False] * max(result_document.Sections.Count, len(ordered_section_paths))
            for idx, section_path in enumerate(ordered_section_paths):
                section_document = self.load_document(section_path)
                target_section = get_target_section(self, result_document, template_document, idx)
                sync_section_layout_from_template(self, result_document, target_section, template_document.Sections[min(idx, template_document.Sections.Count - 1)])
                nodes = section_document.FirstSection.Body.GetChildNodes(self.NodeType.Any, False)
                for node_idx in range(nodes.Count):
                    imported = result_document.ImportNode(nodes[node_idx], True, self.ImportFormatMode.UseDestinationStyles)
                    target_section.Body.AppendChild(imported)
                section_usage[idx] = True
            remove_unused_sections(self, result_document, section_usage)
            resync_all_section_layouts_from_template(self, result_document, template_document)
            normalize_section_starts_for_flow(self, result_document)
            copy_template_styles(self, result_document, template_docx_path)
            result_document.Save(str(output_path))
            return str(output_path)
        result_document = self.Document()
        result_document.RemoveAllChildren()
        result_document.EnsureMinimum()
        for idx, section_path in enumerate(ordered_section_paths):
            section_document = self.load_document(section_path)
            target_section = result_document.FirstSection if idx == 0 else result_document.Sections.Add(result_document.ImportNode(section_document.FirstSection, False, self.ImportFormatMode.KeepSourceFormatting))
            nodes = section_document.FirstSection.Body.GetChildNodes(self.NodeType.Any, False)
            for node_idx in range(nodes.Count):
                target_section.Body.AppendChild(result_document.ImportNode(nodes[node_idx], True, self.ImportFormatMode.KeepSourceFormatting))
        normalize_section_starts_for_flow(self, result_document)
        result_document.Save(str(output_path))
        return str(output_path)

    def normalize_section_flow(self, input_docx_path: str, output_docx_path: str) -> str:
        document = self.load_document(input_docx_path)
        normalize_section_starts_for_flow(self, document)
        out = Path(output_docx_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        document.Save(str(out))
        return str(out)

    def validate_outline_alignment(self, docx_path: str, rules: RuleBundle) -> tuple[bool, list[str]]:
        outline = self.extract_outline(docx_path)
        actual = [item.normalized_title for item in outline]
        expected = [item.normalized_title for item in (rules.target_outline or rules.template_outline)]
        missing = [title for title in expected if title not in actual]
        return not missing, missing


class TemplateRuleAgent:
    def __init__(self, executor: AsposeExecutionAgent) -> None:
        self.executor = executor

    def run(self, template_docx_path: str, outline_mode: str = DEFAULT_OUTLINE_MODE) -> tuple[RuleBundle, dict[str, Any], list[OutlineItem]]:
        resolution = self._resolve_outline(
            docx_path=template_docx_path,
            outline_mode=outline_mode,
            document_kind="template",
        )
        confirmed_outline = list(resolution["outline"])
        structure = self.executor.extract_structure(template_docx_path, outline=confirmed_outline)
        style_profile = self.executor.extract_style_profile(template_docx_path, confirmed_outline)
        structure["style_profile"] = style_profile
        structure["reference_profile"] = style_profile.get("reference_profile", {})
        rules = build_rule_bundle(template_docx_path, confirmed_outline, structure, style_profile)
        rules.outline_mode = str(resolution["requested_outline_mode"])
        rules.effective_outline_mode = str(resolution["effective_outline_mode"])
        rules.outline_generation_mode = str(resolution["outline_generation_mode"])
        rules.outline_candidates_summary = list(resolution["outline_candidates"])
        rules.outline_confirmation_notes = list(resolution["notes"])
        rules.template_outline_generation = dict(resolution["record"])
        return rules, structure, confirmed_outline

    def _resolve_outline(
        self,
        docx_path: str,
        outline_mode: str,
        document_kind: str,
    ) -> dict[str, Any]:
        requested_mode = normalize_outline_mode(outline_mode)
        outline_candidates = self.executor.extract_outline_candidates(docx_path)
        provisional_outline = self.executor.extract_outline(docx_path)
        notes: list[str] = []
        confirmed_outline = self._fallback_confirm_outline(outline_candidates, provisional_outline)
        effective_mode = OUTLINE_MODE_ASPOSE_ONLY
        generation_mode = "rules_only"
        llm_attempted = False
        llm_confirmed = False
        fallback_used = requested_mode == OUTLINE_MODE_ASPOSE_ONLY

        if requested_mode == OUTLINE_MODE_ASPOSE_ONLY:
            notes.append("outline mode aspose_only selected; skipped llm confirmation")
        else:
            llm_attempted = True
            confirm = getattr(self.executor, "confirm_outline_with_llm", None)
            requested_effective_mode = OUTLINE_MODE_ASPOSE_PLUS_LLM if requested_mode == OUTLINE_MODE_LLM_ONLY else requested_mode
            if requested_mode == OUTLINE_MODE_LLM_ONLY:
                notes.append("outline mode llm_only is experimental; using Aspose candidates as the correction substrate")
            if callable(confirm):
                payload = confirm(docx_path, outline_candidates, provisional_outline)
                llm_outline = self._outline_from_confirmation_payload(payload, provisional_outline)
                if llm_outline:
                    confirmed_outline = llm_outline
                    llm_confirmed = True
                    fallback_used = False
                    effective_mode = requested_effective_mode
                    generation_mode = "rules_plus_llm"
                    notes.append("outline confirmed with llm")
                else:
                    notes.append(f"outline mode {requested_mode} fell back to Aspose rules because llm confirmation returned no usable outline")
            else:
                notes.append(f"outline mode {requested_mode} fell back to Aspose rules because llm confirmation is unavailable")

        record = {
            "document_kind": document_kind,
            "requested_outline_mode": requested_mode,
            "effective_outline_mode": effective_mode,
            "outline_generation_mode": generation_mode,
            "outline_candidate_count": len(outline_candidates),
            "provisional_outline_count": len(provisional_outline),
            "confirmed_outline_count": len(confirmed_outline),
            "llm_attempted": llm_attempted,
            "llm_confirmed": llm_confirmed,
            "fallback_used": fallback_used,
            "experimental_mode": requested_mode == OUTLINE_MODE_LLM_ONLY,
            "notes": list(notes),
            "outline": [item.to_dict() for item in confirmed_outline],
        }
        _diag_log(
            "outline_resolution",
            document_kind=document_kind,
            requested_outline_mode=requested_mode,
            effective_outline_mode=effective_mode,
            outline_generation_mode=generation_mode,
            llm_attempted=llm_attempted,
            llm_confirmed=llm_confirmed,
            fallback_used=fallback_used,
            confirmed_outline_count=len(confirmed_outline),
        )
        return {
            "outline": confirmed_outline,
            "outline_candidates": outline_candidates,
            "provisional_outline": provisional_outline,
            "requested_outline_mode": requested_mode,
            "effective_outline_mode": effective_mode,
            "outline_generation_mode": generation_mode,
            "notes": notes,
            "record": record,
        }

    def _confirm_template_outline(
        self,
        template_docx_path: str,
        outline_candidates: list[dict[str, Any]],
        provisional_outline: list[OutlineItem],
    ) -> tuple[list[OutlineItem], str, list[str]]:
        confirm = getattr(self.executor, "confirm_outline_with_llm", None)
        if callable(confirm):
            payload = confirm(template_docx_path, outline_candidates, provisional_outline)
            confirmed = self._outline_from_confirmation_payload(payload, provisional_outline)
            if confirmed:
                return confirmed, "rules_plus_llm", ["outline confirmed with llm"]
        return self._fallback_confirm_outline(outline_candidates, provisional_outline), "rules_only", ["outline confirmed with rules fallback"]

    def _outline_from_confirmation_payload(self, payload: Any, provisional_outline: list[OutlineItem]) -> list[OutlineItem]:
        confirmed = []
        items = (payload or {}).get("confirmed_outline", []) if isinstance(payload, dict) else []
        for order, item in enumerate(items, start=1):
            original = next((candidate for candidate in provisional_outline if candidate.id == item.get("id")), None)
            title = item.get("title") or (original.title if original else "")
            confirmed.append(
                OutlineItem(
                    id=item.get("id") or (original.id if original else f"h{order}"),
                    title=title,
                    normalized_title=normalize_title(title),
                    level=int(item.get("level") or (original.level if original else 1)),
                    order=order,
                    source_paragraph_index=item.get("source_paragraph_index", original.source_paragraph_index if original else None),
                    style_name=original.style_name if original else None,
                    page_index=original.page_index if original else None,
                    path=list(original.path if original else [title]),
                )
            )
        return confirmed

    def _fallback_confirm_outline(self, outline_candidates: list[dict[str, Any]], provisional_outline: list[OutlineItem]) -> list[OutlineItem]:
        if not outline_candidates:
            return provisional_outline
        confirmed = []
        for order, candidate in enumerate(outline_candidates, start=1):
            if candidate.get("is_probable_caption") or candidate.get("is_probable_toc"):
                continue
            title = candidate.get("title", "")
            confirmed.append(
                OutlineItem(
                    id=candidate.get("id", f"h{order}"),
                    title=title,
                    normalized_title=normalize_title(title),
                    level=int(candidate.get("candidate_level") or candidate.get("level") or 1),
                    order=len(confirmed) + 1,
                    source_paragraph_index=candidate.get("source_paragraph_index"),
                    style_name=candidate.get("style_name"),
                    page_index=candidate.get("page_index"),
                    path=list(candidate.get("path") or [title]),
                )
            )
        return confirmed or provisional_outline


class FlowSchedulerAgent:
    def __init__(self, executor: AsposeExecutionAgent) -> None:
        self.executor = executor
        self._outline_agent = TemplateRuleAgent(executor)

    def run(self, source_docx_path: str, rule_bundle: RuleBundle, split_root: str, outline_mode: str | None = None) -> tuple[list[SectionChunk], dict[str, Any], dict[str, str]]:
        resolution = self._outline_agent._resolve_outline(
            docx_path=source_docx_path,
            outline_mode=outline_mode or rule_bundle.outline_mode,
            document_kind="source",
        )
        source_outline = list(resolution["outline"])
        source_structure = self.executor.extract_structure(source_docx_path, outline=source_outline)
        rule_bundle.source_outline_generation = dict(resolution["record"])
        target_outline, outline_mapping = self._build_target_outline(rule_bundle, source_outline)
        rule_bundle.target_outline = target_outline
        rule_bundle.mapping_rules = {
            **dict(rule_bundle.mapping_rules or {}),
            "target_outline_strategy": "template_backbone_plus_source_append",
            "source_to_target_outline_map": outline_mapping,
            "source_outline_mode": dict(resolution["record"]),
        }
        self._ensure_target_section_styles(rule_bundle)
        split_map = self.executor.split_to_section_docs(source_docx_path, source_outline, split_root)
        return build_section_chunks(
            source_docx_path=source_docx_path,
            source_outline=source_outline,
            source_structure=source_structure,
            rule_bundle=rule_bundle,
            split_map=split_map,
        ), source_structure, split_map

    def _section_alias_candidates(self, item: OutlineItem) -> set[str]:
        normalized = item.normalized_title
        aliases = {normalized}
        lowered = item.title.lower()
        if any(token in normalized for token in ("abstract", "摘要")):
            aliases.update({"abstract", "摘要"})
        if any(token in normalized for token in ("keyword", "关键词")):
            aliases.update({"keywords", "keyword", "关键词"})
        if any(token in normalized for token in ("reference", "references", "bibliography", "参考文献")):
            aliases.update({"reference", "references", "bibliography", "参考文献"})
        if any(token in normalized for token in ("appendix", "附录")):
            aliases.update({"appendix", "附录"})
        if any(token in lowered for token in ("acknowledgement", "acknowledgment")) or "致谢" in item.title:
            aliases.update({"acknowledgements", "acknowledgments", "致谢"})
        return {normalize_title(alias) for alias in aliases if alias}

    def _build_target_outline(self, rule_bundle: RuleBundle, source_outline: list[OutlineItem]) -> tuple[list[OutlineItem], list[dict[str, Any]]]:
        template_outline = list(rule_bundle.template_outline)
        template_by_title = {item.normalized_title: item for item in template_outline}
        template_by_alias: dict[str, OutlineItem] = {}
        for item in template_outline:
            for alias in self._section_alias_candidates(item):
                template_by_alias.setdefault(alias, item)
        target_outline = list(template_outline)
        outline_mapping: list[dict[str, Any]] = []
        next_order = len(target_outline) + 1
        for source_item in source_outline:
            matched_template = template_by_title.get(source_item.normalized_title)
            match_kind = "exact_title_match"
            if matched_template is None:
                matched_template = template_by_alias.get(source_item.normalized_title)
                if matched_template is not None:
                    match_kind = "conservative_alias_match"
            if matched_template is not None:
                outline_mapping.append(
                    {
                        "source_section_id": source_item.id,
                        "source_title": source_item.title,
                        "source_normalized_title": source_item.normalized_title,
                        "target_section_id": matched_template.id,
                        "target_title": matched_template.title,
                        "target_normalized_title": matched_template.normalized_title,
                        "match_kind": match_kind,
                    }
                )
                continue
            appended_item = OutlineItem(
                id=f"src-{source_item.id}",
                title=source_item.title,
                normalized_title=source_item.normalized_title,
                level=source_item.level,
                order=next_order,
                source_paragraph_index=source_item.source_paragraph_index,
                style_name=source_item.style_name,
                page_index=source_item.page_index,
                path=list(source_item.path),
            )
            target_outline.append(appended_item)
            outline_mapping.append(
                {
                    "source_section_id": source_item.id,
                    "source_title": source_item.title,
                    "source_normalized_title": source_item.normalized_title,
                    "target_section_id": appended_item.id,
                    "target_title": appended_item.title,
                    "target_normalized_title": appended_item.normalized_title,
                    "match_kind": "source_only_append",
                }
            )
            next_order += 1
        return target_outline, outline_mapping

    def _ensure_target_section_styles(self, rule_bundle: RuleBundle) -> None:
        heading_profiles = rule_bundle.style_profile.get("heading_profiles") or rule_bundle.style_profile.get("heading_styles", {})
        body_profile = (rule_bundle.style_profile.get("body_profiles") or {}).get("default") or rule_bundle.style_profile.get("body_style", {})
        caption_profiles = rule_bundle.style_profile.get("caption_profiles") or {}
        reference_profile = rule_bundle.style_profile.get("reference_profile") or {}
        table_profiles = rule_bundle.style_profile.get("table_profiles") or {}
        default_table_profile = next(iter(table_profiles.values()), {})
        section_layout_profiles = rule_bundle.style_profile.get("section_layout_profiles") or []
        for item in rule_bundle.target_outline:
            if item.normalized_title in rule_bundle.section_element_style_map:
                continue
            body_row_cells = ((default_table_profile or {}).get("body_row_profile") or {}).get("cells") or []
            table_cell_profile = body_row_cells[0] if body_row_cells else {}
            rule_bundle.section_element_style_map[item.normalized_title] = {
                "section_id": item.id,
                "normalized_title": item.normalized_title,
                "title": item.title,
                "order": item.order,
                "level": item.level,
                "section_role": "body",
                "element_styles": {
                    "heading": heading_profiles.get(str(item.level), heading_profiles.get("1", {})),
                    "subheading_level_2": heading_profiles.get("2", heading_profiles.get("1", {})),
                    "subheading_level_3": heading_profiles.get("3", heading_profiles.get("1", {})),
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
                },
            }


class SectionProcessorAgent:
    def __init__(self, executor: AsposeExecutionAgent) -> None:
        self.executor = executor

    def run(self, chunk: SectionChunk, rule_bundle: RuleBundle, output_docx_path: str) -> SectionResult:
        section_output_docx_path, content_actions, before_stats = self.executor.rewrite_section_content(chunk, rule_bundle, output_docx_path)
        section_output_docx_path, style_actions, applied_style_slots = self.executor.apply_section_styles(section_output_docx_path, chunk, rule_bundle)
        validation_issues, after_stats, remaining_risks = self.executor.validate_section_layout(section_output_docx_path, chunk, rule_bundle)
        return SectionResult(
            chunk_id=chunk.chunk_id,
            section_output_docx_path=section_output_docx_path,
            content_actions=content_actions,
            style_actions=style_actions,
            validation_issues=validation_issues,
            section_pass=not validation_issues,
            repair_actions=[issue.get("kind", "issue") for issue in validation_issues],
            section_statistics_before=before_stats,
            section_statistics_after=after_stats,
            remaining_risks=remaining_risks,
            applied_style_slots=applied_style_slots,
            style_slot_mismatches=[],
            consumed_source_block_keys=list(chunk.assigned_source_blocks),
            unmapped_source_block_keys=list(chunk.unmapped_source_block_keys),
            block_mapping_summary=dict(chunk.block_mapping_summary or {}),
            block_mapping_warnings=list(chunk.block_mapping_warnings or []),
            content_integrity_pass=not chunk.unmapped_source_block_keys,
            source_mapping_kind=chunk.source_mapping_kind,
            template_section_title=chunk.template_title,
            template_section_order=chunk.order,
            metadata={
                "target_element_style_slots": list((chunk.target_element_style_slots or {}).keys()),
                "target_mapping_record": dict(chunk.target_mapping_record or {}),
            },
        )


class AggregationReviewAgent:
    def __init__(self, executor: AsposeExecutionAgent) -> None:
        self.executor = executor

    def run(self, section_results: list[SectionResult], rule_bundle: RuleBundle, final_docx_path: str) -> tuple[str, AggregateReport]:
        ordered_paths = [item.section_output_docx_path for item in sorted(section_results, key=lambda result: result.template_section_order)]
        final_path = self.executor.merge_section_docs(ordered_paths, final_docx_path, template_docx_path=rule_bundle.template_docx_path)
        payload = build_aggregate_report(self.executor, final_path, rule_bundle, section_results)
        return final_path, AggregateReport(**payload)
