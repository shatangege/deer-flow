from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineArtifacts:
    workspace: str
    template_rules: str
    template_outline_candidates: str
    source_outline: str
    source_structure: str
    section_chunks: str
    section_results: str
    processed_sections_dir: str
    aggregate_report: str
    final_docx: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def build_pipeline_artifacts(source_docx_path: str, template_docx_path: str, final_docx_path: str) -> PipelineArtifacts:
    final_path = Path(final_docx_path).expanduser().resolve()
    source_stem = Path(source_docx_path).stem
    template_stem = Path(template_docx_path).stem
    workspace = final_path.parent / f"{final_path.stem}.paper-artifacts"
    processed_sections_dir = workspace / "processed-sections"
    return PipelineArtifacts(
        workspace=str(workspace),
        template_rules=str(workspace / f"{template_stem}.template-rules.json"),
        template_outline_candidates=str(workspace / f"{template_stem}.outline-candidates.json"),
        source_outline=str(workspace / f"{source_stem}.outline.json"),
        source_structure=str(workspace / f"{source_stem}.structure.json"),
        section_chunks=str(workspace / f"{source_stem}.section-chunks.json"),
        section_results=str(workspace / f"{source_stem}.section-results.json"),
        processed_sections_dir=str(processed_sections_dir),
        aggregate_report=str(workspace / f"{final_path.stem}.aggregate-report.json"),
        final_docx=str(final_path),
    )
