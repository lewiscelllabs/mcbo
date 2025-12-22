# MCBO Manuscript Fix List

This document provides precise section-by-section edits to address reviewer concerns in the manuscript.

## 1. Add "Modeling Patterns" Subsection

**Location:** After "Ontology Development" section, before "Evaluation" section

**Content to add:**

### Modeling Patterns

MCBO follows BFO-compliant semantic patterns to ensure interoperability with OBO Foundry ontologies. The core pattern for culture conditions uses the process–participant–quality chain:

- A bioprocess (e.g., `BatchCultureProcess`, `FedBatchCultureProcess`) is a `BFO:process` instance
- The process `RO:0000057` (has participant) a `CellCultureSystem` (a `BFO:material entity`)
- The `CellCultureSystem` `RO:0000086` (has quality) a `CultureConditionQuality` instance (a `BFO:quality`)
- Temperature, pH, and dissolved oxygen values are attached as datatype properties to the `CultureConditionQuality` instance

This pattern preserves BFO semantics: processes have material entity participants, which bear qualities. It avoids direct process-to-quality links that would conflict with BFO's occurrent–continuant distinction.

**Diagram suggestion:** Include a figure showing:
```
Process (BFO:process)
  └─ RO:0000057 (has participant) → CellCultureSystem (BFO:material entity)
      └─ RO:0000086 (has quality) → CultureConditionQuality (BFO:quality)
          ├─ hasTemperature (xsd:decimal)
          ├─ hasPH (xsd:decimal)
          └─ hasDissolvedOxygen (xsd:decimal)
```

## 2. Update Evaluation Section

**Location:** Evaluation / Case Study section

**Verified statistics** (from `mcbo-stats --graph .data/graph.ttl`):
```
Cell Culture Process Instances: 724
  Breakdown by type:
    Batch culture process: 518
    Fed-batch culture process: 135
    Perfusion culture process: 49
    Unknown culture process: 22

Bioprocess Sample Instances: 326
```

**Note:** 724 processes but only 326 unique samples because many runs share the same sample accession.

**Changes:**
- Change "725 samples" → "724 cell culture processes" (or "724 curated runs")
- Update process breakdown: "Batch (518), Fed-batch (135), Perfusion (49), Unknown (22)"
- Clarify: "326 unique bioprocess samples across 724 culture process runs"

**Add reproducibility paragraph:**

All 8 competency question SPARQL queries are available in the repository (`eval/queries/cq1.rq` through `cq8.rq`). Query results are provided in `data.sample/results/*.tsv` for the demo data and `.data/results/*.tsv` for the real curated data. The evaluation graph is generated from study data using `mcbo-build-graph` and evaluated with `mcbo-run-eval`. Reviewers can reproduce results by building the demo graph (`data.sample/graph.ttl`) without access to private data.

**Note on sample vs. real data:** The sample graph includes demonstration data for all 8 CQs, including some fields (e.g., nutrient concentrations, clone relationships, gene expression measurements) that may not yet be fully populated in the real curated dataset. This allows reviewers to see the full query capabilities even if the real data is still being curated. CQ3 and CQ6 may return 0 results on the real data until additional curation is completed, but the queries are implemented and validated.

## X MET --3. Reorganize Sections (LOT Methodology)

**Current order (if not already):** Background → Design → Scope → Development → Evaluation → Discussion

**Recommended order (LOT):**
1. **Scope & Competency Questions** (what the ontology covers, CQ list)
2. **Reuse Policy** (which ontologies are reused: IOF, BFO, OBI, IAO, CLO, etc.)
3. **Modeling Patterns** (semantic design patterns, see #1 above)
4. **Implementation** (Protégé, ROBOT, TTL/OWL deliverables)
5. **Evaluation** (724 samples, CQ results, performance)
6. **Discussion** (benefits, limitations, lessons learned)

## 4. Clarify Scope: Mammalian vs Non-Mammalian

**Location:** Scope section or Introduction

**Add explicit statement:**

MCBO focuses on mammalian cell bioprocessing, with primary application to Chinese Hamster Ovary (CHO) and Human Embryonic Kidney 293 (HEK293) cell lines. While the ontology includes a general `CellCultureProcess` class, the primary scope is indicated by the `MammalianCellBioprocess` and `MammalianCellCultureProcess` classes. Non-mammalian cell culture processes (e.g., yeast, bacterial) are explicitly out of scope for this version of MCBO.

## 5. Justify IOF PPP vs BFO:process Classification

**Location:** Modeling Decisions or Ontology Development section

**Add justification:**

MCBO process classes (e.g., `CellCultureProcess`, `MammalianCellBioprocess`) are direct subclasses of `BFO:process` to maintain strict BFO alignment and interoperability with OBO Foundry ontologies. We use `rdfs:seeAlso` annotations to `iof:ManufacturingProcess` and `iof:ProductProductionProcess` to indicate conceptual alignment with IOF manufacturing concepts, while preserving direct BFO classification. This approach ensures compatibility with both BFO-based biomedical ontologies and IOF-based industrial ontologies.

## MET - 6. Fix License Terminology

**Location:** Anywhere "permissive license" appears

**Change:** "permissive license" → "MIT License"

**Verification:** Search manuscript for "permissive" and ensure consistency with LICENSE file.

## MET -- 7. Terminology: "Biomanufacturing" vs "Biopharmaceutical Manufacturing"

**Location:** Throughout manuscript

**Decision needed:** 
- If scope is specifically biopharmaceuticals: use "biopharmaceutical manufacturing" consistently
- If scope includes broader biomanufacturing: clarify in scope section that MCBO focuses on biopharmaceutical manufacturing but the framework could extend to other biomanufacturing domains

**Action:** Review all instances and make consistent choice, or add clarification paragraph.

## MET -- 8. Soften/Remove LLM Claims

**Location:** Anywhere LLM usage is mentioned (e.g., Introduction, Future Work)

**Current (if present):** "LLMs for automating the generation of structured metadata"

**Revised:** "Future work may explore LLM-assisted metadata extraction from unstructured publications and electronic notebooks. The current implementation relies on structured CSV-to-RDF conversion pipelines."

**Or remove entirely** if no LLM work has been done.

## 9. Add Dataset Classification Clarification

**Location:** Ontology Development or Modeling Decisions section

**Add note:**

All dataset classes (e.g., `RNASeqDataset`, `RawReadsDataset`, `AlignedReadsDataset`) are subclasses of `IAO:dataset` (IAO_0000100), which is an information content entity (ICE) in the BFO/IAO hierarchy. This ensures proper classification: datasets are ICEs, not material entities or processes.

## 10. Grammar and Wording Review

**General proofreading pass for:**
- Sentence clarity
- Consistent terminology
- Proper citation formatting
- Figure/table references
- Acronym definitions on first use

## 11. Add Sample Data for Reviewer Reproduction

**Location:** Evaluation section, after describing the 724-sample dataset

**Add paragraph:**

To enable reviewer reproduction without access to the private curated dataset, we provide a public demonstration dataset (`data.sample/`) containing three synthetic studies with 10 process runs. This sample data is structured to exercise all 8 competency questions and demonstrates the full data ingestion workflow. Table X contrasts results between the real curated data and the demonstration data:

**Demo data statistics** (from `mcbo-stats --data-dir data.sample`):
```
Cell Culture Process Instances: 10
  Breakdown by type:
    Batch culture process: 3
    Fed-batch culture process: 4
    Perfusion culture process: 3

Bioprocess Sample Instances: 10
```

**CQ Results comparison** (from `mcbo-run-eval --data-dir data.sample`):

| CQ | Real Data (724 processes) | Demo Data (10 processes) | Notes |
|----|-------------------------|----------------------|-------|
| CQ1 | 161 | 13 | Culture conditions for productivity |
| CQ2 | 3 | 2 | Overexpression engineering |
| CQ3 | 0 | 4 | Nutrient concentrations (requires CollectionDay, ViableCellDensity) |
| CQ4 | 0 | 144 | Gene expression between clones (requires expression matrix) |
| CQ5 | 4 | 3 | Process type distribution |
| CQ6 | 0 | 38 | Genes correlated with productivity (requires expression data) |
| CQ7 | 0 | 7 | Viability fold change (requires ViabilityPercentage) |
| CQ8 | 0 | 3 | Quality profiles (requires TiterValue, QualityType) |

CQs returning 0 on real data reflect ongoing curation efforts; the queries are validated and functional. The demonstration data includes all required fields to show complete functionality. Reviewers can reproduce results by running:

```bash
conda activate mcbo
pip install -e python/  # Install mcbo package (first time only)
make demo               # Build demo graph and run evaluation (recommended)

# Or manually:
mcbo-build-graph build --data-dir data.sample
mcbo-run-eval --data-dir data.sample
mcbo-stats --data-dir data.sample
```

**Rationale:** This addresses reviewer concerns about reproducibility while being transparent about the gap between demo capabilities and current real data curation state.

---

## Summary Checklist

- [ ] Add "Modeling Patterns" subsection with process–participant–quality chain
- [ ] Update all "725" → "724" in evaluation section
- [ ] Add reproducibility paragraph pointing to `eval/queries/` and `eval/results/`
- [ ] **Add sample data section with demo vs. real data comparison table**
- [x] Reorganize sections to follow LOT methodology
- [x] Add explicit mammalian scope statement
- [ ] Justify IOF PPP vs BFO:process classification
- [x] Fix "permissive license" → "MIT License"
- [x] Resolve "biomanufacturing" vs "biopharmaceutical manufacturing" terminology
- [x] Soften/remove unsupported LLM claims
- [ ] Add dataset classification clarification
- [ ] General grammar/wording proofreading pass
- [ ] Sample data section

