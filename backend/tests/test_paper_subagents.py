from deerflow.subagents.builtins import BUILTIN_SUBAGENTS


def test_paper_subagents_registered():
    expected = {
        "paper-template-rules",
        "paper-flow-scheduler",
        "paper-section-processor",
        "paper-aspose-executor",
        "paper-aggregation-review",
    }
    assert expected.issubset(set(BUILTIN_SUBAGENTS))


def test_paper_section_processor_is_scoped():
    config = BUILTIN_SUBAGENTS["paper-section-processor"]
    assert "paper_process_paper_section" in (config.tools or [])
    assert "paper_rewrite_section_content" in (config.tools or [])
    assert "paper_apply_section_styles" in (config.tools or [])
    assert "paper_validate_section_layout" in (config.tools or [])
    assert "paper_aggregate_paper_sections" not in (config.tools or [])
    assert "paper_extract_paper_template_rules" not in (config.tools or [])


def test_paper_aspose_executor_prefers_low_level_tools():
    config = BUILTIN_SUBAGENTS["paper-aspose-executor"]
    expected = {
        "paper_load_document",
        "paper_extract_outline",
        "paper_extract_structure",
        "paper_extract_style_profile",
        "paper_split_to_section_docs",
        "paper_rewrite_section_content",
        "paper_apply_section_styles",
        "paper_validate_section_layout",
        "paper_merge_section_docs",
        "paper_normalize_section_flow",
        "paper_validate_outline_alignment",
    }
    assert expected.issubset(set(config.tools or []))
    assert "paper_run_paper_pipeline" not in (config.tools or [])
