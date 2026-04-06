from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class OutlineItem:
    id: str
    title: str
    normalized_title: str
    level: int
    order: int
    source_paragraph_index: int | None = None
    style_name: str | None = None
    page_index: int | None = None
    path: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DocumentBlock:
    block_key: str
    block_type: str
    block_index: int
    paragraph_index: int | None = None
    table_index: int | None = None
    section_index: int = 0
    text: str = ""
    normalized_text: str = ""
    style_name: str | None = None
    section_path: list[dict[str, Any]] = field(default_factory=list)
    section_role: str | None = None
    paragraph_role: str | None = None
    page_index: int | None = None
    image_count: int = 0
    equation_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DocumentBlock":
        return cls(**payload)


@dataclass(slots=True)
class RuleBundle:
    template_docx_path: str
    template_outline: list[OutlineItem]
    heading_levels: dict[str, int]
    style_profile: dict[str, Any]
    required_sections: list[str]
    target_outline: list[OutlineItem] = field(default_factory=list)
    outline_mode: str = "aspose_plus_llm"
    effective_outline_mode: str = "aspose_plus_llm"
    outline_generation_mode: str = "rules_only"
    outline_candidates_summary: list[dict[str, Any]] = field(default_factory=list)
    outline_confirmation_notes: list[str] = field(default_factory=list)
    template_outline_generation: dict[str, Any] = field(default_factory=dict)
    source_outline_generation: dict[str, Any] = field(default_factory=dict)
    template_structure_summary: dict[str, Any] = field(default_factory=dict)
    layout_profile: dict[str, Any] = field(default_factory=dict)
    section_styles: list[dict[str, Any]] = field(default_factory=list)
    section_element_style_map: dict[str, Any] = field(default_factory=dict)
    role_slots: dict[str, Any] = field(default_factory=dict)
    interpret: dict[str, Any] = field(default_factory=dict)
    mapping_rules: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["template_outline"] = [item.to_dict() for item in self.template_outline]
        payload["target_outline"] = [item.to_dict() for item in self.target_outline]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuleBundle":
        return cls(
            template_docx_path=payload["template_docx_path"],
            template_outline=[OutlineItem(**item) for item in payload.get("template_outline", [])],
            target_outline=[OutlineItem(**item) for item in payload.get("target_outline", payload.get("template_outline", []))],
            heading_levels=dict(payload.get("heading_levels", {})),
            style_profile=dict(payload.get("style_profile", {})),
            required_sections=list(payload.get("required_sections", [])),
            outline_mode=str(payload.get("outline_mode", "aspose_plus_llm")),
            effective_outline_mode=str(payload.get("effective_outline_mode", payload.get("outline_mode", "aspose_plus_llm"))),
            outline_generation_mode=str(payload.get("outline_generation_mode", "rules_only")),
            outline_candidates_summary=list(payload.get("outline_candidates_summary", [])),
            outline_confirmation_notes=list(payload.get("outline_confirmation_notes", [])),
            template_outline_generation=dict(payload.get("template_outline_generation", {})),
            source_outline_generation=dict(payload.get("source_outline_generation", {})),
            template_structure_summary=dict(payload.get("template_structure_summary", {})),
            layout_profile=dict(payload.get("layout_profile", {})),
            section_styles=list(payload.get("section_styles", [])),
            section_element_style_map=dict(payload.get("section_element_style_map", {})),
            role_slots=dict(payload.get("role_slots", {})),
            interpret=dict(payload.get("interpret", {})),
            mapping_rules=dict(payload.get("mapping_rules", {})),
        )


@dataclass(slots=True)
class SectionChunk:
    chunk_id: str
    template_section_id: str
    template_title: str
    normalized_template_title: str
    level: int
    order: int
    source_docx_path: str
    source_section_docx_path: str | None = None
    source_heading_title: str | None = None
    source_mapping_kind: str | None = None
    target_mapping_record: dict[str, Any] = field(default_factory=dict)
    source_excerpt: str = ""
    source_paragraph_range: tuple[int | None, int | None] = (None, None)
    source_block_range: tuple[int | None, int | None] = (None, None)
    source_block_keys: list[str] = field(default_factory=list)
    section_role: str | None = None
    template_section_index: int | None = None
    layout_flow_mode: str = "continuous"
    preferred_section_start: str | None = None
    allow_page_break_before: bool = False
    keep_with_next_hints: list[str] = field(default_factory=list)
    target_element_style_slots: dict[str, Any] = field(default_factory=dict)
    assigned_source_blocks: list[str] = field(default_factory=list)
    unmapped_source_block_keys: list[str] = field(default_factory=list)
    block_mapping_summary: dict[str, Any] = field(default_factory=dict)
    block_mapping_warnings: list[dict[str, Any]] = field(default_factory=list)
    style_slot_hints: list[str] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)
    missing_required_content: bool = False
    risk_flags: list[str] = field(default_factory=list)
    route: str = "staged"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_paragraph_range"] = list(self.source_paragraph_range)
        payload["source_block_range"] = list(self.source_block_range)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SectionChunk":
        data = dict(payload)
        data["source_paragraph_range"] = tuple(data.get("source_paragraph_range") or (None, None))
        data["source_block_range"] = tuple(data.get("source_block_range") or (None, None))
        return cls(**data)


@dataclass(slots=True)
class SectionResult:
    chunk_id: str
    section_output_docx_path: str
    content_actions: list[str]
    style_actions: list[str]
    validation_issues: list[dict[str, Any]]
    section_pass: bool
    repair_actions: list[str] = field(default_factory=list)
    section_statistics_before: dict[str, Any] = field(default_factory=dict)
    section_statistics_after: dict[str, Any] = field(default_factory=dict)
    remaining_risks: list[str] = field(default_factory=list)
    applied_style_slots: list[str] = field(default_factory=list)
    style_slot_mismatches: list[dict[str, Any]] = field(default_factory=list)
    consumed_source_block_keys: list[str] = field(default_factory=list)
    unmapped_source_block_keys: list[str] = field(default_factory=list)
    block_mapping_summary: dict[str, Any] = field(default_factory=dict)
    block_mapping_warnings: list[dict[str, Any]] = field(default_factory=list)
    content_integrity_pass: bool = True
    source_mapping_kind: str | None = None
    template_section_title: str = ""
    template_section_order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SectionResult":
        return cls(**payload)


@dataclass(slots=True)
class RepairPlan:
    issue_kind: str
    owner_agent: str
    target_section_title: str | None = None
    repair_action: str = ""
    reason: str = ""
    retry_scope: str = "global"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AggregateReport:
    final_docx_path: str
    missing_sections: list[str]
    reordered_sections: list[str]
    style_warnings: list[dict[str, Any]]
    section_style_mismatches: list[dict[str, Any]] = field(default_factory=list)
    element_style_mismatches: list[dict[str, Any]] = field(default_factory=list)
    layout_warnings: list[dict[str, Any]] = field(default_factory=list)
    pagination_warnings: list[dict[str, Any]] = field(default_factory=list)
    section_break_warnings: list[dict[str, Any]] = field(default_factory=list)
    excess_blank_space_warnings: list[dict[str, Any]] = field(default_factory=list)
    front_matter_warnings: list[dict[str, Any]] = field(default_factory=list)
    content_integrity_warnings: list[dict[str, Any]] = field(default_factory=list)
    block_mapping_warnings: list[dict[str, Any]] = field(default_factory=list)
    unmapped_source_blocks: list[str] = field(default_factory=list)
    duplicate_mapped_blocks: list[str] = field(default_factory=list)
    mapping_warnings: list[dict[str, Any]] = field(default_factory=list)
    repair_candidates: list[RepairPlan] = field(default_factory=list)
    recommended_next_step: str = ""
    outline_pass: bool = False
    processing_stats: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized: list[RepairPlan] = []
        for item in self.repair_candidates:
            if isinstance(item, RepairPlan):
                normalized.append(item)
            else:
                normalized.append(RepairPlan(**item))
        self.repair_candidates = normalized

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["repair_candidates"] = [item.to_dict() for item in self.repair_candidates]
        return payload
