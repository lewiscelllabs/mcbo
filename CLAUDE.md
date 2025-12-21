# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCBO (Mammalian Cell Bioprocessing Ontology) is a hub-and-spoke, IOF-anchored application ontology for mammalian cell bioprocessing and RNA-seq data curation. It builds on IOF process patterns and BFO foundations, with domain-specific extensions that reference OBO ontology classes for measurement, sequencing, and biological entities.

The ontology is designed to support:
- RNA-seq analysis
- Culture condition optimization
- Product development for CHO cell bioprocessing
- Integration of 724 curated bioprocessing samples from published studies

## Development Commands

### Using Make (Recommended)

```bash
make install       # Install mcbo package
make demo          # Build and evaluate demo data
make qc            # Run ROBOT QC checks on ontology
make all           # Run demo + qc (default)
make real          # Build and evaluate real data (.data/)
make clean         # Remove generated files
make help          # Show all targets
```

### Manual ROBOT QC

```bash
# Download ROBOT if not present
make robot

# Or manually
mkdir -p .robot
curl -L -o .robot/robot.jar "https://github.com/ontodev/robot/releases/download/v1.9.6/robot.jar"

# Run individual QC queries
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/orphan_classes.rq \
  reports/robot/orphan_classes.tsv
```

QC passes if every report is empty (only header line).

### Python Package Installation

```bash
make install
# Or: pip install -e python/
```

### Config-by-Convention

All CLI tools support `--data-dir` for automatic path resolution:

```bash
# These are equivalent:
mcbo-run-eval --data-dir data.sample
mcbo-run-eval --graph data.sample/graph.ttl --results data.sample/results

# Convention: <data-dir>/ contains:
#   graph.ttl           - merged evaluation graph
#   mcbo-instances.ttl  - instance data (ABox)
#   results/            - CQ query results
```

### Competency Question Evaluation

```bash
# Using config-by-convention (recommended)
mcbo-run-eval --data-dir data.sample
mcbo-run-eval --data-dir .data

# Using explicit paths
mcbo-run-eval \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results

# Verify graph parses without running queries
mcbo-run-eval --data-dir data.sample --verify
```

Query results are written as TSV files to `<data-dir>/results/`.

### Available CLI Commands

| Command | Description |
|---------|-------------|
| `mcbo-csv-to-rdf` | Convert CSV metadata to RDF instances (with optional expression data) |
| `mcbo-build-graph` | Build graphs from studies or single CSV (bootstrap, build, merge, add-study) |
| `mcbo-run-eval` | Run SPARQL competency queries |
| `mcbo-stats` | Generate graph statistics |

### Data Workflow Scenarios

| Scenario | Command | Use Case |
|----------|---------|----------|
| Config-by-convention | `make demo` or `make real` | Standard workflow |
| Single CSV, no expression | `mcbo-build-graph bootstrap --data-dir DIR` | Hand-curated metadata, no RNA-seq |
| Multi-study dirs | `mcbo-build-graph build --data-dir DIR` | Per-study CSVs |
| Incremental add | `mcbo-build-graph add-study --study-dir DIR` | Add studies over time |

See `docs/WORKFLOWS.md` for detailed large dataset strategies.

## Architecture

### Hub-and-Spoke Design

MCBO uses a hub-and-spoke architecture with the Industrial Ontology Foundry (IOF) Core as the central hub. The ontology reuses terms from multiple OBO Foundry ontologies:

- **IOF Core**: Industrial processes (ProductProductionProcess, hasOutput)
- **CLO**: Cell lines (CHO-K1)
- **CL**: Cell types (Chinese hamster ovary cell)
- **OBI**: Assays and experimental processes (RNA-seq assay)
- **ChEBI**: Chemicals and media components (glucose, L-glutamine)
- **UO**: Units of measurement (gram per liter)
- **PATO**: Phenotypes (cell viability)
- **SO/GO/PRO**: Molecular entities (transcripts, gene ontology terms, proteins)
- **EFO/ENVO**: Environmental conditions (hypoxia, culture pH)

### Core Modeling Pattern

The ontology uses BFO/OBO-compliant patterns:

1. **Process → Participant → Quality chain**:
   - A bioprocess run (e.g., BatchCultureProcess) is a process instance
   - The run `obo:RO_0000057` (has participant) a CellCultureSystem (material entity)
   - The CellCultureSystem `obo:RO_0000086` (has quality) a CultureConditionQuality instance
   - Temperature/pH/DO values are attached to the CultureConditionQuality

2. **Cell line engineering**:
   - Cell lines can `mcbo:overexpressesGene` gene individuals
   - Inferred from Producer (boolean) + ProductType fields when explicit gene columns not present
   - Antibody products (mAb/BsAb) use shared placeholder gene `mcbo:AntibodyProductGene`

3. **Sample outputs**:
   - Runs produce samples via `mcbo:hasProcessOutput`
   - Samples can be in specific culture phases (StationaryPhase, ExponentialPhase)
   - Productivity measurements are attached to runs

### Key Data Structures

- **TBox (Ontology)**: `ontology/mcbo.owl.ttl` contains the ontology schema
- **ABox (Instances)**: `.data/mcbo-instances.ttl` contains instance data (real data)
- **Evaluation Graphs**: Union of TBox + ABox at `.data/graph.ttl` (real) or `data.sample/graph.ttl` (demo)

### CSV to RDF Conversion Logic

The `mcbo.csv_to_rdf` module (CLI: `mcbo-csv-to-rdf`) transforms tabular metadata into RDF:

- Maps process types (Batch, FedBatch, Perfusion, etc.) to ontology classes
- Creates material entities (CellCultureSystem, cell lines, culture media)
- Attaches culture conditions (temperature, pH, dissolved oxygen) as qualities
- Handles productivity categorization (VeryHigh, High, Medium, LowMedium, Low)
- Infers gene overexpression from Producer + ProductType columns
- Generates IRI-safe identifiers from run/sample accessions

### SPARQL Query Architecture

Competency questions in `eval/queries/*.rq` leverage:

- `rdfs:subClassOf*` property paths for class hierarchies
- OBO relation IRIs (RO_0000057, RO_0000086) for standard relationships
- Filters on productivity types for optimization queries
- Cross-table relationship traversals via the RDF graph structure

## Competency Questions

The ontology is evaluated against 8 competency questions (CQs):

- **CQ1**: Culture conditions (pH, DO, temperature) for peak recombinant protein productivity
- **CQ2**: Cell lines engineered to overexpress gene Y
- **CQ3**: Nutrient concentrations associated with high viable cell density
- **CQ4**: Expression variation of gene X between clones
- **CQ5**: Differentially expressed pathways under Fed-batch vs Perfusion
- **CQ6**: Top genes correlated with recombinant protein productivity in stationary phase
- **CQ7**: Genes with highest fold change between high/low viability cells
- **CQ8**: Cell lines suited for specific glycosylation profiles

Implemented queries: CQ1, CQ2, CQ5 (see `eval/queries/`)

Current evaluation results: 75% CQ coverage, 724 samples, sub-second query times.

## Directory Structure

```
mcbo/
├── ontology/           # MCBO ontology (TBox)
│   └── mcbo.owl.ttl
├── data/               # Input CSV metadata (deprecated - use data.sample/ or .data/)
│   └── sample_metadata.csv
├── python/             # Python package (pip install -e python/)
│   ├── mcbo/           # Core library + CLI modules
│   │   ├── __init__.py      # Package exports
│   │   ├── namespaces.py    # Shared RDF namespaces
│   │   ├── graph_utils.py   # Graph loading/creation utilities
│   │   ├── csv_to_rdf.py    # CSV-to-RDF conversion (mcbo-csv-to-rdf)
│   │   ├── build_graph.py   # Graph building (mcbo-build-graph)
│   │   ├── run_eval.py      # SPARQL evaluation (mcbo-run-eval)
│   │   └── stats_eval_graph.py  # Statistics (mcbo-stats)
│   └── pyproject.toml  # Package metadata and entry points
├── scripts/            # Shell scripts
│   └── run_all_checks.sh    # Full QC + evaluation runner
├── eval/               # Competency question evaluation
│   ├── queries/        # SPARQL query files (*.rq)
│   └── results/        # Query outputs (*.tsv)
├── sparql/             # QC queries for ROBOT (see sparql/README.md)
├── reports/            # QC reports
│   └── robot/
└── docs/               # Documentation and figures
```

## Testing and Validation

Ontology validation uses ROBOT queries in CI/CD:
- Checks for orphan classes (classes without parents)
- Detects duplicate labels
- Identifies missing definitions

See `sparql/README.md` for manual ROBOT commands and query details.
See `.github/workflows/qc.yml` for automated QC workflow.

## Important Notes

- The ontology file uses Turtle format (`.ttl`)
- Instance data is generated from CSV, not hand-curated
- Merged graphs (TBox + ABox) are required for queries using `rdfs:subClassOf*`
- Gene overexpression inference uses heuristics when explicit gene columns absent
- Demo data evaluation uses `data.sample/graph.ttl`; real curated data in `.data/graph.ttl` (git-ignored)
