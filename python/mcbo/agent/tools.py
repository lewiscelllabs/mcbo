"""
Tool definitions for MCBO agent.

Defines the tool schemas that are exposed to the LLM orchestrator,
and provides the execute_tool function to dispatch tool calls.
"""

from pathlib import Path
from typing import Any, Callable, Optional
import json

import pandas as pd
from rdflib import Graph

from .sparql_templates import format_template, list_templates, PREFIXES
from .sql_templates import (
    format_template as format_sql_template,
    list_templates as list_sql_templates,
)
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
                "template_args": {
                    "type": "object",
                    "description": "Extra placeholders required by some templates. "
                                   "Example: {\"product_class\": \"AntibodyProduct\"} "
                                   "for the cell_lines_by_product_class template.",
                    "additionalProperties": True,
                },
            },
        },
    },
    {
        "name": "execute_sql",
        "description": "Execute a DuckDB SQL query against the local mcbo.duckdb database "
                       "(built by `mcbo-build-duckdb`) and return results as a table. "
                       "Use template_name for the canonical CQ queries (same key as the "
                       "SPARQL templates), or raw_query for arbitrary SQL. The agent should "
                       "prefer execute_sql when the question is row/aggregate analytics over "
                       "the sample/expression tables, and execute_sparql when the question "
                       "needs ontology semantics (class hierarchies, relations). "
                       f"Available templates: {', '.join(list_sql_templates())}. "
                       "Tables: samples, expression_long(study_id, sample_id, gene_symbol, value), "
                       "gene_annotations (optional), samples_with_expression (view). "
                       "ALSO: any dataframe stashed by a previous generate_plot call via "
                       "save_df(name, df) is available as a virtual table of the same name "
                       "(e.g. SELECT * FROM pca_cho_top200 WHERE PC1 < 0). The result envelope "
                       "includes 'available_saved_dfs' so you can see what's queryable.",
        "input_schema": {
            "type": "object",
            "properties": {
                "template_name": {
                    "type": "string",
                    "description": "Name of a predefined SQL template to use.",
                },
                "raw_query": {
                    "type": "string",
                    "description": "Raw DuckDB SQL (used if template_name not provided).",
                },
                "filter_clause": {
                    "type": "string",
                    "description": "Optional WHERE predicate to AND into the template "
                                   "(e.g. \"CellLine = 'CHO-K1'\"). Do not include the "
                                   "'AND' keyword; it is added automatically.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional LIMIT to add to the template result set.",
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
        "name": "generate_plot",
        "description": "Render a matplotlib/seaborn PNG in a sandbox. Use ONLY when the user "
                       "explicitly asks for a chart, plot, or visualization. "
                       "The code has access to: "
                       "run_sql(sql)->DataFrame (DuckDB), run_sparql(query)->DataFrame, "
                       "save_df(name, df) to persist intermediates for follow-up SQL, "
                       "list_saved_dfs() to inventory them, "
                       "the current dataframe as 'df', "
                       "the dict 'saved_dfs' (read-only snapshot), "
                       "and pd, np, plt, sns, sklearn. "
                       "The code MUST end with plt.savefig(buf, format='png', dpi=100, "
                       "bbox_inches='tight'). Max figure size 7x6 inches. "
                       "IMPORTANT: run_sql and run_sparql refuse queries returning more than "
                       "200,000 rows -- pre-filter or aggregate. For expression PCA / heatmaps, "
                       "FIRST compute per-gene variance with a small aggregate query "
                       "(SELECT gene_symbol, VAR_POP(value) ...), take the top N genes, "
                       "then fetch only those gene_symbols joined to the slice's samples. "
                       "BEST PRACTICE: when you compute interesting intermediates (PCA coords, "
                       "cluster assignments, gene rankings, normalized matrices), CALL "
                       "save_df('snake_case_name', df) before drawing so the user's likely "
                       "follow-up questions can query those results directly via execute_sql.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code that draws and saves the plot."},
                "title": {"type": "string"},
            },
            "required": ["code", "title"],
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
    """Executes tools in the context of a graph and working dataframe.

    Holds optional handles to:
      - an rdflib Graph (used by execute_sparql)
      - a DuckDB database file (used by execute_sql)

    Both can coexist; the agent picks which tool to call. The DuckDB
    connection is opened lazily (read-only) on first use of execute_sql.
    """

    # Max number of cross-tool saved DataFrames before LRU eviction.
    NAMED_DF_CAP = 50

    def __init__(
        self,
        graph: Optional[Graph] = None,
        duckdb_path: Optional[Path] = None,
    ):
        """Initialize the executor.

        Args:
            graph: rdflib Graph containing MCBO data (enables execute_sparql).
            duckdb_path: Path to an mcbo.duckdb file produced by
                ``mcbo-build-duckdb`` (enables execute_sql).
        """
        from collections import OrderedDict

        self.graph = graph
        self._duckdb_path = Path(duckdb_path) if duckdb_path else None
        self._duckdb_con = None
        self.current_df: Optional[pd.DataFrame] = None
        self.de_results: Optional[pd.DataFrame] = None  # Store DE results
        self.images: list[str] = []  # base64 PNGs produced by generate_plot
        # Named, cross-tool dataframes (LRU). Plot code stashes intermediates
        # here via ``save_df(name, df)``; subsequent execute_sql calls see
        # them as virtual tables, so the LLM can do follow-up SQL against
        # plot outputs without recomputing. Persists across turns within
        # this executor's lifetime (server-process scoped).
        self.named_dfs: "OrderedDict[str, pd.DataFrame]" = OrderedDict()

    def reset_state(self) -> None:
        """Clear per-conversation transient state. Keep handles to graph/duckdb.

        NOTE: ``named_dfs`` is intentionally NOT cleared here. It survives
        across turns so the LLM can run follow-up queries against saved
        plot intermediates ("which samples are in the upper-left cluster?").
        Use ``forget_saved_dfs()`` for an explicit wipe.
        """
        self.current_df = None
        self.de_results = None
        self.images = []

    # ---- named saved dataframes ------------------------------------------

    def save_named_df(self, name: str, df: "pd.DataFrame") -> None:
        """Stash a DataFrame under ``name`` so other tool calls can read it.

        Validates that ``name`` is a safe SQL identifier (letters / digits /
        underscore, starting with letter or underscore) so it can be used
        directly as a virtual table name in execute_sql.

        Enforces an LRU cap (``NAMED_DF_CAP``); oldest entry is evicted
        with a log line if exceeded.
        """
        import re
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(
                f"save_df: name {name!r} must be a valid SQL identifier "
                f"(letters/digits/underscore, starting with letter or underscore)."
            )
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"save_df: expected pandas DataFrame, got {type(df).__name__}"
            )
        if name in self.named_dfs:
            self.named_dfs.move_to_end(name)
        elif len(self.named_dfs) >= self.NAMED_DF_CAP:
            evicted, _ = self.named_dfs.popitem(last=False)
            print(
                f"[mcbo.tool] save_df: evicted '{evicted}' "
                f"(LRU cap {self.NAMED_DF_CAP})",
                flush=True,
            )
        self.named_dfs[name] = df.copy()
        print(
            f"[mcbo.tool] save_df('{name}') -> {len(df)} rows, "
            f"cols={list(df.columns)[:8]}",
            flush=True,
        )

    def list_named_dfs(self) -> dict:
        """Return ``{name: {rows, columns}}`` for every currently saved df."""
        return {
            name: {"rows": int(len(df)), "columns": [str(c) for c in df.columns]}
            for name, df in self.named_dfs.items()
        }

    def forget_named_dfs(self, names: Optional[list] = None) -> int:
        """Drop saved dfs (all, or by name list). Returns count removed."""
        if names is None:
            n = len(self.named_dfs)
            self.named_dfs.clear()
            return n
        n = 0
        for name in names:
            if name in self.named_dfs:
                del self.named_dfs[name]
                n += 1
        return n

    @property
    def duckdb_con(self):
        """Lazy read-only DuckDB connection."""
        if self._duckdb_con is None:
            if self._duckdb_path is None:
                raise RuntimeError(
                    "No DuckDB path configured. Pass --duckdb to the CLI or build "
                    "the DB with: mcbo-build-duckdb --data-dir <dir>"
                )
            if not self._duckdb_path.exists():
                raise FileNotFoundError(
                    f"DuckDB file not found: {self._duckdb_path}. "
                    f"Build it with: mcbo-build-duckdb --data-dir <dir>"
                )
            try:
                import duckdb
            except ImportError as e:
                raise ImportError(
                    "duckdb is required for execute_sql. "
                    "Install with: pip install -e 'python/[duckdb]'"
                ) from e
            self._duckdb_con = duckdb.connect(str(self._duckdb_path), read_only=True)
        return self._duckdb_con

    def close(self) -> None:
        if self._duckdb_con is not None:
            try:
                self._duckdb_con.close()
            finally:
                self._duckdb_con = None
    
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

        # One-line summary of every tool call so a demo'er can see exactly
        # which template / query the agent decided to run. Routed through
        # print() so it shows up in the FastAPI / uvicorn stdout.
        try:
            _summary = self._tool_call_summary(tool_name, arguments)
            print(f"[mcbo.tool] {_summary}", flush=True)
        except Exception:
            pass

        try:
            result = getattr(self, method_name)(arguments)
        except Exception as e:
            print(f"[mcbo.tool] -> EXCEPTION {type(e).__name__}: {e}", flush=True)
            return {"error": str(e)}

        # Brief result summary (row count / error / image count). Keeps the
        # log readable without dumping full rows.
        try:
            if isinstance(result, dict):
                if "error" in result:
                    print(f"[mcbo.tool] -> error: {result['error']}", flush=True)
                elif "row_count" in result:
                    print(
                        f"[mcbo.tool] -> {result['row_count']} rows, "
                        f"cols={result.get('columns')}",
                        flush=True,
                    )
                elif "image" in result or "images" in result:
                    n = len(result.get("images", [])) or (1 if result.get("image") else 0)
                    print(f"[mcbo.tool] -> plot ({n} image{'s' if n != 1 else ''})", flush=True)
                else:
                    keys = list(result.keys())[:5]
                    print(f"[mcbo.tool] -> ok, keys={keys}", flush=True)
        except Exception:
            pass
        return result

    @staticmethod
    def _tool_call_summary(name: str, args: dict) -> str:
        """Compact one-line description of a tool call for logging."""
        if name == "execute_sparql":
            tn = args.get("template_name")
            if tn:
                ta = args.get("template_args") or {}
                fc = args.get("filter_clause") or ""
                parts = [f"template={tn}"]
                if ta: parts.append(f"template_args={ta}")
                if fc: parts.append(f"filter={fc!r}")
                return f"execute_sparql({', '.join(parts)})"
            rq = (args.get("raw_query") or "").strip().replace("\n", " ")
            return f"execute_sparql(raw_query={rq[:240]!r})"
        if name == "execute_sql":
            tn = args.get("template_name")
            if tn:
                fc = args.get("filter_clause") or ""
                lim = args.get("limit")
                parts = [f"template={tn}"]
                if fc: parts.append(f"filter={fc!r}")
                if lim is not None: parts.append(f"limit={lim}")
                return f"execute_sql({', '.join(parts)})"
            rq = (args.get("raw_query") or "").strip().replace("\n", " ")
            return f"execute_sql(raw_query={rq[:240]!r})"
        if name == "generate_plot":
            code = (args.get("code") or "").strip().replace("\n", " ")
            return f"generate_plot(code={code[:160]!r}...)"
        # generic fallback
        return f"{name}({', '.join(f'{k}={v!r}' for k, v in list(args.items())[:3])})"
    
    def _tool_execute_sparql(self, args: dict) -> dict:
        """Execute a SPARQL query."""
        template_name = args.get("template_name")
        raw_query = args.get("raw_query")
        filter_clause = args.get("filter_clause", "")
        # template_args lets the agent pass extra placeholders that some
        # templates require (e.g., product_class for cell_lines_by_product_class).
        template_args = args.get("template_args") or {}

        if template_name:
            try:
                query = format_template(
                    template_name, filter_clause=filter_clause, **template_args
                )
            except KeyError as e:
                return {
                    "error": (
                        f"template '{template_name}' is missing required placeholder {e}. "
                        f"Pass it via template_args={{...}}."
                    )
                }
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
    
    def _tool_execute_sql(self, args: dict) -> dict:
        """Execute a DuckDB SQL query."""
        template_name = args.get("template_name")
        raw_query = args.get("raw_query")
        filter_clause = args.get("filter_clause", "") or ""
        limit = args.get("limit")

        if template_name:
            query = format_sql_template(
                template_name, filter_clause=filter_clause, limit=limit
            )
        elif raw_query:
            query = raw_query
        else:
            return {"error": "Provide either template_name or raw_query"}

        # Register saved cross-tool dataframes as virtual tables so the LLM
        # can do follow-ups against plot intermediates with plain SQL
        # (e.g. SELECT * FROM pca_cho_top200 WHERE PC1 < 0).
        registered: list[str] = []
        for name, ndf in list(self.named_dfs.items()):
            try:
                self.duckdb_con.register(name, ndf)
                registered.append(name)
            except Exception as e:
                print(
                    f"[mcbo.tool] could not register saved df '{name}': {e}",
                    flush=True,
                )
        try:
            df = self.duckdb_con.execute(query).fetchdf()
        finally:
            for name in registered:
                try:
                    self.duckdb_con.unregister(name)
                except Exception:
                    pass

        self.current_df = df
        result = {
            "row_count": int(len(df)),
            "columns": [str(c) for c in df.columns],
            "sample_rows": df.head(10).to_dict(orient="records"),
        }
        if registered:
            result["available_saved_dfs"] = registered
        return result

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
    
    def _tool_generate_plot(self, args: dict) -> dict:
        """Render a matplotlib/seaborn PNG in a sandbox.

        Captures the resulting base64 image on ``self.images`` so the calling
        layer (e.g. the Alchemist Desktop adapter) can surface it to the UI.
        Returns a lightweight ``{ok, title, image_returned}`` to the model so
        the base64 payload doesn't pollute the chat context.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import seaborn as sns
            import numpy as np
            import pandas as _pd
        except ImportError as e:
            return {"error": f"plotting libraries not installed ({e}). "
                             "Install matplotlib + seaborn to enable generate_plot."}
        try:
            import sklearn  # exposed to user code (PCA, clustering, etc.)
        except ImportError:
            sklearn = None  # type: ignore[assignment]

        import base64
        import io as _io

        code = args.get("code", "")
        title = args.get("title", "")
        if not code.strip():
            return {"error": "Missing required argument: code"}

        plt.close("all")
        buf = _io.BytesIO()

        duckdb_path = self._duckdb_path
        graph = self.graph
        # Soft row cap protects the server from OOM when the plot code
        # accidentally fetches a full multi-million-row expression table.
        # Override via MCBO_PLOT_ROW_CAP env var.
        import os as _os
        row_cap = int(_os.environ.get("MCBO_PLOT_ROW_CAP", "200000"))

        def _check_count(n: int, what: str, sql_for_error: str):
            if n > row_cap:
                raise RuntimeError(
                    f"{what} would return {n:,} rows, exceeding the plot "
                    f"sandbox cap of {row_cap:,}. Add a LIMIT or pre-filter "
                    f"your query (e.g. join through samples and filter by "
                    f"CellLine / ProcessType / variance-rank), then re-run. "
                    f"Query: {sql_for_error[:200]}..."
                )

        def run_sql(sql: str):
            if duckdb_path is None:
                raise RuntimeError("No DuckDB configured for this executor.")
            import duckdb
            con = duckdb.connect(str(duckdb_path), read_only=True)
            try:
                # Cheap COUNT(*) gate via a subquery so we can refuse oversized
                # fetches before materializing them.
                try:
                    n = con.execute(
                        f"SELECT COUNT(*) FROM ({sql.rstrip(';')}) _alch_cap"
                    ).fetchone()[0]
                    _check_count(int(n), "run_sql", sql)
                except RuntimeError:
                    raise
                except Exception:
                    # COUNT(*) wrapper failed (e.g., the query was DDL); fall
                    # through and let the real exec surface the error.
                    pass
                return con.execute(sql).fetchdf()
            finally:
                con.close()

        def run_sparql(query: str):
            if graph is None:
                raise RuntimeError("No RDF graph configured for this executor.")
            res = graph.query(query)
            cols = [str(v) for v in res.vars]
            rows = [[str(r.get(v)) if r.get(v) is not None else None for v in res.vars] for r in res]
            _check_count(len(rows), "run_sparql", query)
            return _pd.DataFrame(rows, columns=cols)

        # Cross-tool persistence: closures over self so plot code can stash
        # intermediates (PCA coords, cluster labels, gene rankings, ...) that
        # subsequent tool calls -- especially execute_sql -- can read by
        # name. See ToolExecutor.save_named_df for naming rules.
        _executor = self

        def save_df(name, frame):
            """Persist a DataFrame under `name` for follow-up queries.
            Other tools can then do SELECT * FROM <name> in execute_sql."""
            _executor.save_named_df(name, frame)

        def list_saved_dfs():
            """Inventory of currently persisted dataframes."""
            return _executor.list_named_dfs()

        ns: dict = {
            "run_sql": run_sql,
            "run_sparql": run_sparql,
            "save_df": save_df,
            "list_saved_dfs": list_saved_dfs,
            "pd": _pd, "np": np, "plt": plt, "sns": sns,
            "sklearn": sklearn,
            "buf": buf, "title": title,
            "df": self.current_df,
            "saved_dfs": dict(self.named_dfs),  # snapshot read-only view
        }
        try:
            plt.figure(figsize=(7, 6))
            exec(code, ns)
            if buf.tell() == 0:
                plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        finally:
            plt.close("all")

        data = buf.getvalue()
        if not data:
            return {"error": "Plot code did not produce a PNG."}
        self.images.append(base64.b64encode(data).decode("ascii"))
        return {"ok": True, "title": title, "image_returned": True}

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
    graph: Optional[Graph],
    tool_name: str,
    arguments: dict,
    executor: Optional[ToolExecutor] = None,
    duckdb_path: Optional[Path] = None,
) -> tuple[dict, ToolExecutor]:
    """Execute a tool and return results.

    Convenience function that manages ToolExecutor state across calls.

    Args:
        graph: RDF graph (may be None if only SQL is needed).
        tool_name: Tool to execute.
        arguments: Tool arguments.
        executor: Optional existing executor (for maintaining state).
        duckdb_path: Optional DuckDB path (used when creating a new executor).

    Returns:
        Tuple of (result_dict, executor)
    """
    if executor is None:
        executor = ToolExecutor(graph=graph, duckdb_path=duckdb_path)

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

