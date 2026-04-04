"""Built-in subagent configurations."""

from .bash_agent import BASH_AGENT_CONFIG
from .general_purpose import GENERAL_PURPOSE_CONFIG
from .paper_aggregation_review import PAPER_AGGREGATION_REVIEW_CONFIG
from .paper_aspose_executor import PAPER_ASPOSE_EXECUTOR_CONFIG
from .paper_flow_scheduler import PAPER_FLOW_SCHEDULER_CONFIG
from .paper_section_processor import PAPER_SECTION_PROCESSOR_CONFIG
from .paper_template_rules import PAPER_TEMPLATE_RULES_CONFIG

__all__ = [
    "GENERAL_PURPOSE_CONFIG",
    "BASH_AGENT_CONFIG",
    "PAPER_TEMPLATE_RULES_CONFIG",
    "PAPER_FLOW_SCHEDULER_CONFIG",
    "PAPER_SECTION_PROCESSOR_CONFIG",
    "PAPER_ASPOSE_EXECUTOR_CONFIG",
    "PAPER_AGGREGATION_REVIEW_CONFIG",
]

# Registry of built-in subagents
BUILTIN_SUBAGENTS = {
    "general-purpose": GENERAL_PURPOSE_CONFIG,
    "bash": BASH_AGENT_CONFIG,
    "paper-template-rules": PAPER_TEMPLATE_RULES_CONFIG,
    "paper-flow-scheduler": PAPER_FLOW_SCHEDULER_CONFIG,
    "paper-section-processor": PAPER_SECTION_PROCESSOR_CONFIG,
    "paper-aspose-executor": PAPER_ASPOSE_EXECUTOR_CONFIG,
    "paper-aggregation-review": PAPER_AGGREGATION_REVIEW_CONFIG,
}
