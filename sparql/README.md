# SPARQL QC Queries

This directory contains SPARQL queries used for ontology quality control (QC) via [ROBOT](http://robot.obolibrary.org/).

## Queries

| Query | Purpose |
|-------|---------|
| `orphan_classes.rq` | Finds classes without parent classes (orphans) |
| `duplicate_labels.rq` | Finds classes with duplicate `rdfs:label` values |
| `missing_definitions.rq` | Finds classes missing `obo:IAO_0000115` (definition) annotations |

## Running QC Manually

### Prerequisites

ROBOT must be installed at `.robot/robot.jar`. See [README_SETUP.md](../README_SETUP.md) for installation.

### Commands

Run from repository root:

```bash
# Check for orphan classes
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/orphan_classes.rq \
  reports/robot/orphan_classes.tsv

# Check for duplicate labels
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/duplicate_labels.rq \
  reports/robot/duplicate_labels.tsv

# Check for missing definitions
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/missing_definitions.rq \
  reports/robot/missing_definitions.tsv
```

### Interpreting Results

- **QC passes** if the output TSV contains only a header row (no data rows)
- **QC warns** if the output TSV contains data rows (issues found)

View results:
```bash
# Count issues (subtract 1 for header)
wc -l reports/robot/*.tsv

# View specific issues
cat reports/robot/orphan_classes.tsv
```

## Automated QC

For automated QC that runs all checks plus evaluation:

```bash
bash scripts/run_all_checks.sh
```

This runs:
1. Ontology parsing verification
2. All ROBOT QC queries (above)
3. Demo data evaluation
4. Real data evaluation + QC (if `.data/` exists)

## Running QC on Data Graphs

You can also run QC on merged graphs (ontology + instances):

```bash
# QC on real data graph
java -jar .robot/robot.jar query \
  --input .data/graph.ttl \
  --query sparql/orphan_classes.rq \
  reports/robot/real_data/orphan_classes.tsv
```

Reports for real data graphs are saved to `reports/robot/real_data/`.

