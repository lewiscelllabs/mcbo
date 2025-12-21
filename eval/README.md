# Evaluation (Competency Questions)

This directory contains SPARQL queries for all 8 competency questions (CQ1-CQ8).

## Directory layout

```
eval/
├── queries/
│   ├── cq1.rq             # Culture conditions for peak productivity
│   ├── cq2.rq             # Engineered cell lines overexpressing genes
│   ├── cq3.rq             # Nutrient concentrations and viable cell density at day 6
│   ├── cq4.rq             # Gene expression variation between clones
│   ├── cq5.rq             # Process type comparison (proxy for pathway differential expression)
│   ├── cq6.rq             # Genes correlated with productivity in stationary phase
│   ├── cq7.rq             # Fold change between high/low viability samples
│   └── cq8.rq             # Cell lines/clones suited for glycosylation profiles
└── README.md

# Generated graphs and results (NOT in eval/):
.data/graph.ttl            # Real data graph (git-ignored)
.data/results/             # Real data results (git-ignored)
data.sample/graph.ttl      # Demo data graph (generated)
data.sample/results/       # Demo data results (generated)
```

## Graph Types

| Graph | Location | Purpose | Checked In? |
|-------|----------|---------|-------------|
| `data.sample/graph.ttl` | `data.sample/` | Generated from demo studies | ❌ No (generated) |
| `.data/graph.ttl` | `.data/` | Generated from real curated data | ❌ No (.gitignored) |

### data.sample/graph.ttl (demo data)

This is **generated** from `data.sample/studies/`:
- 7 samples from 2 demo studies
- All 8 CQs return results
- Demonstrates the full data pipeline

### .data/graph.ttl (real data)

This is **generated** from `.data/studies/`:
- Contains real curated data (723+ samples)
- Some CQs may return 0 until additional fields are populated
- Git-ignored (not shared publicly)

## How to run evaluations

### Demo data (generated from data.sample/)

```bash
pip install -e python/  # Install mcbo package (first time only)

# Build graph
mcbo-build-graph build \
  --studies-dir data.sample/studies \
  --output data.sample/graph.ttl

# Evaluate
mcbo-run-eval \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results
```

### Real data (generated from .data/)

```bash
# Build graph
mcbo-build-graph build \
  --studies-dir .data/studies \
  --output .data/graph.ttl

# Evaluate
mcbo-run-eval \
  --graph .data/graph.ttl \
  --queries eval/queries \
  --results .data/results
```

### Or run all at once

```bash
bash scripts/run_all_checks.sh
```

### Compute graph statistics

```bash
# Stats on real data
mcbo-stats --graph .data/graph.ttl

# Stats on demo data
mcbo-stats --graph data.sample/graph.ttl
```

Output includes:
- Total cell culture process instances (by type: Batch, Fed-batch, Perfusion, Unknown)
- Total bioprocess sample instances

## Alternative runners (optional)

### ROBOT query

```bash
robot query \
  --input data.sample/graph.ttl \
  --query eval/queries/cq1.rq \
  --output data.sample/results/cq1.tsv
```

### Apache Jena (arq)

```bash
arq --data data.sample/graph.ttl --query eval/queries/cq1.rq > data.sample/results/cq1.tsv
```

(If using `arq`, ensure prefixes are included in the `.rq` files.)

## Notes on CQ semantics and implementation status

**Fully implemented and tested:**
* **CQ1**: Returns culture conditions (pH, dissolved oxygen, temperature) for processes with medium/high/very-high productivity.
* **CQ2**: Returns engineered CHO cell lines (overexpressesGene) along with maximum observed productivity.
* **CQ4**: Compares gene expression levels between clones (subclones) of a cell line.
* **CQ5**: Reports counts by process type (currently a lightweight proxy for the eventual "differential expression / pathways" CQ).
* **CQ7**: Returns genes with highest fold change between high-viability (>90%) and low-viability (<50%) samples.
* **CQ8**: Identifies cell lines/clones producing products with quality measurements (e.g., glycosylation profiles).

**Implemented but may require additional data:**
* **CQ3**: Finds nutrient concentrations associated with high viable cell density at day 6. Requires processes with `CultureMedium` containing `NutrientConcentration` data linked to day-6 samples with viability measurements.
* **CQ6**: Identifies genes with highest expression in stationary phase samples with high productivity. Requires gene expression data linked to samples in stationary phase.

**Query implementation notes:**
- CQ3 and CQ6 queries are syntactically correct and work with the demo graph. They may return 0 results on the real curated data until additional fields (nutrient concentrations, gene expression data) are populated.
- CQ5 is currently a process type count query rather than a true pathway differential expression analysis. Full pathway analysis would require integration with pathway databases (e.g., GO, KEGG) and statistical computation outside SPARQL.
- CQ8 uses `QualityMeasurement` as a framework for glycosylation profiles. Domain-specific glycosylation attributes can be added as subclasses of `QualityMeasurement` as needed.

See the paper's Evaluation section for interpretation and limitations.

