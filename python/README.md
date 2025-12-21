# MCBO Python Package

📖 **Full documentation: https://mcbo.readthedocs.io/en/latest/api.html**

## Installation

```bash
pip install -e python/
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `mcbo-csv-to-rdf` | Convert CSV metadata to RDF |
| `mcbo-build-graph` | Build graphs from studies |
| `mcbo-run-eval` | Run SPARQL competency queries |
| `mcbo-stats` | Generate graph statistics |

## Quick Usage

```bash
mcbo-build-graph build --data-dir data.sample
mcbo-run-eval --data-dir data.sample
mcbo-stats --data-dir data.sample
```

For complete API documentation and library usage examples, see the [API Reference](https://mcbo.readthedocs.io/en/latest/api.html).
