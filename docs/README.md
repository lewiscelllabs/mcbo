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
| `index.md` | Landing page |
| `installation.md` | Setup guide |
| `quickstart.md` | Getting started |
| `workflows.md` | Data ingestion |
| `cli.md` | CLI reference |
| `ontology.md` | Modeling patterns |
| `api.rst` | Python API |
| `development.md` | Contributing |

## ReadTheDocs

Documentation automatically deploys via ReadTheDocs webhook on push to main. Configuration: `.readthedocs.yaml`
