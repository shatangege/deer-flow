from deerflow.subagents.config import SubagentConfig


PAPER_TEMPLATE_RULES_CONFIG = SubagentConfig(
    name="paper-template-rules",
    description="""Template paper rules specialist.

Use this subagent when:
- You need to extract the template outline hierarchy
- You need to infer required sections from a template paper
- You need the template style profile before scheduling section work

Do NOT use for section processing or final aggregation.""",
    system_prompt="""You are the template-rules specialist for Deer Flow's paper pipeline.

Your responsibilities:
- Read the template paper structure
- Extract the enforced outline hierarchy
- Extract the global style profile
- Produce a concise result focused on rules, not on final paper output

Never perform whole-document aggregation.
Never assume missing sections are optional unless the template implies it.
""",
    tools=[
        "paper_extract_paper_template_rules",
        "paper_extract_outline",
        "paper_extract_structure",
        "paper_extract_style_profile",
        "read_file",
        "ls",
    ],
    disallowed_tools=["task", "ask_clarification", "present_files"],
    model="inherit",
    max_turns=20,
)
