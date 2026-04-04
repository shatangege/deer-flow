from deerflow.subagents.config import SubagentConfig


PAPER_AGGREGATION_REVIEW_CONFIG = SubagentConfig(
    name="paper-aggregation-review",
    description="""Paper aggregation and final review specialist.

Use this subagent when:
- Processed section outputs must be merged into a final paper
- Final outline alignment must be checked
- The final paper result and report need to be produced

Do NOT use for section-level content work.""",
    system_prompt="""You are the aggregation-review specialist for Deer Flow's paper pipeline.

Your responsibilities:
- Merge processed section outputs into the final paper
- Validate outline alignment against the template rules
- Report missing sections, style warnings, and final status clearly

Do not redo section processing work unless explicitly delegated for diagnosis.
""",
    tools=[
        "paper_aggregate_paper_sections",
        "paper_merge_section_docs",
        "paper_validate_outline_alignment",
        "read_file",
        "ls",
    ],
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model="inherit",
    max_turns=20,
)
