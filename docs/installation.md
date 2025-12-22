# Installation

This guide covers setting up the MCBO development environment.

## Prerequisites

- **Conda** or **Miniconda** (for environment management), which will install:
- **Python 3.9+** (3.10 recommended)
- **Java** (for ROBOT ontology tool)

## Creating the Conda Environment

1. Create a new conda environment named `mcbo`:

```bash
conda create -n mcbo python=3.10
```

2. Activate the environment:

```bash
conda activate mcbo
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Installing the MCBO Package

Install the `mcbo` Python package in development mode:

```bash
# From repository root
pip install -e python/

# Or using Make
make install
```

This provides the following CLI commands:

- `mcbo-csv-to-rdf` - Convert CSV metadata to RDF instances
- `mcbo-build-graph` - Build graphs from study directories
- `mcbo-run-eval` - Run SPARQL competency queries
- `mcbo-stats` - Generate graph statistics

## Installing ROBOT

ROBOT is used for ontology quality control checks. Install it to `.robot/robot.jar`:

```bash
# Using Make (recommended)
make robot

# Or manually
mkdir -p .robot
curl -L -o .robot/robot.jar \
  "https://github.com/ontodev/robot/releases/download/v1.9.6/robot.jar"
```

Verify ROBOT works:

```bash
java -jar .robot/robot.jar --version
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

