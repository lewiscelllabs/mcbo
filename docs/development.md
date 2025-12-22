# Development Guide

This guide covers contributing to MCBO, running quality control checks, and understanding 
the evaluation framework.

## Repository Structure

```text
mcbo/
├── ontology/           # MCBO ontology (TBox)
│   └── mcbo.owl.ttl
├── python/             # Python package (pip install -e python/)
│   ├── mcbo/           # Core library + CLI modules
│   │   ├── __init__.py      # Package exports
│   │   ├── namespaces.py    # Shared RDF namespaces
│   │   ├── graph_utils.py   # Graph loading/creation utilities
│   │   ├── csv_to_rdf.py    # CSV-to-RDF conversion
│   │   ├── build_graph.py   # Graph building
│   │   ├── run_eval.py      # SPARQL evaluation
│   │   └── stats_eval_graph.py  # Statistics
│   └── pyproject.toml  # Package metadata and entry points
├── scripts/            # Shell scripts
│   └── run_all_checks.sh    # Full QC + evaluation runner
├── eval/               # Competency question evaluation
│   └── queries/        # SPARQL query files (*.rq)
├── sparql/             # QC queries for ROBOT
├── reports/            # QC reports
│   └── robot/
├── data.sample/        # Demo data (public)
└── .data/              # Real data (git-ignored)
```

## Quality Control

### ROBOT QC Queries

MCBO uses [ROBOT](http://robot.obolibrary.org/) for ontology quality control.

Run all QC checks:

```bash
make qc
```

This executes three QC queries:

| Query | Purpose |
|-------|---------|
| `orphan_classes.rq` | Finds classes without parent classes (orphans) |
| `duplicate_labels.rq` | Finds classes with duplicate `rdfs:label` values |
| `missing_definitions.rq` | Finds classes missing `obo:IAO_0000115` (definition) annotations |

### Manual QC Commands

```bash
# Check for orphan classes
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/orphan_classes.rq \
  reports/robot/orphan_classes.tsv

# Check for duplicate labels
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/duplicate_labels.rq \
  reports/robot/duplicate_labels.tsv

# Check for missing definitions
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/missing_definitions.rq \
  reports/robot/missing_definitions.tsv
```

### Interpreting Results

- **QC passes** if the output TSV contains only a header row (no data rows)
- **QC warns** if the output TSV contains data rows (issues found)

View results:

```bash
# Count issues (subtract 1 for header)
wc -l reports/robot/*.tsv

# View specific issues
cat reports/robot/orphan_classes.tsv
```

## Competency Question Evaluation

### Query Directory

All 8 CQ queries are in `eval/queries/`:

| CQ | Description |
|----|-------------|
| cq1 | Culture conditions (pH, DO, temperature) for peak recombinant protein productivity |
| cq2 | Cell lines engineered to overexpress gene Y |
| cq3 | Nutrient concentrations associated with high viable cell density |
| cq4 | Expression variation of gene X between clones |
| cq5 | Differentially expressed pathways under Fed-batch vs Perfusion |
| cq6 | Top genes correlated with recombinant protein productivity in stationary phase |
| cq7 | Genes with highest fold change between high/low viability cells |
| cq8 | Cell lines suited for specific glycosylation profiles |

### Evaluation Results

**Real Data Statistics** (724 cell culture processes):

```text
Cell Culture Process Instances: 724
  Batch culture process: 518
  Fed-batch culture process: 135
  Perfusion culture process: 49
  Unknown culture process: 22

Bioprocess Sample Instances: 326
```

**Demo vs Real Data Comparison:**

| CQ | Real Data (724) | Demo Data (10) | Notes |
|----|-----------------|----------------|-------|
| CQ1 | 161 | 13 | Culture conditions for productivity |
| CQ2 | 3 | 2 | Overexpression engineering |
| CQ3 | 0 | 4 | Requires CollectionDay, ViableCellDensity |
| CQ4 | 0 | 144 | Requires expression matrix |
| CQ5 | 4 | 3 | Process type distribution |
| CQ6 | 0 | 38 | Requires expression data |
| CQ7 | 0 | 7 | Requires ViabilityPercentage |
| CQ8 | 0 | 3 | Requires TiterValue, QualityType |

CQs returning 0 on real data reflect ongoing curation; the queries are validated and functional.
The demo data includes all required fields to demonstrate complete functionality.

### Running Evaluations

```bash
# Demo data
mcbo-run-eval --data-dir data.sample

# Real data
mcbo-run-eval --data-dir .data

# Verify graph parses without running queries
mcbo-run-eval --data-dir data.sample --verify
```

### Alternative Query Runners

**ROBOT:**

```bash
robot query \
  --input data.sample/graph.ttl \
  --query eval/queries/cq1.rq \
  --output data.sample/results/cq1.tsv
```

**Apache Jena (arq):**

```bash
arq --data data.sample/graph.ttl --query eval/queries/cq1.rq
```

## CI/CD Pipeline

### GitHub Actions Workflow

The repository includes a CI/CD workflow at `.github/workflows/qc.yml` that runs:

1. Ontology parsing verification
2. ROBOT QC queries
3. Demo data build and evaluation

Run the CI pipeline locally:

```bash
make ci
```

This executes:

```bash
make install   # Install mcbo package
make qc        # Run ROBOT QC checks
make demo      # Build and evaluate demo data
make verify-demo  # Verify graph parses
```

### Running All Checks

For a complete QC and evaluation run:

```bash
bash scripts/run_all_checks.sh
```

This runs:

1. Ontology parsing verification
2. All ROBOT QC queries
3. Demo data build and evaluation
4. Real data build and evaluation (if `.data/` exists)

## Contributing

### Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run QC checks: `make qc`
5. Run demo evaluation: `make demo`
6. Submit a pull request

### Term Requests

To request new ontology terms:

1. Go to [GitHub Issues](https://github.com/lewiscelllabs/mcbo/issues)
2. Click "New Issue"
3. Select "MCBO Term Request"
4. Fill in the template

### Coding Standards

- Python code should follow PEP 8
- Use type hints where practical
- Add docstrings to public functions
- Keep functions focused and small

### Testing Changes

Before submitting:

```bash
# Install package in development mode
pip install -e python/

# Run full QC + demo
make all

# Verify no regressions
cat data.sample/results/SUMMARY.txt
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make all` | Run demo + qc (default) |
| `make demo` | Build and evaluate demo data |
| `make real` | Build and evaluate real data (.data/) |
| `make qc` | Run ROBOT QC checks on ontology |
| `make clean` | Remove generated files |
| `make install` | Install mcbo package |
| `make robot` | Download ROBOT jar |
| `make ci` | Run full CI pipeline |
| `make docs` | Build Sphinx documentation |

See `make help` for the complete list.

