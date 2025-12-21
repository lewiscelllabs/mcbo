#!/usr/bin/env python3
"""
Compute statistics from the evaluation graph to verify sample/process counts.

Usage:
  python scripts/stats_eval_graph.py --graph .data/graph.ttl          # Real data
  python scripts/stats_eval_graph.py --graph data.sample/graph.ttl    # Demo data

Output:
  - Cell culture process count by type (Batch, Fed-batch, Perfusion, Unknown)
  - Bioprocess sample count
"""

import argparse
from pathlib import Path
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

MCBO = Namespace("http://example.org/mcbo#")
BFO = Namespace("http://purl.obolibrary.org/obo/BFO_")


def count_processes(g: Graph) -> dict:
    """Count cell culture process instances by type."""
    counts = {}
    
    # Query for all process instances
    query = """
    PREFIX mcbo: <http://example.org/mcbo#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT ?process ?type ?typeLabel
    WHERE {
      ?process rdf:type ?type .
      ?type rdfs:subClassOf* mcbo:CellCultureProcess .
      OPTIONAL { ?type rdfs:label ?typeLabel }
    }
    """
    
    results = g.query(query)
    total = 0
    by_type = {}
    
    for row in results:
        total += 1
        type_uri = str(row.type)
        type_label = str(row.typeLabel) if row.typeLabel else type_uri.split("#")[-1]
        by_type[type_label] = by_type.get(type_label, 0) + 1
    
    counts["total"] = total
    counts["by_type"] = by_type
    return counts


def count_samples(g: Graph) -> int:
    """Count bioprocess sample instances."""
    query = """
    PREFIX mcbo: <http://example.org/mcbo#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    
    SELECT (COUNT(?sample) AS ?count)
    WHERE {
      ?sample rdf:type mcbo:BioprocessSample .
    }
    """
    
    results = g.query(query)
    for row in results:
        # Access the first (and only) binding
        return int(row[0])
    return 0


def main():
    ap = argparse.ArgumentParser(description="Compute statistics from evaluation graph")
    ap.add_argument("--graph", type=str, required=True, help="Path to evaluation graph TTL file")
    args = ap.parse_args()
    
    graph_path = Path(args.graph)
    if not graph_path.exists():
        print(f"Error: Graph file not found: {graph_path}")
        return 1
    
    g = Graph()
    g.parse(str(graph_path), format="turtle")
    
    print(f"Statistics for: {graph_path}")
    print("=" * 60)
    
    # Count processes
    process_counts = count_processes(g)
    print(f"\nCell Culture Process Instances: {process_counts['total']}")
    if process_counts['by_type']:
        print("  Breakdown by type:")
        for ptype, count in sorted(process_counts['by_type'].items()):
            print(f"    {ptype}: {count}")
    
    # Count samples
    sample_count = count_samples(g)
    print(f"\nBioprocess Sample Instances: {sample_count}")
    
    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())

