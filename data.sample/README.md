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

## Demo Studies

| Study | Cell Line | Process Types |
|-------|-----------|---------------|
| study_demo_001 | CHO-K1 | Fed-Batch |
| study_demo_002 | HEK293 | Batch, Perfusion |
| study_demo_003 | CHO-DG44 | Batch, Perfusion |

All 8 CQs return results with this demo data. See the [Workflows Guide](https://mcbo.readthedocs.io/en/latest/workflows.html) for detailed scenarios.
