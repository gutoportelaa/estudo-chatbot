"""Ferramentas do agente e seu contrato de contexto (issue #32)."""

from .contract import (
    DEFAULT_TRUNCATION_NOTICE,
    Tool,
    ToolResult,
    collect_tool_block,
    fit_to_budget,
)
from .diagram import (
    DiagramArtifact,
    DiagramType,
    detect_diagram_intent,
    generate_diagram,
    validate_mermaid,
)

__all__ = [
    "DEFAULT_TRUNCATION_NOTICE",
    "Tool",
    "ToolResult",
    "collect_tool_block",
    "fit_to_budget",
    "DiagramArtifact",
    "DiagramType",
    "detect_diagram_intent",
    "generate_diagram",
    "validate_mermaid",
]
