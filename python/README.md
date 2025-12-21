# Python Scripts

This directory contains all Python scripts for the MCBO project.

## Scripts

| Script | Description |
|--------|-------------|
| `csv_to_rdf.py` | Converts CSV metadata to RDF/Turtle format |
| `build_graph.py` | Builds and merges knowledge graphs |
| `run_eval.py` | Runs competency question SPARQL queries |
| `stats_eval_graph.py` | Generates statistics from evaluation graphs |

## Usage Examples

### Convert CSV to RDF

```bash
python python/csv_to_rdf.py \
  --csv_file .data/sample_metadata.csv \
  --output_file .data/processed/mcbo_instances.ttl
```

### Build a Graph from Studies

```bash
python python/build_graph.py build \
  --studies-dir data.sample/studies \
  --output data.sample/graph.ttl
```

### Run Evaluation Queries

```bash
python python/run_eval.py \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results
```

### Verify Graph Parses

```bash
python python/run_eval.py --graph data.sample/graph.ttl --verify
```

### Generate Statistics

```bash
python python/stats_eval_graph.py --graph .data/graph.ttl
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
