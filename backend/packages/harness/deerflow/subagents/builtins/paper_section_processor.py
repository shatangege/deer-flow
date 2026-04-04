from deerflow.subagents.config import SubagentConfig


PAPER_SECTION_PROCESSOR_CONFIG = SubagentConfig(
    name="paper-section-processor",
    description="""Single-section paper processing specialist.

Use this subagent when:
- One section chunk needs content organization or minimal completion
- One section chunk needs template-aligned styling
- One section chunk needs section-level review and repair

Do NOT use for template rule extraction or full-document merge.""",
    system_prompt="""You are the section-processor specialist for Deer Flow's paper pipeline.

Your responsibilities:
- Process exactly one section chunk at a time
- Organize or minimally complete content within template constraints
- Apply section styling to match the template rules
- Run section-level validation and report remaining issues

Boundaries:
- Do not invent facts, data, conclusions, or references
- Do not perform full-document aggregation
- Prefer structural completion and formatting over freeform writing
""",
    tools=[
        "paper_process_paper_section",
        "paper_rewrite_section_content",
        "paper_apply_section_styles",
        "paper_validate_section_layout",
        "read_file",
        "ls",
    ],
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model="inherit",
    max_turns=30,
)
