# Sample Data for MCBO Workflow Demo

This directory contains sample data to demonstrate the MCBO data ingestion workflow.

## Directory Structure

```
data.sample/
├── studies/
│   ├── study_demo_001/
│   │   ├── sample_metadata.csv    # 4 CHO-K1 fed-batch runs
│   │   └── expression_matrix.csv  # 7 genes × 4 samples
│   └── study_demo_002/
│       ├── sample_metadata.csv    # 3 HEK293 runs (batch + perfusion)
│       └── expression_matrix.csv  # 6 genes × 3 samples
├── processed/
│   └── mcbo_instances.ttl         # Generated instances
├── results/                       # CQ evaluation results
├── graph.ttl                      # Generated evaluation graph
└── README.md
```

## Quick Test

```bash
# Run all checks (includes demo data)
bash scripts/run_all_checks.sh
```

## Manual Workflow

### Option A: Incremental (add studies one at a time)

```bash
conda activate mcbo

# 1. Add first study
python python/build_graph.py add-study \
  --study-dir data.sample/studies/study_demo_001 \
  --instances data.sample/processed/mcbo_instances.ttl

# 2. Add second study
python python/build_graph.py add-study \
  --study-dir data.sample/studies/study_demo_002 \
  --instances data.sample/processed/mcbo_instances.ttl

# 3. Merge with ontology to create evaluation graph
python python/build_graph.py merge \
  --ontology ontology/mcbo.owl.ttl \
  --instances data.sample/processed/mcbo_instances.ttl \
  --output data.sample/graph.ttl

# 4. Run CQ evaluation
python python/run_eval.py \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results

# View results
cat data.sample/results/SUMMARY.txt
```

### Option B: Full rebuild (all studies at once)

```bash
conda activate mcbo

# Build graph from all demo studies
python python/build_graph.py build \
  --studies-dir data.sample/studies \
  --ontology ontology/mcbo.owl.ttl \
  --instances data.sample/processed/mcbo_instances.ttl \
  --output data.sample/graph.ttl

# Evaluate against all 8 CQs
python python/run_eval.py \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results

# View results
cat data.sample/results/SUMMARY.txt
```

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

