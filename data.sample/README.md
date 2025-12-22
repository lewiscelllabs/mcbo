# Sample Data for MCBO Workflow Demo

📖 **Full documentation: https://mcbo.readthedocs.io/en/latest/workflows.html**

## Quick Test

```bash
make demo
```

## Structure

```
data.sample/
├── studies/            # Multi-study directory structure
├── expression/         # Per-study expression matrices
├── sample_metadata.csv # Combined metadata
├── graph.ttl           # Generated evaluation graph
└── results/            # CQ evaluation results
```

`graph.ttl`  is **generated** from `data.sample/studies/`:
- 9 samples from 3 demo studies
- All 8 CQs return results
- Demonstrates the full data pipeline

## Demo Studies

| Study | Cell Line | Process Types |
|-------|-----------|---------------|
| study_demo_001 | CHO-K1 | Fed-Batch |
| study_demo_002 | HEK293 | Batch, Perfusion |
| study_demo_003 | CHO-DG44 | Batch, Perfusion |


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

All 8 CQs return results with this demo data. See the [Workflows Guide](https://mcbo.readthedocs.io/en/latest/workflows.html) for detailed scenarios.
