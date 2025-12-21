# MCBO - Mammalian Cell Bioprocessing Ontology

[![CI/CD](https://github.com/lewiscelllabs/mcbo/actions/workflows/qc.yml/badge.svg)](https://github.com/lewiscelllabs/mcbo/actions/workflows/qc.yml)
[![Documentation Status](https://readthedocs.org/projects/mcbo/badge/?version=latest)](https://mcbo.readthedocs.io/en/latest/?badge=latest)
[![YouTube](https://img.shields.io/badge/YouTube-Video-red?logo=youtube)](https://youtu.be/YTvCv-l0ia4)

A hub-and-spoke, IOF-anchored application ontology for mammalian cell bioprocessing and RNA-seq data curation.

📖 **[Full Documentation](https://mcbo.readthedocs.io/)**

## Term Requests

Please click [New Term Request](https://github.com/lewiscelllabs/mcbo/issues/new?template=mcbo-term-request.md) to submit your request.

(Issues > New Issue > MCBO Term Request)


## Quick Start

**Pre-requisites**: 
- Python 3.9+ (3.10 recommended)
- Conda (for environment management)
- Java (for ROBOT ontology tool)

```bash
make conda-env
conda activate mcbo
make install
make demo
```

See the [Installation Guide](https://mcbo.readthedocs.io/en/latest/installation.html) for detailed setup instructions.

## Ontology Overview
<img width="2561" height="1781" alt="MCBO Ontology Diagram" src="https://github.com/user-attachments/assets/781c1af6-8238-45a3-b26b-c6c9010dd77e" />

## Competency Questions

MCBO supports 8 competency questions.

See the [full CQ documentation](https://mcbo.readthedocs.io/en/latest/index.html#competency-questions).

## Documentation

| Section | Description |
|---------|-------------|
| [Installation](https://mcbo.readthedocs.io/en/latest/installation.html) | Environment setup and dependencies |
| [Quick Start](https://mcbo.readthedocs.io/en/latest/quickstart.html) | Run the demo in minutes |
| [Workflows](https://mcbo.readthedocs.io/en/latest/workflows.html) | Data ingestion scenarios |
| [CLI Reference](https://mcbo.readthedocs.io/en/latest/cli.html) | Command-line tools and CSV columns |
| [Ontology Design](https://mcbo.readthedocs.io/en/latest/ontology.html) | Modeling patterns and architecture |
| [API Reference](https://mcbo.readthedocs.io/en/latest/api.html) | Python package documentation |
| [Development](https://mcbo.readthedocs.io/en/latest/development.html) | Contributing and QC checks |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Citation

> Robasky, K., Morrissey, J., Riedl, M., Dräger, A., Borth, N., Betenbaugh, M. J., & Lewis, N. E. (2025). 
> MCBO: Mammalian Cell Bioprocessing Ontology, A Hub-and-Spoke, IOF-Anchored Application Ontology.
> *ICBO-EAST 2025*.
---

