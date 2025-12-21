#!/usr/bin/env python3
"""
Build MCBO evaluation graph from multiple studies.

Usage (after pip install -e python/):
  mcbo-build-graph add-study --study-dir .data/studies/study_001 --instances .data/mcbo-instances.ttl
  mcbo-build-graph build --studies-dir data.sample/studies --output data.sample/graph.ttl
  mcbo-build-graph build --data-dir data.sample   # Config-by-convention

Or run directly:
  python -m mcbo.build_graph build --studies-dir data.sample/studies --output data.sample/graph.ttl

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

Config-by-convention with --data-dir:
  <data-dir>/
    graph.ttl               # Output: merged evaluation graph
    mcbo-instances.ttl      # Output: instance data (ABox)
    studies/                # Input: study directories
    expression/             # Input: per-study expression matrices (optional)
    sample_metadata.csv     # Input: single CSV for bootstrap (alternative to studies/)
    results/                # Output: evaluation results

The script will:
  - Process each study's metadata + expression matrix
  - Merge all studies into mcbo-instances.ttl
  - Combine with ontology into <data-dir>/graph.ttl
"""

import argparse
from pathlib import Path

import pandas as pd

from .namespaces import MCBO
from .graph_utils import iri_safe, create_graph, ensure_parent_dir
from .csv_to_rdf import convert_csv_to_rdf, load_expression_matrix, add_expression_data


# Configuration by convention defaults
DEFAULT_PATHS = {
    "graph": "graph.ttl",
    "instances": "mcbo-instances.ttl",
    "ontology": "ontology/mcbo.owl.ttl",
    "studies": "studies",
    "expression": "expression",
    "metadata": "sample_metadata.csv",
    "results": "results",
}


def resolve_data_dir_path(data_dir: Path, key: str) -> Path:
    """Resolve a path relative to data_dir using convention defaults."""
    return data_dir / DEFAULT_PATHS[key]


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


def process_study(study_dir: Path, created_genes: set = None):
    """Process a single study directory and return its RDF graph."""
    if created_genes is None:
        created_genes = set()
    
    metadata_file, expr_file = find_study_files(study_dir)
    
    if metadata_file is None:
        print(f"  WARNING: No metadata file found in {study_dir}, skipping")
        return create_graph()
    
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
    main_graph = create_graph()
    
    if instances_file.exists():
        print(f"Loading existing instances from: {instances_file}")
        main_graph.parse(str(instances_file), format="turtle")
        print(f"  Existing triples: {len(main_graph)}")
    
    # Process the new study
    created_genes = set()
    study_graph = process_study(study_dir, created_genes)
    
    # Merge
    initial_count = len(main_graph)
    for triple in study_graph:
        main_graph.add(triple)
    
    print(f"  Added triples: {len(main_graph) - initial_count}")
    print(f"  Total triples: {len(main_graph)}")
    
    # Save
    ensure_parent_dir(instances_file)
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
    main_graph = create_graph()
    created_genes = set()
    
    for study_dir in study_dirs:
        print(f"\nProcessing study: {study_dir.name}")
        study_graph = process_study(study_dir, created_genes)
        for triple in study_graph:
            main_graph.add(triple)
    
    print(f"\n  Total instance triples: {len(main_graph)}")
    
    # Save instances
    ensure_parent_dir(instances_file)
    main_graph.serialize(destination=str(instances_file), format="turtle")
    print(f"  Saved instances to: {instances_file}")
    
    # Load ontology and merge
    print(f"\nMerging with ontology...")
    main_graph.parse(str(ontology_file), format="turtle")
    print(f"  Total triples (ontology + instances): {len(main_graph)}")
    
    # Save final graph
    ensure_parent_dir(output_file)
    main_graph.serialize(destination=str(output_file), format="turtle")
    print(f"  Saved full graph to: {output_file}")


def merge_ontology_instances(ontology_file: Path, instances_file: Path, output_file: Path):
    """Simple merge: ontology + instances -> graph.ttl"""
    print(f"\n=== Merging ontology + instances ===")
    
    g = create_graph()
    
    print(f"Loading ontology: {ontology_file}")
    g.parse(str(ontology_file), format="turtle")
    onto_count = len(g)
    print(f"  Ontology triples: {onto_count}")
    
    print(f"Loading instances: {instances_file}")
    g.parse(str(instances_file), format="turtle")
    print(f"  Instance triples: {len(g) - onto_count}")
    print(f"  Total triples: {len(g)}")
    
    ensure_parent_dir(output_file)
    g.serialize(destination=str(output_file), format="turtle")
    print(f"  Saved to: {output_file}")


def bootstrap_from_csv(csv_file: Path, ontology_file: Path, output_file: Path, 
                       expression_matrix: Path = None, expression_dir: Path = None):
    """Bootstrap a graph from a single CSV file with optional expression data.
    
    This is the "single curated CSV" workflow where all study data is in one file,
    with optional per-study expression matrices in a directory.
    """
    from .csv_to_rdf import convert_csv_to_rdf, load_expression_matrix, load_expression_dir, add_expression_data
    
    print(f"\n=== Bootstrapping graph from single CSV ===")
    print(f"Metadata CSV: {csv_file}")
    
    # Create temporary instances file using standardized naming
    instances_file = output_file.parent / "mcbo-instances.ttl"
    ensure_parent_dir(instances_file)
    
    # Load expression data
    expr_data = {}
    if expression_matrix:
        print(f"Loading expression matrix: {expression_matrix}")
        expr_data = load_expression_matrix(str(expression_matrix))
        print(f"  Loaded expression data for {len(expr_data)} samples")
    elif expression_dir:
        expr_data = load_expression_dir(str(expression_dir))
    
    # Convert CSV to RDF
    g = convert_csv_to_rdf(str(csv_file), str(instances_file))
    
    # Add expression data if available
    if expr_data:
        df = pd.read_csv(csv_file)
        created_genes = set()
        matched_count = 0
        for _, row in df.iterrows():
            sample_id = str(row.get("SampleAccession", "")).strip()
            if sample_id and sample_id in expr_data:
                sample_uri = MCBO[f"sample_{iri_safe(sample_id)}"]
                add_expression_data(g, sample_uri, sample_id, expr_data, created_genes)
                matched_count += 1
        g.serialize(destination=str(instances_file), format="turtle")
        print(f"Added expression data for {matched_count} samples ({len(created_genes)} unique genes)")
    
    # Merge with ontology
    print(f"\nMerging with ontology: {ontology_file}")
    g.parse(str(ontology_file), format="turtle")
    print(f"  Total triples: {len(g)}")
    
    # Save final graph
    ensure_parent_dir(output_file)
    g.serialize(destination=str(output_file), format="turtle")
    print(f"  Saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Build MCBO evaluation graph from studies or single CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CONFIG-BY-CONVENTION: Auto-detect structure in data directory
  mcbo-build-graph build --data-dir data.sample    # Uses data.sample/studies/ or sample_metadata.csv
  mcbo-build-graph build --data-dir .data          # Real data

  # SCENARIO 1: Bootstrap from single curated CSV (no expression)
  mcbo-build-graph bootstrap --csv .data/sample_metadata.csv --output .data/graph.ttl

  # SCENARIO 4: Bootstrap from single CSV + per-study expression matrices
  mcbo-build-graph bootstrap \\
    --csv .data/sample_metadata.csv \\
    --expression-dir .data/expression/ \\
    --output .data/graph.ttl

  # SCENARIO 2 & 3: Build from multi-study directories (each with own CSV)
  mcbo-build-graph build --studies-dir .data/studies --output .data/graph.ttl

  # Add a single study incrementally (for large datasets)
  mcbo-build-graph add-study --study-dir .data/studies/my_study --instances .data/mcbo-instances.ttl

  # Merge existing instances with ontology
  mcbo-build-graph merge --instances .data/mcbo-instances.ttl --output .data/graph.ttl

Convention: When using --data-dir, the tool looks for:
  <data-dir>/graph.ttl               - output merged graph
  <data-dir>/mcbo-instances.ttl      - output instance data (ABox)
  <data-dir>/studies/                - input study directories
  <data-dir>/expression/             - input per-study expression matrices
  <data-dir>/sample_metadata.csv     - input single CSV (for bootstrap)
  ontology/mcbo.owl.ttl              - ontology (TBox)
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # bootstrap command (single CSV workflow)
    bootstrap_parser = subparsers.add_parser("bootstrap", 
        help="Bootstrap graph from single curated CSV (+ optional expression dir)")
    bootstrap_parser.add_argument("--csv", type=Path, default=None, 
                                  help="Single CSV file with all sample metadata")
    bootstrap_parser.add_argument("--data-dir", type=Path, default=None,
                                  help="Data directory (uses config-by-convention)")
    bootstrap_parser.add_argument("--ontology", type=Path, default=Path("ontology/mcbo.owl.ttl"))
    bootstrap_parser.add_argument("--output", type=Path, default=None)
    bootstrap_parser.add_argument("--expression-matrix", type=Path, default=None,
                                  help="Single expression matrix CSV")
    bootstrap_parser.add_argument("--expression-dir", type=Path, default=None,
                                  help="Directory of per-study expression matrices")
    
    # add-study command
    add_parser = subparsers.add_parser("add-study", help="Add a single study to instances")
    add_parser.add_argument("--study-dir", type=Path, required=True, help="Study directory")
    add_parser.add_argument("--data-dir", type=Path, default=None,
                           help="Data directory (uses config-by-convention for instances)")
    add_parser.add_argument("--instances", type=Path, default=None,
                           help="Output instances file (will append if exists)")
    
    # build command
    build_parser = subparsers.add_parser("build", help="Build full graph from study directories")
    build_parser.add_argument("--studies-dir", type=Path, default=None, 
                             help="Directory containing study subdirs")
    build_parser.add_argument("--data-dir", type=Path, default=None,
                             help="Data directory (uses config-by-convention)")
    build_parser.add_argument("--ontology", type=Path, default=Path("ontology/mcbo.owl.ttl"))
    build_parser.add_argument("--instances", type=Path, default=None)
    build_parser.add_argument("--output", type=Path, default=None)
    
    # merge command
    merge_parser = subparsers.add_parser("merge", help="Merge ontology + instances into graph.ttl")
    merge_parser.add_argument("--data-dir", type=Path, default=None,
                             help="Data directory (uses config-by-convention)")
    merge_parser.add_argument("--ontology", type=Path, default=Path("ontology/mcbo.owl.ttl"))
    merge_parser.add_argument("--instances", type=Path, default=None)
    merge_parser.add_argument("--output", type=Path, default=None)
    
    args = parser.parse_args()
    
    # Resolve paths using config-by-convention
    data_dir = getattr(args, 'data_dir', None)
    
    if args.command == "bootstrap":
        if args.expression_matrix and args.expression_dir:
            parser.error("Cannot specify both --expression-matrix and --expression-dir")
        
        # Resolve paths
        if data_dir:
            csv_file = args.csv or resolve_data_dir_path(data_dir, "metadata")
            output_file = args.output or resolve_data_dir_path(data_dir, "graph")
            expr_dir = args.expression_dir or (resolve_data_dir_path(data_dir, "expression") 
                        if resolve_data_dir_path(data_dir, "expression").exists() else None)
        else:
            if not args.csv:
                parser.error("bootstrap requires --csv or --data-dir")
            csv_file = args.csv
            output_file = args.output or Path(".data/graph.ttl")
            expr_dir = args.expression_dir
        
        bootstrap_from_csv(csv_file, args.ontology, output_file, 
                          args.expression_matrix, expr_dir)
    
    elif args.command == "add-study":
        if data_dir:
            instances_file = args.instances or resolve_data_dir_path(data_dir, "instances")
        else:
            instances_file = args.instances or Path(".data/mcbo-instances.ttl")
        add_study(args.study_dir, instances_file)
    
    elif args.command == "build":
        if data_dir:
            studies_dir = args.studies_dir or resolve_data_dir_path(data_dir, "studies")
            instances_file = args.instances or resolve_data_dir_path(data_dir, "instances")
            output_file = args.output or resolve_data_dir_path(data_dir, "graph")
        else:
            if not args.studies_dir:
                parser.error("build requires --studies-dir or --data-dir")
            studies_dir = args.studies_dir
            instances_file = args.instances or Path(".data/mcbo-instances.ttl")
            output_file = args.output or Path(".data/graph.ttl")
        build_full_graph(studies_dir, args.ontology, instances_file, output_file)
    
    elif args.command == "merge":
        if data_dir:
            instances_file = args.instances or resolve_data_dir_path(data_dir, "instances")
            output_file = args.output or resolve_data_dir_path(data_dir, "graph")
        else:
            instances_file = args.instances or Path(".data/mcbo-instances.ttl")
            output_file = args.output or Path(".data/graph.ttl")
        merge_ontology_instances(args.ontology, instances_file, output_file)


if __name__ == "__main__":
    main()

