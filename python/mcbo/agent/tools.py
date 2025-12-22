"""
Tool definitions for MCBO agent.

Defines the tool schemas that are exposed to the LLM orchestrator,
and provides the execute_tool function to dispatch tool calls.
"""

from typing import Any, Callable, Optional
import json

import pandas as pd
from rdflib import Graph

from .sparql_templates import format_template, list_templates, PREFIXES
from .stats_tools import (
    compute_correlation,
    compute_fold_change,
    find_peak_conditions,
    filter_by_threshold,
    differential_expression,
    summarize_by_group,
)
from .pathway_tools import get_pathway_enrichment


# Tool definitions in OpenAI/Anthropic function calling format
TOOL_DEFINITIONS = [
    {
        "name": "execute_sparql",
        "description": "Execute a SPARQL query on the MCBO RDF graph and return results as a table. "
                       "Use template names for common queries or provide raw SPARQL. "
                       f"Available templates: {', '.join(list_templates())}",
        "input_schema": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Name of a predefined SPARQL template to use",
                },
                "raw_query": {
                    "type": "string", 
                    "description": "Raw SPARQL query (used if template_name not provided)",
                },
                "filter_clause": {
                    "type": "string",
                    "description": "Optional FILTER clause to add to template queries",
                },
            },
        },
    },
    {
        "name": "compute_correlation",
        "description": "Compute Pearson or Spearman correlation between two columns in the data. "
                       "Returns correlation coefficient, p-value, and significance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x_col": {
                    "type": "string",
                    "description": "Name of the first column (x-axis)",
                },
                "y_col": {
                    "type": "string",
                    "description": "Name of the second column (y-axis)",
                },
                "method": {
                    "type": "string",
                    "enum": ["pearson", "spearman"],
                    "description": "Correlation method (default: pearson)",
                },
            },
            "required": ["x_col", "y_col"],
        },
    },
    {
        "name": "compute_fold_change",
        "description": "Compute fold change between two groups. Returns log2 fold change "
                       "and t-test p-value for significance testing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_col": {
                    "type": "string",
                    "description": "Column containing group labels",
                },
                "value_col": {
                    "type": "string",
                    "description": "Column containing values to compare",
                },
                "group1": {
                    "type": "string",
                    "description": "Label for the first group (numerator)",
                },
                "group2": {
                    "type": "string",
                    "description": "Label for the second group (denominator/reference)",
                },
            },
            "required": ["group_col", "value_col", "group1", "group2"],
        },
    },
    {
        "name": "find_peak_conditions",
        "description": "Find conditions associated with peak values of a metric. "
                       "Groups data by condition columns and finds combinations with highest metric values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition_cols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of column names representing conditions (e.g., temperature, pH)",
                },
                "metric_col": {
                    "type": "string",
                    "description": "Column containing the metric to optimize (e.g., productivityValue)",
                },
                "method": {
                    "type": "string",
                    "enum": ["max", "mean", "median"],
                    "description": "How to aggregate within condition groups (default: mean)",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of top condition combinations to return (default: 5)",
                },
            },
            "required": ["condition_cols", "metric_col"],
        },
    },
    {
        "name": "filter_by_threshold",
        "description": "Filter the current data by a threshold condition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "col": {
                    "type": "string",
                    "description": "Column to apply the condition to",
                },
                "op": {
                    "type": "string",
                    "enum": [">", ">=", "<", "<=", "==", "!="],
                    "description": "Comparison operator",
                },
                "value": {
                    "type": "number",
                    "description": "Threshold value",
                },
            },
            "required": ["col", "op", "value"],
        },
    },
    {
        "name": "differential_expression",
        "description": "Perform differential expression analysis between two groups. "
                       "Computes log2 fold change and p-value for each gene. "
                       "Use the cell_line parameter to filter by a specific cell line.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_col": {
                    "type": "string",
                    "description": "Column containing group labels (e.g., processType)",
                },
                "group1": {
                    "type": "string",
                    "description": "Label for treatment/condition group",
                },
                "group2": {
                    "type": "string",
                    "description": "Label for control/reference group",
                },
                "cell_line": {
                    "type": "string",
                    "description": "Cell line to filter by (e.g., HEK293, CHO-K1). Partial match.",
                },
                "gene_col": {
                    "type": "string",
                    "description": "Column containing gene identifiers (default: gene)",
                },
                "value_col": {
                    "type": "string",
                    "description": "Column containing expression values (default: expressionValue)",
                },
                "log2fc_threshold": {
                    "type": "number",
                    "description": "Minimum absolute log2 fold change for significance (default: 1.0)",
                },
                "pvalue_threshold": {
                    "type": "number",
                    "description": "Maximum p-value for significance (default: 0.05)",
                },
            },
            "required": ["group_col", "group1", "group2"],
        },
    },
    {
        "name": "get_pathway_enrichment",
        "description": "Perform pathway enrichment analysis on a list of genes. "
                       "Uses KEGG or Reactome to find pathways overrepresented in the gene list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gene_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of gene symbols to analyze",
                },
                "database": {
                    "type": "string",
                    "enum": ["kegg", "reactome"],
                    "description": "Pathway database to use (default: kegg)",
                },
                "organism": {
                    "type": "string",
                    "description": "Organism code (hsa=human, mmu=mouse, cge=hamster). Default: hsa",
                },
                "pvalue_threshold": {
                    "type": "number",
                    "description": "P-value cutoff for significant pathways (default: 0.05)",
                },
            },
            "required": ["gene_list"],
        },
    },
    {
        "name": "summarize_by_group",
        "description": "Compute summary statistics for a value column grouped by another column.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_col": {
                    "type": "string",
                    "description": "Column to group by",
                },
                "value_col": {
                    "type": "string",
                    "description": "Column to summarize",
                },
            },
            "required": ["group_col", "value_col"],
        },
    },
    {
        "name": "get_significant_genes",
        "description": "Extract significant genes from differential expression results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "both"],
                    "description": "Filter by direction of change (default: both)",
                },
            },
        },
    },
]


class ToolExecutor:
    """Executes tools in the context of a graph and working dataframe."""
    
    def __init__(self, graph: Graph):
        """Initialize with an RDF graph.
        
        Args:
            graph: rdflib Graph containing MCBO data
        """
        self.graph = graph
        self.current_df: Optional[pd.DataFrame] = None
        self.de_results: Optional[pd.DataFrame] = None  # Store DE results
    
    def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and return results.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments as a dict
            
        Returns:
            dict with tool results
        """
        method_name = f"_tool_{tool_name}"
        if not hasattr(self, method_name):
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            return getattr(self, method_name)(arguments)
        except Exception as e:
            return {"error": str(e)}
    
    def _tool_execute_sparql(self, args: dict) -> dict:
        """Execute a SPARQL query."""
        template_name = args.get("template_name")
        raw_query = args.get("raw_query")
        filter_clause = args.get("filter_clause", "")
        
        if template_name:
            query = format_template(template_name, filter_clause=filter_clause)
        elif raw_query:
            if not raw_query.strip().upper().startswith("PREFIX"):
                query = PREFIXES + raw_query
            else:
                query = raw_query
        else:
            return {"error": "Provide either template_name or raw_query"}
        
        # Execute query
        result = self.graph.query(query)
        
        # Convert to DataFrame
        rows = []
        columns = [str(v) for v in result.vars]
        for row in result:
            row_dict = {}
            for v in result.vars:
                val = row.get(v)
                row_dict[str(v)] = str(val) if val is not None else None
            rows.append(row_dict)
        
        self.current_df = pd.DataFrame(rows, columns=columns)
        
        return {
            "row_count": len(self.current_df),
            "columns": columns,
            "sample_rows": self.current_df.head(10).to_dict(orient="records"),
        }
    
    def _tool_compute_correlation(self, args: dict) -> dict:
        """Compute correlation between two columns."""
        if self.current_df is None or self.current_df.empty:
            return {"error": "No data loaded. Run execute_sparql first."}
        
        x_col = args["x_col"]
        y_col = args["y_col"]
        method = args.get("method", "pearson")
        
        return compute_correlation(self.current_df, x_col, y_col, method)
    
    def _tool_compute_fold_change(self, args: dict) -> dict:
        """Compute fold change between groups."""
        if self.current_df is None or self.current_df.empty:
            return {"error": "No data loaded. Run execute_sparql first."}
        
        return compute_fold_change(
            self.current_df,
            args["group_col"],
            args["value_col"],
            args["group1"],
            args["group2"],
        )
    
    def _tool_find_peak_conditions(self, args: dict) -> dict:
        """Find peak conditions."""
        if self.current_df is None or self.current_df.empty:
            return {"error": "No data loaded. Run execute_sparql first."}
        
        return find_peak_conditions(
            self.current_df,
            args["condition_cols"],
            args["metric_col"],
            args.get("method", "mean"),
            args.get("top_n", 5),
        )
    
    def _tool_filter_by_threshold(self, args: dict) -> dict:
        """Filter data by threshold."""
        if self.current_df is None or self.current_df.empty:
            return {"error": "No data loaded. Run execute_sparql first."}
        
        self.current_df = filter_by_threshold(
            self.current_df,
            args["col"],
            args["op"],
            args["value"],
        )
        
        return {
            "remaining_rows": len(self.current_df),
            "sample_rows": self.current_df.head(5).to_dict(orient="records"),
        }
    
    def _tool_differential_expression(self, args: dict) -> dict:
        """Perform differential expression analysis."""
        if self.current_df is None or self.current_df.empty:
            return {"error": "No data loaded. Run execute_sparql first."}
        
        self.de_results = differential_expression(
            self.current_df,
            args["group_col"],
            args["group1"],
            args["group2"],
            gene_col=args.get("gene_col", "gene"),
            value_col=args.get("value_col", "expressionValue"),
            log2fc_threshold=args.get("log2fc_threshold", 1.0),
            pvalue_threshold=args.get("pvalue_threshold", 0.05),
            cell_line=args.get("cell_line"),
        )
        
        sig_genes = self.de_results[self.de_results["significant"] == True]
        
        return {
            "total_genes": len(self.de_results),
            "significant_genes": len(sig_genes),
            "upregulated": len(sig_genes[sig_genes["direction"] == "up"]),
            "downregulated": len(sig_genes[sig_genes["direction"] == "down"]),
            "top_genes": self.de_results.head(10).to_dict(orient="records"),
        }
    
    def _tool_get_pathway_enrichment(self, args: dict) -> dict:
        """Get pathway enrichment for a gene list."""
        gene_list = args["gene_list"]
        database = args.get("database", "kegg")
        organism = args.get("organism", "hsa")
        pvalue = args.get("pvalue_threshold", 0.05)
        
        return get_pathway_enrichment(gene_list, database, organism, pvalue)
    
    def _tool_summarize_by_group(self, args: dict) -> dict:
        """Summarize data by group."""
        if self.current_df is None or self.current_df.empty:
            return {"error": "No data loaded. Run execute_sparql first."}
        
        summary = summarize_by_group(
            self.current_df,
            args["group_col"],
            args["value_col"],
        )
        
        return {
            "groups": len(summary),
            "summary": summary.to_dict(orient="records"),
        }
    
    def _tool_get_significant_genes(self, args: dict) -> dict:
        """Get significant genes from DE results."""
        if self.de_results is None or self.de_results.empty:
            return {"error": "No DE results. Run differential_expression first."}
        
        direction = args.get("direction", "both")
        
        sig = self.de_results[self.de_results["significant"] == True]
        
        if direction == "up":
            sig = sig[sig["direction"] == "up"]
        elif direction == "down":
            sig = sig[sig["direction"] == "down"]
        
        gene_list = sig["gene"].tolist()
        
        return {
            "gene_count": len(gene_list),
            "genes": gene_list,
        }


def execute_tool(
    graph: Graph,
    tool_name: str,
    arguments: dict,
    executor: Optional[ToolExecutor] = None,
) -> tuple[dict, ToolExecutor]:
    """Execute a tool and return results.
    
    This is a convenience function that manages ToolExecutor state.
    
    Args:
        graph: RDF graph
        tool_name: Tool to execute
        arguments: Tool arguments
        executor: Optional existing executor (for maintaining state)
        
    Returns:
        Tuple of (result_dict, executor)
    """
    if executor is None:
        executor = ToolExecutor(graph)
    
    result = executor.execute(tool_name, arguments)
    return result, executor


def get_tool_by_name(name: str) -> Optional[dict]:
    """Get a tool definition by name."""
    for tool in TOOL_DEFINITIONS:
        if tool["name"] == name:
            return tool
    return None


__all__ = [
    "TOOL_DEFINITIONS",
    "ToolExecutor",
    "execute_tool",
    "get_tool_by_name",
]

