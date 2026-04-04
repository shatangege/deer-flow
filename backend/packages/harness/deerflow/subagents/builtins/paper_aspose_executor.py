from deerflow.subagents.config import SubagentConfig


PAPER_ASPOSE_EXECUTOR_CONFIG = SubagentConfig(
    name="paper-aspose-executor",
    description="""Paper document execution specialist.

Use this subagent when:
- A paper pipeline step must be executed through the paper MCP tools
- Document operations should stay isolated from the main conversation
- You need a low-level execution result, not high-level planning

Do NOT use for template interpretation or final review decisions.""",
    system_prompt="""You are the Aspose execution specialist for Deer Flow's paper pipeline.

Your responsibilities:
- Execute paper MCP tool calls cleanly
- Return concrete paths and structured results
- Keep responses concise and execution-focused

Do not make orchestration decisions beyond the delegated execution task.
""",
    tools=[
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
        "read_file",
        "ls",
    ],
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model="inherit",
    max_turns=20,
)
