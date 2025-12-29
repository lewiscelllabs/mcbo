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

## CSV Column Reference

This section explains how to format the CSV (real data) for subsequent parsing by `mcbo-csv-to-rdf` (`--csv_file`) into the `mcbo-instances.ttl` file.

### Column Overview (36 total)

The schema has 36 columns organized into categories:

| Category | Columns | Purpose |
|----------|---------|---------|
| Identifiers | 4 | Sample/run/study IDs |
| Dataset Provenance | 8 | Source database and sequencing metadata |
| Cell Line | 6 | Cell line characteristics |
| Culture Conditions | 4 | Temperature, pH, nutrients |
| Process/Productivity | 6 | Process type and production metrics |
| Product | 3 | What the cell line produces |
| Sample State | 5 | Time-point and viability data |

### Identifier Columns

| Column | CQs | Type | Description |
|--------|-----|------|-------------|
| `RunAccession` | all | string | Unique run/process ID (e.g., ERR4319927) |
| `SampleAccession` | all | string | Unique sample ID (e.g., ERS4805133) |
| `StudyID` | all | string | Study identifier (e.g., study_dhiman) |
| `FullSampleName` | — | string | Full descriptive sample name |

### Dataset Provenance Columns

| Column | CQs | Type | Description |
|--------|-----|------|-------------|
| `DatasetAccession` | — | string | Database accession (e.g., ERP122753, SRP066848) |
| `DatasetReadable` | — | string | Human-readable dataset ID |
| `DatasetName` | — | string | Dataset name (e.g., Dhiman, vanWijk) |
| `DatasetAbbrev` | — | string | Dataset abbreviation (e.g., D, vW) |
| `Author` | — | string | Lead author name |
| `LibraryStrategy` | — | string | Sequencing library type (rRNA, PolyA) |
| `PairedEnd` | — | boolean | Paired-end sequencing (TRUE/FALSE) |
| `Source` | — | string | Data source (SRA, In-House) |

### Cell Line Columns

| Column | CQs | Type | Description |
|--------|-----|------|-------------|
| `CellLine` | 1-8 | string | Cell line name (CHO-K1, CHO-S, HEK293) |
| `Host` | — | boolean | Is this a host/parental line (TRUE/FALSE) |
| `CellLineSource` | — | enum | Commercial vs Non-Commercial |
| `CellLineExact` | — | string | Specific source (ATCC, Horizon, Life Technologies) |
| `SelectionMarker` | — | string | Selection marker (GS+/-, GS-/-, ProcessEvolved) |
| `Growth` | — | enum | Growth rate (Low/Medium/High) |

### Culture Condition Columns

| Column | CQs | Type | Description |
|--------|-----|------|-------------|
| `Temperature` | 1 | decimal | Culture temperature (°C) |
| `pH` | 1 | decimal | Culture medium pH |
| `DissolvedOxygen` | 1 | decimal | Dissolved oxygen (% saturation) |
| `Glutamine` | — | boolean | Glutamine present (TRUE/FALSE) |
| `GlutamineConcentration` | 3 | decimal | Glutamine concentration (mM) |

### Process and Productivity Columns

| Column | CQs | Type | Description |
|--------|-----|------|-------------|
| `ProcessType` | 5 | enum | Batch, FedBatch, Perfusion |
| `CulturePhase` | 4, 6 | enum | EarlyExp, MidExp, LateExp, Stationary |
| `Productivity` | 1, 6 | enum | VeryHigh/High/Medium/Low |
| `Stability` | — | boolean | Stable expression (TRUE/FALSE) |
| `TiterValue` | 8 | decimal | Product titer (mg/L) |
| `QualityType` | 8 | string | Quality attribute (Glycosylation, Aggregation) |

### Product Columns

| Column | CQs | Type | Description |
|--------|-----|------|-------------|
| `Producer` | 2 | boolean | TRUE if producer line |
| `ProductType` | 2, 8 | string | Product: gene symbol (AMBP), class (mAb), or Control |
| `EnsemblGeneID` | — | string | Ensembl ID when ProductType is a gene symbol |

### Sample State Columns

| Column | CQs | Type | Description |
|--------|-----|------|-------------|
| `CollectionDay` | 3 | integer | Day of sample collection |
| `ViableCellDensity` | 3 | decimal | Viable cells/mL |
| `ViabilityPercentage` | 7 | decimal | Cell viability % |
| `CloneID` | 4, 8 | string | Clone identifier |

### ProductType Classification

The `ProductType` column determines product class:

| ProductType Value | RDF Class | Example |
|-------------------|-----------|---------|
| Gene symbol (all caps, 2-10 chars) | `ProteinProduct` + `encodedByGene` | AMBP, CCL20, FN1 |
| Antibody terms | `AntibodyProduct` | mAb, IgG, BsAb, bispecific |
| Control terms | (skipped) | Control, WT, Mock |

When `ProductType` is a gene symbol, provide `EnsemblGeneID` for the Ensembl stable ID.

### Expression Data

Gene expression data comes from **separate matrix files**, not metadata columns:

```csv
SampleAccession,ACTB,GAPDH,TP53
DEMO001_SAMPLE_A,1000,800,250
```

Gene annotations (Ensembl IDs for expression genes) go in `gene_annotations.csv`.



### Detailed CQ-to-Column Mapping

#### CQ1: Culture conditions for HIGH productivity samples
**Query**: What culture conditions (temperature, pH, DO) are associated with high 
productivity?

| Column | Status | Notes |
|--------|--------|-------|
| `Temperature` | ✅ Exists | Used in current csv_to_rdf.py |
| `pH` | ❌ **NEW** | Add to CSV |
| `DissolvedOxygen` | ❌ **NEW** | Add to CSV |
| `Productivity` | ✅ Exists | Categorical: High/Medium/Low/VeryHigh |
| `ProcessType` | ✅ Exists | Used to identify CellCultureProcess subtypes |

#### CQ2: Overexpression / CHO engineering
**Query**: Which CHO cell lines overexpress gene X for producing therapeutic 
protein Y?

| Column | Status | Notes |
|--------|--------|-------|
| `CellLine` | ✅ Exists | |
| `Producer` | ✅ Exists | Boolean: TRUE if producer line |
| `ProductType` | ✅ Exists | Product name (mAb, BsAb, or gene symbol) |

#### CQ3: Nutrient concentrations for viability at day 6
**Query**: Which nutrient concentrations in cell line K are most associated with 
viable cell density above Z at day 6?

| Column | Status | Notes |
|--------|--------|-------|
| `CellLine` | ✅ Exists | |
| `Glutamine` | ✅ Exists | Boolean presence |
| `GlutamineConcentration` | ✅ Exists | Numeric (mM) |
| `CollectionDay` | ❌ **NEW** | Integer: day of sample collection |
| `ViableCellDensity` | ❌ **NEW** | Decimal: cells/mL |

#### CQ4: Gene expression between clones
**Query**: How does the expression of gene X vary between clone A and clone B?

| Column | Status | Notes |
|--------|--------|-------|
| `CellLine` | ✅ Exists | Base cell line |
| `CloneID` | ❌ **NEW** | Specific clone within cell line |
| `GeneSymbol` | ❌ **NEW** | Gene being measured |
| `ExpressionValue` | ❌ **NEW** | Expression level (TPM/FPKM/etc.) |
| `CulturePhase` | ✅ Exists | For comparing at same phase |

#### CQ5: Process types comparison
**Query**: How many processes of each type (Fed-batch vs Perfusion)?

| Column | Status | Notes |
|--------|--------|-------|
| `ProcessType` | ✅ Exists | Batch/FedBatch/Perfusion/Continuous |

**Status**: ✅ Fully supported

#### CQ6: Genes correlated with productivity in stationary phase
**Query**: Which genes are most correlated with recombinant protein productivity in 
stationary phase?

| Column | Status | Notes |
|--------|--------|-------|
| `CulturePhase` | ✅ Exists | Filter for "Stationary" or "Stat" |
| `Productivity` | ✅ Exists | |
| `GeneSymbol` | ❌ **NEW** | Gene being measured |
| `ExpressionValue` | ❌ **NEW** | Expression level |

#### CQ7: Genes with fold change by viability
**Query**: Which genes have the highest fold change between cells with viability 
>90% vs <50%?

| Column | Status | Notes |
|--------|--------|-------|
| `ViabilityPercentage` | ❌ **NEW** | Cell viability as percentage |
| `GeneSymbol` | ❌ **NEW** | Gene being measured |
| `ExpressionValue` | ❌ **NEW** | Expression level |

#### CQ8: Cell lines for glycosylation profiles
**Query**: Which cell lines or subclones are best suited for glycosylation profiles 
required for therapeutic protein X?

| Column | Status | Notes |
|--------|--------|-------|
| `CellLine` | ✅ Exists | |
| `CloneID` | ❌ **NEW** | Specific clone |
| `ProductType` | ✅ Exists | Therapeutic protein name |
| `TiterValue` | ❌ **NEW** | Product titer |
| `QualityType` | ❌ **NEW** | Quality attribute (e.g., "Glycosylation") |

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

3. **Gene expression data**: For real RNA-seq data with thousands of genes per 
sample, use a separate **expression matrix file**:

   ```bash
   mcbo-csv-to-rdf \
     --csv_file data/sample_metadata.csv \
     --expression_matrix data/expression_matrix.csv \
     --output_file data/mcbo-instances.ttl
   ```

   Expression matrix format (genes as columns, samples as rows):
   ```csv
   SampleAccession,GeneX,GeneY,GeneZ,ACTB,GAPDH
   ERS4805133,150,200,50,1000,800
   ERS4805134,180,220,45,950,850
   ```

   This creates one `mcbo:GeneExpressionMeasurement` per gene-sample pair, all 
   linked via `mcbo:hasGeneExpression`.

4. **Quality measurements**: The `QualityType` column could contain values like 
"Glycosylation", "Aggregation", "ChargeVariants", etc.


### Expression Matrix Format

For gene expression data (CQ4, CQ6, CQ7), use a separate CSV file:

```text
SampleAccession,GeneX,GeneY,GeneZ,ACTB,GAPDH
ERS4805133,150,200,50,1000,800
ERS4805134,180,220,45,950,850
```

- First column must be `SampleAccession` (matching metadata CSV)
- Remaining columns are gene symbols
- Values are expression levels (TPM, FPKM, etc.)

## Running as Python Modules

Commands can also be run as Python modules:

```bash
python -m mcbo.csv_to_rdf --help
python -m mcbo.build_graph --help
python -m mcbo.run_eval --help
python -m mcbo.stats_eval_graph --help
```

