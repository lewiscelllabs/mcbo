# mcbo
Bioprocessing ontology that builds on IOF process patterns and BFO foundations, with domain-specific extensions that reference OBO ontology classes for measurement, sequencing, and biological entities.

**New Term Request:**

Please click `'Issues'>'New Issue'>'MCBO Term Request'` to submit your request

**Please cite:**

Robasky, K., Morrissey, J., Riedl, M., Dräger, A., Borth, N., Betenbaugh, M. J., & Lewis, N. E. (2025, November 11). MCBO: Mammalian Cell Bioprocessing Ontology, a hub-and-spoke, IOF-anchored application ontology for mammalian cell bioprocessing. [preprint/paper details].

[![CI/CD](https://github.com/lewiscelllabs/mcbo/actions/workflows/qc.yml/badge.svg)](https://github.com/lewiscelllabs/mcbo/actions/workflows/qc.yml)

[![YouTube](https://img.shields.io/badge/YouTube-Video-red?style=for-the-badge&logo=youtube)](https://youtu.be/YTvCv-l0ia4)

# MCBO Project

Main MCBO ontology diagram below (click to get github doc, then right-click and open in new tab to zoom in).

- `ontology/`: The MCBO ontology (TBox)
- `src/`: Core CSV-to-RDF conversion logic
- `scripts/`: Workflow scripts (`build_graph.py`, `run_all_checks.sh`)
- `eval/`: Competency question queries and results
- `data.sample/`: **Demo data** - try this first to test the workflow!
- `.data/`: Private directory for real world curated data (.gitignore'd)
- `docs/`: Implementation details and CQ column requirements
- `sparql/`: QC queries; outputs to `reports/robot`

## Quick Start

```bash
# 1. Create and activate conda environment
conda create -n mcbo python=3.10
conda activate mcbo
pip install -r requirements.txt

# 2. Run all checks (Ontology verification, QC + demo data + real data if present)
bash scripts/run_all_checks.sh
```

## Adding Your Own Data

Real-world curated data goes in `.data/` (git-ignored). Each study has its own subdirectory:

```
.data/
├── studies/
│   ├── my_study_001/
│   │   ├── sample_metadata.csv    # Required: one row per run/sample
│   │   └── expression_matrix.csv  # Optional: genes as columns
│   └── my_study_002/
│       └── sample_metadata.csv
├── processed/
│   └── mcbo_instances.ttl         # Generated
└── graph.ttl                      # Generated
```

### Workflow: Add Studies → Build Graph → Evaluate

```bash
conda activate mcbo

# Step 1: Add a new study (can repeat for multiple studies)
python scripts/build_graph.py add-study \
  --study-dir .data/studies/my_new_study \
  --instances .data/processed/mcbo_instances.ttl

# Step 2: Merge with ontology to create evaluation graph
python scripts/build_graph.py merge \
  --ontology ontology/mcbo.owl.ttl \
  --instances .data/processed/mcbo_instances.ttl \
  --output .data/graph.ttl

# Step 3: Run CQ evaluation
python run_eval.py \
  --graph .data/graph.ttl \
  --queries eval/queries \
  --results .data/results
```

### Alternative: Rebuild Everything at Once

```bash
python scripts/build_graph.py build \
  --studies-dir .data/studies \
  --instances .data/processed/mcbo_instances.ttl \
  --output .data/graph.ttl
```

See `docs/README.md` for detailed instructions and `docs/CQ_DATA_REQUIREMENTS.md` for CSV column definitions.

<img width="2561" height="1781" alt="image" src="https://github.com/user-attachments/assets/781c1af6-8238-45a3-b26b-c6c9010dd77e" />

# Competency questions:

All 8 competency questions have SPARQL query implementations in `eval/queries/`:

- **CQ1**: Under what culture conditions (pH, dissolved oxygen, temperature) do the cells reach peak recombinant protein productivity?
- **CQ2**: Which cell lines have been engineered to overexpress gene Y?
- **CQ3**: Which nutrient concentrations in cell line K are most associated with viable cell density above Z at day 6 of culture?
- **CQ4**: How does the expression of gene X vary between clone A and clone B?
- **CQ5**: What pathways are differentially expressed under Fed-batch vs Perfusion in cell line K? *(Currently implemented as process type comparison)*
- **CQ6**: Which are the top genes correlated with recombinant protein productivity in the stationary phase of all experiments?
- **CQ7**: Which genes have the highest fold change between cells with viability (>90%) and those without (<50%)?
- **CQ8**: Which cell lines or subclones are best suited for glycosylation profiles required for therapeutic protein X?

**Note:** The demo graph (`data.sample/graph.ttl`) includes demonstration data for all CQs. Some CQs (CQ3, CQ6) may return 0 results on the real curated data until additional fields are populated. See `eval/README.md` for details.

