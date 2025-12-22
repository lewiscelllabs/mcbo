# MCBO Setup Instructions

📖 **Full documentation: https://mcbo.readthedocs.io/en/latest/installation.html**

## Quick Setup

```bash
make conda-env         # Creates conda env with Python + Java
conda activate mcbo
make install           # Installs Python packages + downloads ROBOT
make demo              # Verify setup with demo data
```

This sets up everything you need including:
- Python dependencies from `requirements.txt`
- The `mcbo` CLI tools
- ROBOT ontology tool (at `.robot/robot.jar`)

For troubleshooting, see the [Installation Guide](https://mcbo.readthedocs.io/en/latest/installation.html).
