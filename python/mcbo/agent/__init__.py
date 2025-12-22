"""
MCBO Agent - LLM-powered competency question evaluation.

This module provides an LLM orchestrator that uses pre-built analysis tools
to answer MCBO competency questions requiring statistical analysis,
correlation computation, and pathway enrichment.
"""

from .sparql_templates import SPARQL_TEMPLATES, get_template, format_template
from .stats_tools import (
    compute_correlation,
    compute_fold_change,
    find_peak_conditions,
    filter_by_threshold,
    differential_expression,
)
from .pathway_tools import (
    get_pathway_enrichment,
    get_kegg_pathways,
    load_local_pathway_db,
)
from .tools import TOOL_DEFINITIONS, execute_tool
from .orchestrator import AgentOrchestrator, get_provider

__all__ = [
    # SPARQL templates
    "SPARQL_TEMPLATES",
    "get_template",
    "format_template",
    # Statistics tools
    "compute_correlation",
    "compute_fold_change",
    "find_peak_conditions",
    "filter_by_threshold",
    "differential_expression",
    # Pathway tools
    "get_pathway_enrichment",
    "get_kegg_pathways",
    "load_local_pathway_db",
    # Tool definitions
    "TOOL_DEFINITIONS",
    "execute_tool",
    # Orchestrator
    "AgentOrchestrator",
    "get_provider",
]

