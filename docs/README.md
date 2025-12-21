# MCBO Documentation

📖 **Read the full documentation: https://mcbo.readthedocs.io/**

## Building Locally

```bash
# Install docs dependencies (in mcbo environment)
pip install -r docs/requirements.txt

# Build
make docs
```

Output: `docs/_build/html/index.html`

## Structure

| File | Description |
|------|-------------|
| `index.rst` | Landing page |
| `installation.rst` | Setup guide |
| `quickstart.rst` | Getting started |
| `workflows.rst` | Data ingestion |
| `cli.rst` | CLI reference |
| `ontology.rst` | Modeling patterns |
| `api.rst` | Python API |
| `development.rst` | Contributing |

## ReadTheDocs

Documentation automatically deploys via ReadTheDocs webhook on push to main. Configuration: `.readthedocs.yaml`
