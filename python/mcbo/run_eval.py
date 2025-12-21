#!/usr/bin/env python3
"""
Run MCBO competency question evaluation queries.

Usage (after pip install -e python/):
  mcbo-run-eval --graph data.sample/graph.ttl --queries eval/queries --results data.sample/results
  mcbo-run-eval --graph data.sample/graph.ttl --verify
  mcbo-run-eval --data-dir data.sample --verify

Or run directly:
  python -m mcbo.run_eval --graph data.sample/graph.ttl --verify
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Iterable, Tuple

from rdflib import Graph
from rdflib.query import Result

from .graph_utils import load_graphs, ensure_dir, ensure_parent_dir


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


# Configuration by convention defaults
DEFAULT_PATHS = {
    "graph": "graph.ttl",
    "instances": "mcbo-instances.ttl",
    "ontology": "ontology/mcbo.owl.ttl",
    "results": "results",
}


def resolve_data_dir_path(data_dir: Path, key: str) -> Path:
    """Resolve a path relative to data_dir using convention defaults."""
    return data_dir / DEFAULT_PATHS[key]


def iter_query_files(query_dir: Path) -> Iterable[Path]:
    """Iterate over SPARQL query files in a directory."""
    if not query_dir.exists():
        raise FileNotFoundError(f"Query directory not found: {query_dir}")
    for p in sorted(query_dir.glob("*.rq")):
        yield p


def result_to_tsv(res: Result) -> Tuple[str, int]:
    """Convert rdflib SPARQL Result to TSV string and return (tsv, row_count)."""
    vars_ = [str(v) for v in res.vars]
    lines = ["\t".join(vars_)]
    row_count = 0
    for row in res:
        row_count += 1
        cells = []
        for v in res.vars:
            val = row.get(v)
            cells.append("" if val is None else str(val))
        lines.append("\t".join(cells))
    return "\n".join(lines) + "\n", row_count


def run_query(g: Graph, query_text: str) -> Result:
    """Execute a SPARQL query on a graph."""
    return g.query(query_text)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run MCBO competency question evaluation queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run evaluation with explicit paths
  mcbo-run-eval --graph data.sample/graph.ttl --queries eval/queries --results data.sample/results

  # Use config-by-convention (auto-resolves paths from data directory)
  mcbo-run-eval --data-dir data.sample
  mcbo-run-eval --data-dir .data

  # Verify graph parses without running queries
  mcbo-run-eval --graph data.sample/graph.ttl --verify
  mcbo-run-eval --data-dir data.sample --verify

  # Use separate ontology and instances files
  mcbo-run-eval --ontology ontology/mcbo.owl.ttl --instances .data/mcbo-instances.ttl

  # Fail if any competency question returns 0 results
  mcbo-run-eval --data-dir data.sample --fail-on-empty

Convention: When using --data-dir, the tool looks for:
  <data-dir>/graph.ttl          - merged evaluation graph
  <data-dir>/mcbo-instances.ttl - instance data (ABox)
  <data-dir>/results/           - query results output directory
  eval/queries/                 - SPARQL query files (*.rq)
"""
    )
    ap.add_argument("--graph", type=str, default=None,
                    help="Path to a single TTL file containing the merged evaluation graph (ontology + instances).")
    ap.add_argument("--data-dir", type=str, default=None,
                    help="Data directory (uses config-by-convention for graph.ttl and results/)")
    ap.add_argument("--ontology", type=str, default=None,
                    help="Path to ontology TTL (TBox), e.g., ontology/mcbo.owl.ttl")
    ap.add_argument("--instances", type=str, default=None,
                    help="Path to instances TTL (ABox), e.g., data/mcbo-instances.ttl")
    ap.add_argument("--queries", type=str, default="eval/queries",
                    help="Directory containing *.rq files (default: eval/queries)")
    ap.add_argument("--results", type=str, default=None,
                    help="Directory to write *.tsv outputs (default: <data-dir>/results or eval/results)")
    ap.add_argument("--write-merged", type=str, default=None,
                    help="If set, write the loaded merged graph to this TTL path.")
    ap.add_argument("--fail-on-empty", action="store_true",
                    help="Exit non-zero if any query returns 0 rows.")
    ap.add_argument("--verify", action="store_true",
                    help="Only verify graph parses; report triple count and exit (no queries run).")
    args = ap.parse_args()

    # Resolve paths using config-by-convention if --data-dir provided
    data_dir = Path(args.data_dir) if args.data_dir else None
    
    if data_dir:
        graph_path = args.graph or str(resolve_data_dir_path(data_dir, "graph"))
        results_dir = Path(args.results) if args.results else resolve_data_dir_path(data_dir, "results")
    else:
        graph_path = args.graph
        results_dir = Path(args.results) if args.results else Path("eval/results")
    
    query_dir = Path(args.queries)
    ensure_dir(results_dir)

    # Load graph
    ontology_path = Path("ontology/mcbo.owl.ttl")
    print("Loading graph...", end="", flush=True)
    load_start = time.time()
    try:
        if graph_path:
            graph_paths = [Path(graph_path)]
            # If ontology exists and graph is not the ontology itself, load it too
            if ontology_path.exists() and str(ontology_path) != graph_path:
                graph_paths.insert(0, ontology_path)
            g = load_graphs(graph_paths)
            source_desc = f"graph={graph_path}" + (f" + ontology" if len(graph_paths) > 1 else "")
        else:
            if not args.ontology or not args.instances:
                raise SystemExit("Provide --graph, --data-dir, or both --ontology and --instances.")
            g = load_graphs([Path(args.ontology), Path(args.instances)])
            source_desc = f"ontology={args.ontology}, instances={args.instances}"
        load_time = time.time() - load_start
        print(f" loaded {len(g):,} triples in {format_duration(load_time)}")
    except Exception as e:
        if args.verify:
            print(f"\nFAIL: Graph parsing failed - {e}")
            raise SystemExit(1)
        raise

    # If --verify, just report triple count and exit
    if args.verify:
        triple_count = len(g)
        print(f"PASS: {triple_count} triples")
        return

    # Optionally write merged graph
    if args.write_merged:
        out_path = Path(args.write_merged)
        ensure_parent_dir(out_path)
        g.serialize(destination=str(out_path), format="turtle")

    # Run each query
    query_files = list(iter_query_files(query_dir))
    total_queries = len(query_files)
    print(f"Running {total_queries} competency queries...")
    
    any_empty = False
    summary_lines = []
    eval_start = time.time()
    
    for i, qfile in enumerate(query_files, 1):
        print(f"  [{i}/{total_queries}] {qfile.name}...", end="", flush=True)
        query_start = time.time()
        
        qtext = qfile.read_text(encoding="utf-8")
        res = run_query(g, qtext)
        tsv, nrows = result_to_tsv(res)

        out_tsv = results_dir / (qfile.stem + ".tsv")
        out_tsv.write_text(tsv, encoding="utf-8")
        
        query_time = time.time() - query_start
        status = "✓" if nrows > 0 else "⚠"
        print(f" {status} {nrows} rows ({format_duration(query_time)})")

        summary_lines.append(f"{qfile.name}\t{nrows}\t->\t{out_tsv}")
        if nrows == 0:
            any_empty = True
    
    total_time = time.time() - eval_start
    print(f"Completed {total_queries} queries in {format_duration(total_time)}")

    # Write a simple run summary
    summary_path = results_dir / "SUMMARY.txt"
    summary_path.write_text(
        "MCBO CQ evaluation run\n"
        f"Source: {source_desc}\n\n"
        + "\n".join(summary_lines)
        + "\n",
        encoding="utf-8",
    )

    if args.fail_on_empty and any_empty:
        raise SystemExit("One or more queries returned 0 rows (fail-on-empty enabled).")


if __name__ == "__main__":
    main()

