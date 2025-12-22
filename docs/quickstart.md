# Quick Start

This guide gets you running MCBO in minutes using the included demo data.

## Prerequisites

Ensure you have completed the {doc}`installation` steps:

```bash
conda activate mcbo
make install
```

## Running the Demo

The fastest way to see MCBO in action:

```bash
make demo
```

This single command:

1. Builds a graph from the demo studies in `data.sample/studies/`
2. Runs all 8 competency question (CQ) SPARQL queries
3. Displays statistics and results

Expected output:

```text
Building demo graph...
Running CQ evaluation on demo data...

=== EVALUATION SUMMARY ===
Graph: data.sample/graph.ttl
Queries: eval/queries

CQ Results:
  cq1: 13 results
  cq2: 2 results
  cq3: 4 results
  ...

✅ Demo data processing complete
```

## Understanding the Output

### Demo Data Structure

```text
data.sample/
├── studies/                  # Input: study directories
│   ├── study_demo_001/
│   │   ├── sample_metadata.csv
│   │   └── expression_matrix.csv
│   └── study_demo_002/
│       └── sample_metadata.csv
├── graph.ttl                 # Generated: evaluation graph
├── mcbo-instances.ttl        # Generated: instance data
└── results/                  # Generated: CQ results
    ├── cq1.tsv
    ├── cq2.tsv
    └── SUMMARY.txt
```

### Generated Files

- **graph.ttl** - The merged evaluation graph (TBox + ABox) used for SPARQL queries
- **mcbo-instances.ttl** - Instance data (ABox) generated from CSV files
- **results/*.tsv** - Tab-separated query results for each competency question

## Manual Steps (Alternative)

If you prefer to run commands individually:

```bash
# Step 1: Build the graph
mcbo-build-graph build --data-dir data.sample

# Step 2: Run evaluation queries
mcbo-run-eval --data-dir data.sample

# Step 3: View statistics
mcbo-stats --data-dir data.sample

# Step 4: Check the results
cat data.sample/results/SUMMARY.txt
```

## Running QC Checks

To validate the ontology with ROBOT:

```bash
make qc
```

This runs quality control queries that check for:

- Orphan classes (classes without parents)
- Duplicate labels
- Missing definitions

## Run Everything

To run the complete CI/CD pipeline locally:

```bash
make all    # Runs demo + qc
```

Or for a full CI check including verification:

```bash
make ci     # Runs install + qc + demo + verify-demo
```

## Next Steps

- {doc}`workflows` - Learn about different data ingestion scenarios
- {doc}`cli` - Explore all CLI commands and options
- {doc}`ontology` - Understand the MCBO modeling patterns

