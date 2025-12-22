# Installation

This guide covers setting up the MCBO development environment.

## Prerequisites

- **Conda** or **Miniconda** 

Conda is used in `make conda-env` to install:
- **Python 3.9+** (3.10 recommended)
- **Java** (for ROBOT ontology tool)
- **robot**

## Creating the Conda Environment

1. Create a new conda environment named `mcbo`:

```bash
make conda-env
```

2. Activate the environment:

```bash
conda activate mcbo
```

## Installing the MCBO Package

Install the `mcbo` Python package and ROBOT:

```bash
# Using Make (recommended) - installs Python packages + ROBOT
make install
```

This provides the following CLI commands:

- `mcbo-csv-to-rdf` - Convert CSV metadata to RDF instances
- `mcbo-build-graph` - Build graphs from study directories
- `mcbo-run-eval` - Run SPARQL competency queries
- `mcbo-stats` - Generate graph statistics

## ROBOT

ROBOT is automatically downloaded by `make install`. It's used for ontology quality control checks and is located at `.robot/robot.jar`.

To verify ROBOT works:

```bash
java -jar .robot/robot.jar --version
```

To re-download manually:

```bash
make robot
```

## Verifying Installation

Run the demo workflow to verify everything is set up correctly:

```bash
# Activate environment
conda activate mcbo

# Run the full demo
make demo
```

This will:

1. Build the demo graph from `data.sample/`
2. Run all 8 competency question queries
3. Display statistics and results

You should see output ending with:

```text
✅ Demo data processing complete
   Graph: data.sample/graph.ttl
   Results: data.sample/results/
```

## Dependencies

### Core Python Dependencies

- `rdflib>=7.0.0` - RDF graph manipulation
- `pandas>=1.5.0` - Data processing

### External Tools

- **Java** - Required for ROBOT (JRE 8+)
- **ROBOT** - Ontology tool for QC queries (located at `.robot/robot.jar`)

See `requirements.txt` for the complete list of Python dependencies.

