# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

📖 **Full documentation: https://mcbo.readthedocs.io/**

## Project Overview

MCBO (Mammalian Cell Bioprocessing Ontology) is a hub-and-spoke, IOF-anchored application ontology for mammalian cell bioprocessing and RNA-seq data curation. Built on BFO foundations with IOF process patterns.

## Quick Commands

```bash
make install       # Install mcbo package
make demo          # Build and evaluate demo data
make qc            # Run ROBOT QC checks
make all           # Run demo + qc (default)
make real          # Build and evaluate real data (.data/)
make docs          # Build Sphinx documentation
```

## CLI Tools

| Command | Description |
|---------|-------------|
| `mcbo-csv-to-rdf` | Convert CSV to RDF instances |
| `mcbo-build-graph` | Build graphs (bootstrap, build, merge, add-study) |
| `mcbo-run-eval` | Run SPARQL competency queries |
| `mcbo-stats` | Generate graph statistics |

## Key Patterns

See [Ontology Design](https://mcbo.readthedocs.io/en/latest/ontology.html) for the BFO-compliant process–participant–quality chain pattern.

## Directory Structure

```
mcbo/
├── ontology/           # MCBO ontology (TBox)
├── python/             # Python package with CLI
├── eval/queries/       # Competency question SPARQL queries
├── sparql/             # QC queries for ROBOT
├── data.sample/        # Demo data (public)
├── .data/              # Real data (git-ignored)
└── docs/               # Sphinx documentation
```

## Important Notes

- Instance data generated from CSV via `mcbo-csv-to-rdf`
- Merged graphs (TBox + ABox) required for `rdfs:subClassOf*` queries
- Demo: `data.sample/graph.ttl`; Real: `.data/graph.ttl` (git-ignored)

For complete details, see https://mcbo.readthedocs.io/
