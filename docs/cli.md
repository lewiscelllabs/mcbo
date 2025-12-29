# CLI Reference

MCBO provides four command-line tools for working with bioprocessing data and the ontology.

## Available Commands

| Command | Description |
|---------|-------------|
| `mcbo-csv-to-rdf` | Convert CSV metadata to RDF instances (with optional expression data) |
| `mcbo-build-graph` | Build graphs from studies or single CSV (bootstrap, build, merge, add-study) |
| `mcbo-run-eval` | Run SPARQL competency queries |
| `mcbo-stats` | Generate graph statistics |

## mcbo-build-graph

Build and manage evaluation graphs.

### Subcommands

**bootstrap** - Create graph from single CSV

```bash
mcbo-build-graph bootstrap \
  --csv .data/sample_metadata.csv \
  --output .data/graph.ttl
```

**build** - Build from study directories

```bash
mcbo-build-graph build \
  --studies-dir .data/studies \
  --output .data/graph.ttl

# Or with config-by-convention
mcbo-build-graph build --data-dir .data
```

**add-study** - Add a study incrementally

```bash
mcbo-build-graph add-study \
  --study-dir .data/studies/my_new_study \
  --instances .data/mcbo-instances.ttl
```

**merge** - Merge instances with ontology

```bash
mcbo-build-graph merge \
  --ontology ontology/mcbo.owl.ttl \
  --instances .data/mcbo-instances.ttl \
  --output .data/graph.ttl
```

### Options

```text
--data-dir DIR       Use config-by-convention (auto-resolves paths)
--csv FILE           Input CSV file (for bootstrap)
--studies-dir DIR    Directory containing study subdirectories
--study-dir DIR      Single study directory to add
--instances FILE     Path to instances TTL file
--output FILE        Output graph file
--ontology FILE      Ontology TTL file (default: ontology/mcbo.owl.ttl)
--expression-dir DIR Directory with per-study expression matrices
--expression-matrix FILE  Single expression matrix file
```

## mcbo-csv-to-rdf

Low-level CSV to RDF conversion.

```bash
mcbo-csv-to-rdf \
  --csv_file .data/sample_metadata.csv \
  --output_file .data/mcbo-instances.ttl
```

With expression data:

```bash
mcbo-csv-to-rdf \
  --csv_file .data/sample_metadata.csv \
  --output_file .data/mcbo-instances.ttl \
  --expression_dir .data/expression/
```

### Options

```text
--csv_file FILE          Input CSV metadata file (required)
--output_file FILE       Output TTL file (required)
--expression_matrix FILE Single expression matrix CSV
--expression_dir DIR     Directory with per-study expression CSVs
```

## mcbo-run-eval

Run SPARQL competency question queries.

```bash
# Using config-by-convention
mcbo-run-eval --data-dir data.sample

# Using explicit paths
mcbo-run-eval \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results
```

### Options

```text
--data-dir DIR      Use config-by-convention
--graph FILE        Input graph TTL file
--queries DIR       Directory with .rq query files (default: eval/queries)
--results DIR       Output directory for TSV results
--verify            Only verify graph parses, don't run queries
--fail-on-empty     Exit with error if any CQ returns 0 results
```

## mcbo-stats

Generate statistics about a graph.

```bash
mcbo-stats --data-dir data.sample

# Or with explicit path
mcbo-stats --graph .data/graph.ttl
```

Output includes:

- Total cell culture process instances (by type: Batch, Fed-batch, Perfusion, Unknown)
- Total bioprocess sample instances

## Config-by-Convention

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

## Data Dictionary

> **This is the authoritative reference for CSV column definitions.** All metadata files (`sample_metadata.csv`) use these 36 columns.

### Column Overview

| Category | Count | Purpose |
|----------|-------|---------|
| [Identifiers](#identifiers) | 4 | Sample/run/study IDs |
| [Dataset Provenance](#dataset-provenance) | 8 | Source database and sequencing metadata |
| [Cell Line](#cell-line) | 6 | Cell line characteristics |
| [Culture Conditions](#culture-conditions) | 5 | Temperature, pH, nutrients |
| [Process & Productivity](#process--productivity) | 6 | Process type and production metrics |
| [Product](#product) | 3 | What the cell line produces |
| [Sample State](#sample-state) | 4 | Time-point and viability data |

---

### Identifiers

| Column | Type | CQs | Definition |
|--------|------|-----|------------|
| `RunAccession` | string | all | Unique identifier for a bioprocess run. Typically an SRA run accession (e.g., ERR4319927) or internal ID. Primary key for joining with expression data. |
| `SampleAccession` | string | all | Unique identifier for a biological sample. Typically an SRA sample accession (e.g., ERS4805133). One run may produce one sample. |
| `StudyID` | string | all | Identifier grouping related samples into a study (e.g., study_dhiman). Used to organize data by publication or project. |
| `FullSampleName` | string | — | Human-readable descriptive name combining cell line, conditions, and other metadata. For display purposes. |

### Dataset Provenance

| Column | Type | CQs | Definition |
|--------|------|-----|------------|
| `DatasetAccession` | string | — | Primary database accession for the dataset (e.g., ERP122753, SRP066848). Links to external repositories. |
| `DatasetReadable` | string | — | Human-readable version of the dataset accession. Often same as DatasetAccession. |
| `DatasetName` | string | — | Short name for the dataset, typically author surname (e.g., Dhiman, vanWijk, Hefzi). |
| `DatasetAbbrev` | string | — | Single-letter or short abbreviation for the dataset (e.g., D, vW, H). Used in compact displays. |
| `Author` | string | — | Lead author or principal investigator name for the study. |
| `LibraryStrategy` | string | — | RNA-seq library preparation method. Values: rRNA (ribosomal depletion), PolyA (poly-A selection). |
| `PairedEnd` | boolean | — | Whether sequencing used paired-end reads. TRUE = paired-end, FALSE = single-end. |
| `Source` | string | — | Origin of the data. Values: SRA (public repository), In-House (internal data). |

### Cell Line

| Column | Type | CQs | Definition |
|--------|------|-----|------------|
| `CellLine` | string | 1-8 | Cell line name used in the bioprocess. Common values: CHO-K1, CHO-S, CHO-DG44, CHO-DXB11, HEK293. CHO lines are classified as `mcbo:CHOCellLine`. |
| `Host` | boolean | — | Whether this is a host/parental cell line (not producing recombinant product). TRUE = host line, FALSE = producer line. |
| `CellLineSource` | enum | — | Commercial availability. Values: Commercial, Non-Commercial. |
| `CellLineExact` | string | — | Specific vendor or source of the cell line (e.g., ATCC, Horizon, Life Technologies, Thermo Fisher). |
| `SelectionMarker` | string | — | Genetic selection system used. Values: GS+/- (glutamine synthetase heterozygous), GS-/- (knockout), DHFR, ProcessEvolved. |
| `Growth` | enum | — | Qualitative growth rate assessment. Values: Low, Medium, High. |

### Culture Conditions

| Column | Type | CQs | Definition |
|--------|------|-----|------------|
| `Temperature` | decimal | 1 | Culture temperature in degrees Celsius. Typical range: 31-37°C. Lower temperatures often used for productivity. |
| `pH` | decimal | 1 | Culture medium pH. Typical range: 6.8-7.4. Critical for cell viability and product quality. |
| `DissolvedOxygen` | decimal | 1 | Dissolved oxygen as percentage of air saturation. Typical range: 20-60%. Affects metabolism and productivity. |
| `Glutamine` | boolean | — | Whether glutamine was supplemented in the medium. TRUE = present, FALSE = absent or glutamine-free medium. |
| `GlutamineConcentration` | decimal | 3 | Glutamine concentration in millimolar (mM). Typical range: 0-8 mM. Key nutrient affecting growth and ammonia production. |

### Process & Productivity

| Column | Type | CQs | Definition |
|--------|------|-----|------------|
| `ProcessType` | enum | 5 | Bioreactor operating mode. Values: Batch (no feeding), FedBatch (nutrient feeding), Perfusion (continuous media exchange). Maps to `mcbo:BatchCultureProcess`, `mcbo:FedBatchCultureProcess`, `mcbo:PerfusionCultureProcess`. |
| `CulturePhase` | enum | 4, 6 | Growth phase at sample collection. Values: EarlyExp, MidExp, LateExp (exponential sub-phases), Stationary. |
| `Productivity` | enum | 1, 6 | Qualitative productivity assessment. Values: VeryHigh, High, Medium, Low. CQ1 filters for High/VeryHigh. |
| `Stability` | boolean | — | Whether the cell line shows stable transgene expression over passages. TRUE = stable, FALSE = unstable. |
| `TiterValue` | decimal | 8 | Product concentration in mg/L. Final or harvest titer of recombinant protein/antibody. |
| `QualityType` | string | 8 | Product quality attribute being assessed. Values: Glycosylation, Aggregation, ChargeVariants, etc. |

### Product

| Column | Type | CQs | Definition |
|--------|------|-----|------------|
| `Producer` | boolean | 2 | Whether this cell line produces recombinant product. TRUE = producer (creates `mcbo:overexpressesGene` link), FALSE = host/control. |
| `ProductType` | string | 2, 8 | The recombinant product being produced. Three categories: (1) **Gene symbol** (e.g., AMBP, CCL20) → creates `mcbo:ProteinProduct` with `encodedByGene` link; (2) **Antibody term** (mAb, IgG, BsAb) → creates `mcbo:AntibodyProduct`; (3) **Control** (Control, WT, Mock) → skipped. |
| `EnsemblGeneID` | string | — | Ensembl stable gene identifier for the product gene. **Only applicable when ProductType is a gene symbol.** Format: ENSG followed by 11 digits (e.g., ENSG00000106927 for AMBP). Links to Ensembl database for cross-referencing genomic data. Creates `mcbo:hasEnsemblGeneID` property on the gene. |

### Sample State

| Column | Type | CQs | Definition |
|--------|------|-----|------------|
| `CollectionDay` | integer | 3 | Day of culture when sample was collected. Day 0 = inoculation. CQ3 specifically queries day 6 samples. |
| `ViableCellDensity` | decimal | 3 | Viable cell concentration in cells/mL at collection. Typical range: 1e6 - 2e7 cells/mL. |
| `ViabilityPercentage` | decimal | 7 | Percentage of cells that are viable at collection. Range: 0-100%. CQ7 compares >90% vs <50% viability. |
| `CloneID` | string | 4, 8 | Identifier for a specific clone within a cell line. Used to compare expression between clones (CQ4) and link to quality data (CQ8). |

---

### ProductType Classification

The `ProductType` column determines how the product is modeled in RDF:

| ProductType Value | RDF Class | Example | Notes |
|-------------------|-----------|---------|-------|
| Gene symbol (all caps, 2-10 chars) | `mcbo:ProteinProduct` | AMBP, CCL20, FN1 | Creates gene via `encodedByGene`; add `EnsemblGeneID` |
| Antibody terms | `mcbo:AntibodyProduct` | mAb, IgG, BsAb | Subclass of ProteinProduct |
| Control terms | (skipped) | Control, WT, Mock | No product created |

### Expression Data

Gene expression comes from **separate matrix files** (not metadata columns):

```csv
SampleAccession,ACTB,GAPDH,TP53
DEMO001_SAMPLE_A,1000,800,250
```

- First column: `SampleAccession` (must match metadata)
- Other columns: gene symbols with expression values
- Ensembl IDs for expression genes: use `gene_annotations.csv`

---

### CQ-to-Column Quick Reference

Each competency query (CQ) uses specific columns. See [Data Dictionary](#data-dictionary) for full definitions.

| CQ | Question | Required Columns |
|----|----------|------------------|
| CQ1 | Culture conditions for high productivity | `Temperature`, `pH`, `DissolvedOxygen`, `Productivity` |
| CQ2 | CHO lines overexpressing genes | `CellLine` (CHO*), `Producer`, `ProductType` |
| CQ3 | Nutrients for viability at day 6 | `CellLine`, `GlutamineConcentration`, `CollectionDay`, `ViableCellDensity` |
| CQ4 | Expression between clones | `CellLine`, `CloneID`, `CulturePhase` + expression matrix |
| CQ5 | Process type counts | `ProcessType` |
| CQ6 | Genes correlated with productivity | `CulturePhase`, `Productivity` + expression matrix |
| CQ7 | Genes by viability threshold | `ViabilityPercentage` + expression matrix |
| CQ8 | Cell lines for quality profiles | `CellLine`, `CloneID`, `TiterValue`, `QualityType` |

### Design Decision: Single Table vs. Normalized Schema

**We chose a single flat table (`sample_metadata.csv`) because:**

1. **Curation simplicity**: Domain experts can edit in Excel/Google Sheets without 
joins
2. **1:1 relationships**: Most bioprocessing studies have one run → one sample
3. **Sparse data**: Not every study has every column; flat tables handle this 
naturally
4. **Expression is separate**: The high-dimensional gene expression data is already 
in its own matrix file

**Trade-offs accepted:**
- Wide tables with many columns (36)
- Some column redundancy across rows (e.g., same CellLine repeated)
- Not ideal for complex many-to-many relationships

**If you need normalized schema later:**
- The RDF output IS normalized (each entity is a distinct node)
- You could create `studies.csv`, `runs.csv`, `samples.csv` and modify `build_graph.
py`
- For now, the flat approach works well for <1000 samples per study

---

### Implementation Notes

1. **Empty values are OK**: The csv_to_rdf.py converter handles missing/NA values 
gracefully. Adding empty columns won't break existing data.

2. **Multi-valued fields**: If a sample has multiple quality types, use 
semicolon-separated values (e.g., `"Glycosylation;Aggregation"`).

3. **Gene expression data**: See [Expression Data](#expression-data) section above. Creates one `mcbo:GeneExpressionMeasurement` per gene-sample pair.

4. **Quality measurements**: `QualityType` values include Glycosylation, Aggregation, ChargeVariants, etc.

## Running as Python Modules

Commands can also be run as Python modules:

```bash
python -m mcbo.csv_to_rdf --help
python -m mcbo.build_graph --help
python -m mcbo.run_eval --help
python -m mcbo.stats_eval_graph --help
```

