# Sample Data for MCBO Workflow Demo

This directory contains sample data to demonstrate all MCBO data ingestion workflows.

## Directory Structure

```
data.sample/
├── sample_metadata.csv       # Combined metadata for all studies (Scenario 1 & 4)
├── expression/               # Per-study expression matrices (Scenario 4)
│   ├── study_demo_001.csv
│   ├── study_demo_002.csv
│   └── study_demo_003.csv
├── studies/                  # Multi-study directory structure (Scenario 2 & 3)
│   ├── study_demo_001/
│   │   ├── sample_metadata.csv
│   │   └── expression_matrix.csv
│   ├── study_demo_002/
│   │   ├── sample_metadata.csv
│   │   └── expression_matrix.csv
│   └── study_demo_003/
│       ├── sample_metadata.csv
│       └── expression_matrix.csv
├── processed/                # Generated instances
│   └── mcbo-instances.ttl
├── results/                  # CQ evaluation results
└── graph.ttl                 # Generated evaluation graph
```

## Quick Test

```bash
pip install -e python/  # First time only
bash scripts/run_all_checks.sh
```

---

## Four Data Workflow Scenarios

### Scenario 1: Single CSV, No Expression Data

Use when you have all metadata in one hand-curated CSV file.

```bash
mcbo-build-graph bootstrap \
  --csv data.sample/sample_metadata.csv \
  --output data.sample/graph.ttl
```

### Scenario 2: Multi-Study Directories (No Expression)

Use when each study has its own `sample_metadata.csv` but no expression data.

```bash
mcbo-build-graph build \
  --studies-dir data.sample/studies \
  --output data.sample/graph.ttl
```

### Scenario 3: Multi-Study Directories WITH Expression

Use when each study has its own `sample_metadata.csv` AND `expression_matrix.csv`.

```bash
mcbo-build-graph build \
  --studies-dir data.sample/studies \
  --output data.sample/graph.ttl
```

(Same command as Scenario 2 - expression matrices are auto-detected)

### Scenario 4: Single CSV + Per-Study Expression Matrices

Use when you have one combined metadata CSV but separate expression matrices per study.
This is the "bootstrap" workflow for large curated datasets.

```bash
mcbo-build-graph bootstrap \
  --csv data.sample/sample_metadata.csv \
  --expression-dir data.sample/expression/ \
  --output data.sample/graph.ttl
```

Or using `mcbo-csv-to-rdf` + `mcbo-build-graph merge`:

```bash
# Step 1: Convert CSV to instances with expression data
mcbo-csv-to-rdf \
  --csv_file data.sample/sample_metadata.csv \
  --output_file data.sample/mcbo-instances.ttl \
  --expression_dir data.sample/expression/

# Step 2: Merge with ontology
mcbo-build-graph merge \
  --ontology ontology/mcbo.owl.ttl \
  --instances data.sample/mcbo-instances.ttl \
  --output data.sample/graph.ttl
```

---

## Incremental Workflow (Adding Studies Over Time)

After bootstrapping, add new studies incrementally:

```bash
# Add a new study
mcbo-build-graph add-study \
  --study-dir data.sample/studies/study_demo_003 \
  --instances data.sample/mcbo-instances.ttl

# Rebuild the graph
mcbo-build-graph merge \
  --instances data.sample/mcbo-instances.ttl \
  --output data.sample/graph.ttl
```

---

## Evaluate the Graph

After building, run competency question evaluation:

```bash
mcbo-run-eval \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results

# View results
cat data.sample/results/SUMMARY.txt

# Get statistics
mcbo-stats --graph data.sample/graph.ttl
```

---

## Sample Data Details

### study_demo_001 (CHO-K1 Fed-Batch)
- 4 samples from 2 clones (Clone_A, Clone_B)
- Covers exponential and stationary phases
- Expression data for 7 genes including housekeeping (ACTB, GAPDH)
- Demonstrates CQ1, CQ3, CQ4, CQ6, CQ7

### study_demo_002 (HEK293 Mixed)
- 3 samples: 2 batch, 1 perfusion
- Includes titer and quality measurements
- Expression data for 6 genes including inflammatory markers
- Demonstrates CQ5, CQ8

### study_demo_003 (CHO-DG44 Mixed)
- 2 samples: 1 batch, 1 perfusion
- Clone_X with bispecific antibody (BsAb) production
- Expression data for 6 genes including growth factors

## Expected Results

All 8 CQs should return results:

| CQ | Results | Description |
|----|---------|-------------|
| CQ1 | 9 | Culture conditions for productivity |
| CQ2 | 1 | Overexpression engineering |
| CQ3 | 4 | Nutrient concentrations at day 6 |
| CQ4 | 224 | Gene expression between clones |
| CQ5 | 3 | Process type distribution |
| CQ6 | 26 | Genes in stationary phase |
| CQ7 | 7 | Viability fold change |
| CQ8 | 3 | Quality profiles |
