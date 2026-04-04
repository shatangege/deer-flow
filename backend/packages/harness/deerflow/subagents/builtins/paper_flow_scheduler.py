from deerflow.subagents.config import SubagentConfig


PAPER_FLOW_SCHEDULER_CONFIG = SubagentConfig(
    name="paper-flow-scheduler",
    description="""Paper section scheduling specialist.

Use this subagent when:
- You need to split a source paper by template outline
- You need to produce section chunks for downstream processing
- You need to reason about missing or mismatched sections

Do NOT use for styling or final merge.""",
    system_prompt="""You are the flow-scheduler specialist for Deer Flow's paper pipeline.

Your responsibilities:
- Use the template rule bundle as the source of truth
- Split the source paper into ordered section chunks
- Preserve template section coverage even when source content is missing
- Report chunking decisions clearly and compactly

Do not process section styling or final aggregation.
""",
    tools=[
        "paper_split_paper_sections",
        "paper_extract_structure",
        "paper_split_to_section_docs",
        "read_file",
        "ls",
    ],
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model="inherit",
    max_turns=20,
)
