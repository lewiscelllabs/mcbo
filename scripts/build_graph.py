#!/usr/bin/env python3
"""
build_graph.py — Build MCBO evaluation graph from multiple studies.

This script supports two workflows:

1. INCREMENTAL: Add studies one at a time
   python scripts/build_graph.py add-study \
     --study-dir .data/studies/study_001 \
     --instances .data/processed/mcbo_instances.ttl

2. FULL BUILD: Combine all studies into final graph
   python scripts/build_graph.py build \
     --studies-dir .data/studies \
     --ontology ontology/mcbo.owl.ttl \
     --output .data/graph.ttl

Expected study directory structure:
  .data/studies/           # Real data (git-ignored)
    study_001/
      sample_metadata.csv
      expression_matrix.csv  (optional)
    ...
  
  data.sample/studies/     # Demo data (checked in)
    study_demo_001/
      sample_metadata.csv
      expression_matrix.csv  (optional)
    ...

The script will:
  - Process each study's metadata + expression matrix
  - Merge all studies into mcbo_instances.ttl
  - Combine with ontology into <data-dir>/graph.ttl
"""

import argparse
import sys
from pathlib import Path

# Add src to path for csv_to_rdf import
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rdflib import Graph, Namespace
from csv_to_rdf import convert_csv_to_rdf, load_expression_matrix, add_expression_data, iri_safe
import pandas as pd

MCBO = Namespace("http://example.org/mcbo#")


def find_study_files(study_dir: Path) -> tuple:
    """Find metadata and expression files in a study directory."""
    metadata_file = None
    expr_file = None
    
    # Look for metadata file
    for name in ["sample_metadata.csv", "metadata.csv", "samples.csv"]:
        f = study_dir / name
        if f.exists():
            metadata_file = f
            break
    
    # Look for expression matrix
    for name in ["expression_matrix.csv", "expression.csv", "counts.csv", "tpm.csv"]:
        f = study_dir / name
        if f.exists():
            expr_file = f
            break
    
    return metadata_file, expr_file


def process_study(study_dir: Path, created_genes: set = None) -> Graph:
    """Process a single study directory and return its RDF graph."""
    if created_genes is None:
        created_genes = set()
    
    metadata_file, expr_file = find_study_files(study_dir)
    
    if metadata_file is None:
        print(f"  WARNING: No metadata file found in {study_dir}, skipping")
        return Graph()
    
    print(f"  Processing: {metadata_file.name}")
    
    # Create temp output for this study
    temp_output = Path("/tmp") / f"mcbo_study_{study_dir.name}.ttl"
    
    # Convert CSV to RDF
    g = convert_csv_to_rdf(str(metadata_file), str(temp_output))
    
    # Add expression data if available
    if expr_file:
        print(f"    + Expression matrix: {expr_file.name}")
        expr_data = load_expression_matrix(str(expr_file))
        df = pd.read_csv(metadata_file)
        for _, row in df.iterrows():
            sample_id = str(row.get("SampleAccession", "")).strip()
            if sample_id and sample_id in expr_data:
                sample_uri = MCBO[f"sample_{iri_safe(sample_id)}"]
                add_expression_data(g, sample_uri, sample_id, expr_data, created_genes)
    
    return g


def add_study(study_dir: Path, instances_file: Path):
    """Add a single study to the existing instances file."""
    print(f"\n=== Adding study: {study_dir.name} ===")
    
    # Load existing instances if file exists
    main_graph = Graph()
    main_graph.bind("mcbo", MCBO)
    
    if instances_file.exists():
        print(f"Loading existing instances from: {instances_file}")
        main_graph.parse(str(instances_file), format="turtle")
        print(f"  Existing triples: {len(main_graph)}")
    
    # Process the new study
    created_genes = set()  # Track genes across the merge
    study_graph = process_study(study_dir, created_genes)
    
    # Merge
    initial_count = len(main_graph)
    for triple in study_graph:
        main_graph.add(triple)
    
    print(f"  Added triples: {len(main_graph) - initial_count}")
    print(f"  Total triples: {len(main_graph)}")
    
    # Save
    main_graph.serialize(destination=str(instances_file), format="turtle")
    print(f"  Saved to: {instances_file}")


def build_full_graph(studies_dir: Path, ontology_file: Path, instances_file: Path, output_file: Path):
    """Build complete graph from all studies + ontology."""
    print(f"\n=== Building full graph ===")
    print(f"Studies directory: {studies_dir}")
    print(f"Ontology: {ontology_file}")
    
    # Find all study directories
    study_dirs = sorted([d for d in studies_dir.iterdir() if d.is_dir()])
    print(f"Found {len(study_dirs)} study directories")
    
    # Process all studies
    main_graph = Graph()
    main_graph.bind("mcbo", MCBO)
    created_genes = set()
    
    for study_dir in study_dirs:
        print(f"\nProcessing study: {study_dir.name}")
        study_graph = process_study(study_dir, created_genes)
        for triple in study_graph:
            main_graph.add(triple)
    
    print(f"\n  Total instance triples: {len(main_graph)}")
    
    # Save instances
    instances_file.parent.mkdir(parents=True, exist_ok=True)
    main_graph.serialize(destination=str(instances_file), format="turtle")
    print(f"  Saved instances to: {instances_file}")
    
    # Load ontology and merge
    print(f"\nMerging with ontology...")
    main_graph.parse(str(ontology_file), format="turtle")
    print(f"  Total triples (ontology + instances): {len(main_graph)}")
    
    # Save final graph
    output_file.parent.mkdir(parents=True, exist_ok=True)
    main_graph.serialize(destination=str(output_file), format="turtle")
    print(f"  Saved full graph to: {output_file}")


def merge_ontology_instances(ontology_file: Path, instances_file: Path, output_file: Path):
    """Simple merge: ontology + instances -> graph.ttl"""
    print(f"\n=== Merging ontology + instances ===")
    
    g = Graph()
    g.bind("mcbo", MCBO)
    
    print(f"Loading ontology: {ontology_file}")
    g.parse(str(ontology_file), format="turtle")
    onto_count = len(g)
    print(f"  Ontology triples: {onto_count}")
    
    print(f"Loading instances: {instances_file}")
    g.parse(str(instances_file), format="turtle")
    print(f"  Instance triples: {len(g) - onto_count}")
    print(f"  Total triples: {len(g)}")
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(output_file), format="turtle")
    print(f"  Saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Build MCBO evaluation graph from multiple studies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add a single study to existing instances
  python scripts/build_graph.py add-study \\
    --study-dir .data/studies/my_study \\
    --instances .data/processed/mcbo_instances.ttl

  # Build full graph from all studies
  python scripts/build_graph.py build \\
    --studies-dir .data/studies \\
    --ontology ontology/mcbo.owl.ttl \\
    --instances .data/processed/mcbo_instances.ttl \\
    --output .data/graph.ttl

  # Just merge ontology + instances (no study processing)
  python scripts/build_graph.py merge \\
    --ontology ontology/mcbo.owl.ttl \\
    --instances .data/processed/mcbo_instances.ttl \\
    --output .data/graph.ttl
  
  # Demo data example
  python scripts/build_graph.py build \\
    --studies-dir data.sample/studies \\
    --output data.sample/graph.ttl
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # add-study command
    add_parser = subparsers.add_parser("add-study", help="Add a single study to instances")
    add_parser.add_argument("--study-dir", type=Path, required=True, help="Study directory")
    add_parser.add_argument("--instances", type=Path, default=Path(".data/processed/mcbo_instances.ttl"),
                           help="Output instances file (will append if exists)")
    
    # build command
    build_parser = subparsers.add_parser("build", help="Build full graph from all studies")
    build_parser.add_argument("--studies-dir", type=Path, required=True, help="Directory containing study subdirs")
    build_parser.add_argument("--ontology", type=Path, default=Path("ontology/mcbo.owl.ttl"))
    build_parser.add_argument("--instances", type=Path, default=Path(".data/processed/mcbo_instances.ttl"))
    build_parser.add_argument("--output", type=Path, default=Path(".data/graph.ttl"))
    
    # merge command
    merge_parser = subparsers.add_parser("merge", help="Merge ontology + instances into graph.ttl")
    merge_parser.add_argument("--ontology", type=Path, default=Path("ontology/mcbo.owl.ttl"))
    merge_parser.add_argument("--instances", type=Path, default=Path(".data/processed/mcbo_instances.ttl"))
    merge_parser.add_argument("--output", type=Path, default=Path(".data/graph.ttl"))
    
    args = parser.parse_args()
    
    if args.command == "add-study":
        add_study(args.study_dir, args.instances)
    elif args.command == "build":
        build_full_graph(args.studies_dir, args.ontology, args.instances, args.output)
    elif args.command == "merge":
        merge_ontology_instances(args.ontology, args.instances, args.output)


if __name__ == "__main__":
    main()

