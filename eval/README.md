# Evaluation (Competency Questions)

📖 **Full documentation: https://mcbo.readthedocs.io/en/latest/development.html#competency-question-evaluation**

## Query Files

All 8 CQ queries are in `eval/queries/`:

| CQ | Description |
|----|-------------|
| cq1 | Culture conditions for peak productivity |
| cq2 | Engineered cell lines |
| cq3 | Nutrient concentrations |
| cq4 | Gene expression between clones |
| cq5 | Process type comparison |
| cq6 | Genes in stationary phase |
| cq7 | Viability fold change |
| cq8 | Glycosylation profiles |

## Running Evaluations

```bash
mcbo-run-eval --data-dir data.sample
mcbo-run-eval --data-dir .data
```

For complete evaluation documentation including results comparison, see the [Development Guide](https://mcbo.readthedocs.io/en/latest/development.html).
