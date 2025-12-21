# MCBO Python Package

This directory contains the Python package and CLI tools for the MCBO project.

## Installation

### For Development (Recommended)

Install the package in editable mode from the repository root:

```bash
pip install -e python/
```

This allows you to:
- Import `mcbo` from anywhere
- Edit the source and see changes immediately
- Use CLI commands from any directory (`mcbo-run-eval`, `mcbo-build-graph`, etc.)

### For Production

```bash
pip install python/
```

## Package Structure

```
python/
├── mcbo/                        # Core package
│   ├── __init__.py             # Package exports
│   ├── namespaces.py           # RDF namespace definitions (MCBO, OBO, RO, etc.)
│   ├── graph_utils.py          # Graph utilities (load, create, iri_safe, etc.)
│   ├── csv_to_rdf.py           # CSV-to-RDF conversion logic + CLI
│   ├── build_graph.py          # Graph building CLI
│   ├── run_eval.py             # SPARQL evaluation CLI
│   └── stats_eval_graph.py     # Statistics CLI
├── pyproject.toml              # Package configuration
└── README.md                   # This file
```

## CLI Commands

After installation (`pip install -e python/`), the following commands are available:

| Command | Description |
|---------|-------------|
| `mcbo-csv-to-rdf` | Convert CSV metadata to RDF instances |
| `mcbo-build-graph` | Build graphs from study directories |
| `mcbo-run-eval` | Run SPARQL competency queries |
| `mcbo-stats` | Generate graph statistics |

### Usage Examples

```bash
# SCENARIO 1: Bootstrap from single CSV (no expression)
mcbo-build-graph bootstrap \
  --csv .data/sample_metadata.csv \
  --output .data/graph.ttl

# SCENARIO 4: Bootstrap from single CSV + per-study expression
mcbo-build-graph bootstrap \
  --csv .data/sample_metadata.csv \
  --expression-dir .data/expression/ \
  --output .data/graph.ttl

# SCENARIO 2 & 3: Build from multi-study directories
mcbo-build-graph build \
  --studies-dir .data/studies \
  --output .data/graph.ttl

# Convert CSV to RDF (low-level)
mcbo-csv-to-rdf \
  --csv_file .data/sample_metadata.csv \
  --output_file .data/processed/mcbo_instances.ttl \
  --expression_dir .data/expression/

# Run evaluation queries
mcbo-run-eval \
  --graph .data/graph.ttl \
  --queries eval/queries \
  --results .data/results

# Verify graph parses
mcbo-run-eval --graph data.sample/graph.ttl --verify

# Generate statistics
mcbo-stats --graph .data/graph.ttl
```

### Alternative: Run as Python Modules

You can also run the commands as Python modules:

```bash
python -m mcbo.csv_to_rdf --help
python -m mcbo.build_graph --help
python -m mcbo.run_eval --help
python -m mcbo.stats_eval_graph --help
```

## Using as a Library

After installation, import the package in your Python code:

```python
from mcbo import (
    # Namespaces
    MCBO, OBO, RDF, RDFS, XSD,
    RO_HAS_PARTICIPANT, RO_HAS_QUALITY, BFO_HAS_PART,
    
    # Graph utilities
    create_graph, load_graph, load_graphs,
    iri_safe, safe_numeric,
    ensure_dir, ensure_parent_dir,
    
    # CSV conversion
    convert_csv_to_rdf,
    load_expression_matrix,
    add_expression_data,
)

# Create a new graph with MCBO namespaces
g = create_graph()

# Load an existing graph
g = load_graph(Path("data.sample/graph.ttl"))

# Convert CSV to RDF
g = convert_csv_to_rdf("data/sample_metadata.csv", "output.ttl")
```

## Running All Checks

For a complete QC and evaluation run, use the shell script:

```bash
bash scripts/run_all_checks.sh
```

This runs:
1. Ontology parsing verification
2. ROBOT QC queries on ontology
3. Demo data build and evaluation
4. Real data build and evaluation (if available)

The script automatically installs the `mcbo` package if not already installed.
