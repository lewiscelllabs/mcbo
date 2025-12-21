#!/usr/bin/env python3
"""
Run MCBO competency question evaluation queries.

Usage (after pip install -e python/):
  mcbo-run-eval --graph data.sample/graph.ttl --queries eval/queries --results data.sample/results
  mcbo-run-eval --graph data.sample/graph.ttl --verify

Or run directly:
  python -m mcbo.run_eval --graph data.sample/graph.ttl --verify
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Tuple

from rdflib import Graph
from rdflib.query import Result

from .graph_utils import load_graphs, ensure_dir, ensure_parent_dir


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
    ap = argparse.ArgumentParser(description="Run MCBO competency question evaluation queries")
    ap.add_argument("--graph", type=str, default=None,
                    help="Path to a single TTL file containing the merged evaluation graph (ontology + instances).")
    ap.add_argument("--ontology", type=str, default=None,
                    help="Path to ontology TTL (TBox), e.g., ontology/mcbo.owl.ttl")
    ap.add_argument("--instances", type=str, default=None,
                    help="Path to instances TTL (ABox), e.g., data/processed/mcbo_instances.ttl")
    ap.add_argument("--queries", type=str, default="eval/queries",
                    help="Directory containing *.rq files (default: eval/queries)")
    ap.add_argument("--results", type=str, default="eval/results",
                    help="Directory to write *.tsv outputs (default: eval/results)")
    ap.add_argument("--write-merged", type=str, default=None,
                    help="If set, write the loaded merged graph to this TTL path.")
    ap.add_argument("--fail-on-empty", action="store_true",
                    help="Exit non-zero if any query returns 0 rows.")
    ap.add_argument("--verify", action="store_true",
                    help="Only verify graph parses; report triple count and exit (no queries run).")
    args = ap.parse_args()

    query_dir = Path(args.queries)
    results_dir = Path(args.results)
    ensure_dir(results_dir)

    # Load graph
    ontology_path = Path("ontology/mcbo.owl.ttl")
    try:
        if args.graph:
            graph_paths = [Path(args.graph)]
            # If ontology exists and graph is not the ontology itself, load it too
            if ontology_path.exists() and str(ontology_path) != args.graph:
                graph_paths.insert(0, ontology_path)
            g = load_graphs(graph_paths)
            source_desc = f"graph={args.graph}" + (f" + ontology" if len(graph_paths) > 1 else "")
        else:
            if not args.ontology or not args.instances:
                raise SystemExit("Provide either --graph OR both --ontology and --instances.")
            g = load_graphs([Path(args.ontology), Path(args.instances)])
            source_desc = f"ontology={args.ontology}, instances={args.instances}"
    except Exception as e:
        if args.verify:
            print(f"FAIL: Graph parsing failed - {e}")
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
    any_empty = False
    summary_lines = []
    for qfile in iter_query_files(query_dir):
        qtext = qfile.read_text(encoding="utf-8")
        res = run_query(g, qtext)
        tsv, nrows = result_to_tsv(res)

        out_tsv = results_dir / (qfile.stem + ".tsv")
        out_tsv.write_text(tsv, encoding="utf-8")

        summary_lines.append(f"{qfile.name}\t{nrows}\t->\t{out_tsv}")
        if nrows == 0:
            any_empty = True

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

