# MCBO Setup Instructions

## Creating the MCBO Conda Environment

1. Create a new conda environment named `mcbo`:
   ```bash
   conda create -n mcbo python=3.10
   ```

2. Activate the environment:
   ```bash
   conda activate mcbo
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running All Checks

The `scripts/run_all_checks.sh` script runs both ROBOT QC queries and all CQ evaluations:

```bash
bash scripts/run_all_checks.sh
```

This script will:
1. Activate the `mcbo` conda environment (if available)
2. Run ROBOT QC queries (orphan classes, duplicate labels, missing definitions)
3. Build and evaluate demo data (`data.sample/`) and real data (`.data/` if present)
4. Output summary results for both datasets

Results are written to:
- `reports/robot/` - QC query results
- `data.sample/results/` - CQ results from demo data
- `.data/results/` - CQ results from real data (if present)

## Manual Evaluation

To run evaluations manually:

```bash
# Activate environment
conda activate mcbo

# Run on real data (if available)
python python/run_eval.py \
  --graph .data/graph.ttl \
  --queries eval/queries \
  --results .data/results

# Run on demo data
python python/run_eval.py \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results
```

## Dependencies

- Python 3.10+
- rdflib >= 7.0.0
- pandas >= 1.5.0
- Java (for ROBOT)
- ROBOT jar (located at `.robot/robot.jar`)

See `requirements.txt` for Python package versions.

