# CQ Data Requirements

This document maps each Competency Question (CQ) to the CSV columns required to support it in the evaluation graph.

## Data Workflow

### Directory Structure for Studies

```
data/studies/
  study_001/
    sample_metadata.csv      # Required
    expression_matrix.csv    # Optional (genes as columns)
  study_002/
    sample_metadata.csv
    expression_matrix.csv
  ...
```

### Workflow 1: Add Studies Incrementally

```bash
# Add first study
python python/build_graph.py add-study \
  --study-dir .data/studies/study_001 \
  --instances .data/processed/mcbo_instances.ttl

# Add another study (appends to existing)
python python/build_graph.py add-study \
  --study-dir .data/studies/study_002 \
  --instances .data/processed/mcbo_instances.ttl

# Merge with ontology to create graph.ttl
python python/build_graph.py merge \
  --ontology ontology/mcbo.owl.ttl \
  --instances .data/processed/mcbo_instances.ttl \
  --output .data/graph.ttl

# Evaluate
python python/run_eval.py \
  --graph .data/graph.ttl \
  --queries eval/queries \
  --results .data/results
```

### Workflow 2: Full Rebuild from All Studies

```bash
# Process all studies and merge with ontology in one step
python python/build_graph.py build \
  --studies-dir .data/studies \
  --ontology ontology/mcbo.owl.ttl \
  --instances .data/processed/mcbo_instances.ttl \
  --output .data/graph.ttl

# Evaluate
python python/run_eval.py \
  --graph .data/graph.ttl \
  --queries eval/queries \
  --results .data/results
```

### Demo Data Workflow

```bash
# Build and evaluate demo data
python python/build_graph.py build \
  --studies-dir data.sample/studies \
  --output data.sample/graph.ttl

python python/run_eval.py \
  --graph data.sample/graph.ttl \
  --queries eval/queries \
  --results data.sample/results
```

---

## Summary: New Columns Needed

The following 10 columns should be added to `data/sample_metadata.csv` (empty values are fine; the converter handles missing data):

| Column | Type | Required For | Description |
|--------|------|--------------|-------------|
| `pH` | decimal | CQ1 | Culture medium pH |
| `DissolvedOxygen` | decimal | CQ1 | Dissolved oxygen (% saturation or mg/L) |
| `CollectionDay` | integer | CQ3 | Day of culture when sample was collected |
| `ViableCellDensity` | decimal | CQ3 | Viable cell density (cells/mL) |
| `ViabilityPercentage` | decimal | CQ7 | Cell viability as percentage (0-100) |
| `CloneID` | string | CQ4, CQ8 | Unique clone identifier (e.g., Clone_A, Clone_B) |
| `OverexpressedGene` | string | CQ2 | Gene the cell line overexpresses (engineering) |
| `GeneSymbol` | string | CQ4, CQ6, CQ7 | Gene symbol for expression measurements |
| `ExpressionValue` | decimal | CQ4, CQ6, CQ7 | Gene expression value (e.g., TPM, FPKM) |
| `TiterValue` | decimal | CQ8 | Product titer (e.g., mg/L) |
| `QualityType` | string | CQ8 | Quality attribute type (e.g., Glycosylation, Aggregation) |

## Detailed CQ-to-Column Mapping

### CQ1: Culture conditions for HIGH productivity samples
**Query**: What culture conditions (temperature, pH, DO) are associated with high productivity?

| Column | Status | Notes |
|--------|--------|-------|
| `Temperature` | ✅ Exists | Used in current csv_to_rdf.py |
| `pH` | ❌ **NEW** | Add to CSV |
| `DissolvedOxygen` | ❌ **NEW** | Add to CSV |
| `Productivity` | ✅ Exists | Categorical: High/Medium/Low/VeryHigh |
| `ProcessType` | ✅ Exists | Used to identify CellCultureProcess subtypes |

### CQ2: Overexpression / CHO engineering
**Query**: Which CHO cell lines overexpress gene X for producing therapeutic protein Y?

| Column | Status | Notes |
|--------|--------|-------|
| `CellLine` | ✅ Exists | |
| `Producer` | ✅ Exists | Boolean: TRUE if producer line |
| `ProductType` | ✅ Exists | Product name (mAb, BsAb, or gene symbol) |

### CQ3: Nutrient concentrations for viability at day 6
**Query**: Which nutrient concentrations in cell line K are most associated with viable cell density above Z at day 6?

| Column | Status | Notes |
|--------|--------|-------|
| `CellLine` | ✅ Exists | |
| `Glutamine` | ✅ Exists | Boolean presence |
| `GlutamineConcentration` | ✅ Exists | Numeric (mM) |
| `CollectionDay` | ❌ **NEW** | Integer: day of sample collection |
| `ViableCellDensity` | ❌ **NEW** | Decimal: cells/mL |

### CQ4: Gene expression between clones
**Query**: How does the expression of gene X vary between clone A and clone B?

| Column | Status | Notes |
|--------|--------|-------|
| `CellLine` | ✅ Exists | Base cell line |
| `CloneID` | ❌ **NEW** | Specific clone within cell line |
| `GeneSymbol` | ❌ **NEW** | Gene being measured |
| `ExpressionValue` | ❌ **NEW** | Expression level (TPM/FPKM/etc.) |
| `CulturePhase` | ✅ Exists | For comparing at same phase |

### CQ5: Process types comparison
**Query**: How many processes of each type (Fed-batch vs Perfusion)?

| Column | Status | Notes |
|--------|--------|-------|
| `ProcessType` | ✅ Exists | Batch/FedBatch/Perfusion/Continuous |

**Status**: ✅ Fully supported

### CQ6: Genes correlated with productivity in stationary phase
**Query**: Which genes are most correlated with recombinant protein productivity in stationary phase?

| Column | Status | Notes |
|--------|--------|-------|
| `CulturePhase` | ✅ Exists | Filter for "Stationary" or "Stat" |
| `Productivity` | ✅ Exists | |
| `GeneSymbol` | ❌ **NEW** | Gene being measured |
| `ExpressionValue` | ❌ **NEW** | Expression level |

### CQ7: Genes with fold change by viability
**Query**: Which genes have the highest fold change between cells with viability >90% vs <50%?

| Column | Status | Notes |
|--------|--------|-------|
| `ViabilityPercentage` | ❌ **NEW** | Cell viability as percentage |
| `GeneSymbol` | ❌ **NEW** | Gene being measured |
| `ExpressionValue` | ❌ **NEW** | Expression level |

### CQ8: Cell lines for glycosylation profiles
**Query**: Which cell lines or subclones are best suited for glycosylation profiles required for therapeutic protein X?

| Column | Status | Notes |
|--------|--------|-------|
| `CellLine` | ✅ Exists | |
| `CloneID` | ❌ **NEW** | Specific clone |
| `ProductType` | ✅ Exists | Therapeutic protein name |
| `TiterValue` | ❌ **NEW** | Product titer |
| `QualityType` | ❌ **NEW** | Quality attribute (e.g., "Glycosylation") |

## Design Decision: Single Table vs. Normalized Schema

**We chose a single flat table (`sample_metadata.csv`) because:**

1. **Curation simplicity**: Domain experts can edit in Excel/Google Sheets without joins
2. **1:1 relationships**: Most bioprocessing studies have one run → one sample
3. **Sparse data**: Not every study has every column; flat tables handle this naturally
4. **Expression is separate**: The high-dimensional gene expression data is already in its own matrix file

**Trade-offs accepted:**
- Wide tables with many columns (37+)
- Some column redundancy across rows (e.g., same CellLine repeated)
- Not ideal for complex many-to-many relationships

**If you need normalized schema later:**
- The RDF output IS normalized (each entity is a distinct node)
- You could create `studies.csv`, `runs.csv`, `samples.csv` and modify `build_graph.py`
- For now, the flat approach works well for <1000 samples per study

---

## Implementation Notes

1. **Empty values are OK**: The csv_to_rdf.py converter handles missing/NA values gracefully. Adding empty columns won't break existing data.

2. **Multi-valued fields**: If a sample has multiple quality types, use semicolon-separated values (e.g., `"Glycosylation;Aggregation"`).

3. **Gene expression data**: For real RNA-seq data with thousands of genes per sample, use a separate **expression matrix file**:

   ```bash
   python python/csv_to_rdf.py \
     --csv_file data/sample_metadata.csv \
     --expression_matrix data/expression_matrix.csv \
     --output_file data/processed/mcbo_instances.ttl
   ```

   Expression matrix format (genes as columns, samples as rows):
   ```csv
   SampleAccession,GeneX,GeneY,GeneZ,ACTB,GAPDH
   ERS4805133,150,200,50,1000,800
   ERS4805134,180,220,45,950,850
   ```

   This creates one `mcbo:GeneExpressionMeasurement` per gene-sample pair, all linked via `mcbo:hasGeneExpression`.

4. **Quality measurements**: The `QualityType` column could contain values like "Glycosylation", "Aggregation", "ChargeVariants", etc.

