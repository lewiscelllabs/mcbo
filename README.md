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
- `python/`: Python package with CLI tools (`mcbo-csv-to-rdf`, `mcbo-build-graph`, `mcbo-run-eval`, `mcbo-stats`)
- `scripts/`: Shell scripts (`run_all_checks.sh`)
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

# 2. Install mcbo package and run demo
make install
make demo          # Build and evaluate demo data
make qc            # Run ROBOT QC checks on ontology

# Or run all checks at once
make all           # Runs demo + qc
```

## Adding Your Own Data

Real-world curated data goes in `.data/` (git-ignored). Use config-by-convention:

```
.data/
├── studies/                  # Input: study directories
│   ├── my_study_001/
│   │   ├── sample_metadata.csv    # Required
│   │   └── expression_matrix.csv  # Optional
│   └── my_study_002/
│       └── sample_metadata.csv
├── mcbo-instances.ttl        # Generated: instance data (ABox)
├── graph.ttl                 # Generated: evaluation graph
└── results/                  # Generated: CQ results
```

### Workflow: Using Makefile (Recommended)

```bash
conda activate mcbo

# Build and evaluate real data
make real

# Or run individual steps
make real-build    # Build graph
make real-eval     # Run CQ evaluation
make real-stats    # Show statistics
```

### Workflow: Using CLI Commands

```bash
# Config-by-convention (auto-resolves paths)
mcbo-build-graph build --data-dir .data
mcbo-run-eval --data-dir .data
mcbo-stats --data-dir .data

# Or add studies incrementally for large datasets
mcbo-build-graph add-study --study-dir .data/studies/my_new_study --data-dir .data
mcbo-build-graph merge --data-dir .data
```

See `docs/WORKFLOWS.md` for large dataset strategies and `docs/CQ_DATA_REQUIREMENTS.md` for CSV column definitions.

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

