# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

MCBO (Mammalian Cell Bioprocessing Ontology) is a hub-and-spoke, IOF-anchored application ontology for mammalian cell bioprocessing and RNA-seq data curation. The repository includes:

- OWL ontology (TBox) in Turtle format
- Python package for data ingestion, graph building, and SPARQL evaluation
- LLM-powered agent for natural language querying
- 8 competency questions (CQs) with SPARQL implementations
- Quality control pipeline using ROBOT

## Build & Test Commands

### First-Time Setup
```bash
# Create and activate conda environment
make conda-env
conda activate mcbo

# Install Python package and ROBOT
make install
```

### Common Development Tasks
```bash
# Run full demo build and evaluation (default target)
make demo

# Run ROBOT QC checks on ontology
make qc

# Run both demo and QC
make all

# Run CI pipeline locally (install + qc + demo + verify)
make ci

# Build documentation
make docs
# View at: docs/_build/html/index.html

# Clean all generated files
make clean
```

### Data Processing
```bash
# Build knowledge graph from CSV data
mcbo-build-graph build --data-dir data.sample
# Or bootstrap from single CSV: mcbo-build-graph bootstrap --data-dir <dir>

# Run SPARQL evaluation on all 8 CQs
mcbo-run-eval --data-dir data.sample

# Generate statistics about graph content
mcbo-stats --data-dir data.sample

# Verify graph parses without running queries
mcbo-run-eval --data-dir data.sample --verify
```

### Testing
```bash
# Run agent tests (requires mock provider or API keys)
pytest python/tests/test_agent_integration.py -v

# Run statistical tools tests
pytest python/tests/test_stats_tools.py -v

# Run all tests
pytest python/tests/ -v
```

### LLM Agent
```bash
# Install agent dependencies
make install-agent

# Set API key (choose one)
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...

# Ask competency questions
mcbo-agent-eval --data-dir data.sample --cq CQ1
mcbo-agent-eval --data-dir data.sample --cq "What genes are differentially expressed under Fed-batch vs Perfusion?"

# Use local LLM (free, private)
make install-ollama
mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider ollama --model qwen2.5:3b

# Verbose mode to see tool calls
mcbo-agent-eval --data-dir data.sample --cq CQ1 --verbose
```

## Architecture

### Repository Structure
```
mcbo/
├── ontology/mcbo.owl.ttl       # OWL ontology (TBox) - hand-crafted
├── python/mcbo/                # Python package
│   ├── namespaces.py           # Shared RDF namespace definitions
│   ├── graph_utils.py          # Graph loading/creation utilities
│   ├── csv_to_rdf.py           # CSV-to-RDF conversion (instances)
│   ├── build_graph.py          # Graph builder (ontology + instances)
│   ├── run_eval.py             # SPARQL query executor
│   ├── stats_eval_graph.py     # Statistics generator
│   └── agent/                  # LLM-powered agent
│       ├── orchestrator.py     # Main agent logic, system prompt
│       ├── tools.py            # Tool definitions and executor
│       ├── sparql_templates.py # Parameterized SPARQL queries
│       ├── stats_tools.py      # Statistical analysis (correlation, fold change)
│       ├── pathway_tools.py    # Pathway enrichment (KEGG, Reactome)
│       ├── agent_eval.py       # CLI entry point
│       └── mcp_server.py       # MCP server for Claude Desktop
├── eval/queries/               # SPARQL queries for 8 CQs (cq1.rq - cq8.rq)
├── sparql/                     # QC queries for ROBOT
│   ├── orphan_classes.rq
│   ├── duplicate_labels.rq
│   └── missing_definitions.rq
├── data.sample/                # Demo data (public, checked in)
│   ├── studies/*/sample_metadata.csv  # Per-study CSV files
│   ├── graph.ttl               # Generated: merged ontology + instances
│   └── results/                # Generated: CQ evaluation results
└── .data/                      # Real data (git-ignored)
```

### Key Design Patterns

**Hub-and-Spoke Architecture**:
- Core ontology (`ontology/mcbo.owl.ttl`) defines MCBO-specific classes
- References OBO ontologies for biological entities (genes, proteins)
- Anchored to IOF (Industrial Ontology Foundational) for process modeling
- Built on BFO (Basic Formal Ontology) upper-level ontology

**Data Flow**:
1. CSV files (`studies/*/sample_metadata.csv`) contain experimental metadata
2. `csv_to_rdf.py` converts CSV to RDF instances (ABox)
3. `build_graph.py` merges ontology (TBox) + instances (ABox) → `graph.ttl`
4. `run_eval.py` executes SPARQL queries against `graph.ttl`

**Graph Building Modes**:
- **build**: Multi-study mode - processes `studies/*/sample_metadata.csv` files
- **bootstrap**: Single-study mode - processes one `sample_metadata.csv` file

### CLI Entry Points

All CLIs are defined in `python/pyproject.toml` under `[project.scripts]`:

```python
mcbo-csv-to-rdf     → mcbo.csv_to_rdf:main         # Low-level CSV→RDF converter
mcbo-build-graph    → mcbo.build_graph:main        # High-level graph builder
mcbo-run-eval       → mcbo.run_eval:main           # SPARQL evaluator
mcbo-stats          → mcbo.stats_eval_graph:main   # Statistics generator
mcbo-agent-eval     → mcbo.agent.agent_eval:main   # LLM agent
```

## Agent System

### Architecture
The agent orchestrates LLM tool-calling to answer competency questions:

1. **Orchestrator** (`orchestrator.py`): Manages conversation loop
2. **LLM Providers**: OpenAI, Anthropic, Ollama (local), Mock (testing)
3. **Tool Executor** (`tools.py`): Executes tools and returns structured results
4. **SPARQL Templates** (`sparql_templates.py`): Parameterized queries
5. **Analysis Tools**: Stats (`stats_tools.py`), Pathways (`pathway_tools.py`)

### System Prompt Structure
The system prompt in `orchestrator.py` (line 34) has three critical sections:

1. **SPARQL TEMPLATES**: Maps question types to template names
2. **WORKFLOWS**: Step-by-step instructions per CQ type
3. **CRITICAL RULES**: Anti-hallucination guardrails

### Customizing the Agent

**Adding a new SPARQL template**:
1. Add template definition to `sparql_templates.py`
2. Update `SYSTEM_PROMPT` in `orchestrator.py` to reference it
3. Define when to use it (question type → template mapping)

**Adding a new tool**:
1. Define schema in `tools.py` → `TOOL_DEFINITIONS`
2. Implement handler in `ToolExecutor._execute_single_tool()`
3. Update `SYSTEM_PROMPT` to explain when/how to use it

**Modifying workflows**:
Edit the `WORKFLOWS BY QUESTION TYPE` section in `orchestrator.py` to change how the agent approaches each CQ type.

### MCP Server Integration
The agent can run as an MCP (Model Context Protocol) server for Claude Desktop:

```bash
python -m mcbo.agent.mcp_server
```

Configuration in `~/.config/claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "mcbo": {
      "command": "python",
      "args": ["-m", "mcbo.agent.mcp_server"],
      "cwd": "/path/to/mcbo",
      "env": {"DATA_DIR": "/path/to/mcbo/data.sample"}
    }
  }
}
```

## Competency Questions

MCBO supports 8 competency questions (CQs):

- **CQ1**: Culture conditions for peak recombinant protein productivity
- **CQ2**: Cell lines engineered to overexpress specific genes
- **CQ3**: Nutrient concentrations associated with high viable cell density
- **CQ4**: Gene expression variation between clones
- **CQ5**: Differentially expressed pathways (Fed-batch vs Perfusion)
- **CQ6**: Top genes correlated with productivity in stationary phase
- **CQ7**: Genes with highest fold change by viability
- **CQ8**: Cell lines suited for specific glycosylation profiles

Each CQ has:
- SPARQL query in `eval/queries/cqN.rq`
- Natural language description in `orchestrator.py` → `CQ_DESCRIPTIONS`
- Template mapping in `sparql_templates.py` → `CQ_TEMPLATE_MAPPING`

## Quality Control

### ROBOT QC Checks
Three QC queries run via ROBOT (defined in `sparql/`):

1. **orphan_classes.rq**: Finds classes without parent classes
2. **duplicate_labels.rq**: Finds duplicate `rdfs:label` values
3. **missing_definitions.rq**: Finds classes missing IAO definition annotations

**QC passes** if TSV output has only a header row (no data rows).

Run manually:
```bash
make qc
# Or individual checks:
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/orphan_classes.rq \
  reports/robot/orphan_classes.tsv
```

### CI/CD Pipeline
GitHub Actions workflow at `.github/workflows/qc.yml` runs:
1. ROBOT QC queries on ontology
2. Demo data build and evaluation
3. Fails if QC finds issues (configurable via `FAIL_ON_FINDINGS`)

## Data Conventions

### Directory Structure
By convention, data directories follow this pattern:
```
<data-dir>/
├── studies/*/sample_metadata.csv  # Per-study CSV (for 'build' mode)
├── sample_metadata.csv            # Single CSV (for 'bootstrap' mode)
├── graph.ttl                      # Generated: merged graph
├── mcbo-instances.ttl             # Generated: instances only
├── results/                       # Generated: CQ evaluation results
│   ├── cq1.tsv, cq2.tsv, ...
│   └── SUMMARY.txt
└── STATS.txt                      # Generated: graph statistics
```

### CSV Column Names
The CSV-to-RDF converter expects specific column names (case-sensitive):

**Core columns**:
- `SampleID`, `RunID`, `CellLineLabel`, `ProcessType`
- `Temperature`, `pH`, `DissolvedOxygen`
- `ProductivityValue`, `TiterValue`, `ViabilityPercentage`

**Expression columns**:
- Gene expression: `<GeneSymbol>` (e.g., `GAPDH`, `MYC`)

**Process types** (must match ontology class labels):
- `Batch`, `Fed-batch`, `Perfusion`, `Chemostat`

See `docs/cli.md` for full column reference.

## Important Files

### Ontology
- `ontology/mcbo.owl.ttl`: Hand-crafted OWL ontology (TBox)
  - DO NOT auto-generate this file
  - Edit manually following OBO/OWL conventions
  - Must be valid Turtle syntax

### Python Package
- `python/mcbo/namespaces.py`: Central namespace registry
  - All RDF namespaces defined here
  - Import and use in other modules (don't redefine)

- `python/mcbo/graph_utils.py`: Graph utilities
  - `load_ontology()`: Loads base ontology
  - `create_new_graph()`: Creates fresh graph with namespaces

### Configuration
- `environment.yml`: Conda environment specification
  - Python 3.10 + OpenJDK (for ROBOT)
  - Core dependencies: rdflib, pandas

- `python/pyproject.toml`: Python package metadata
  - Optional dependencies: `[agent]`, `[mcp]`, `[dev]`, `[full]`
  - Use `pip install -e python/[agent]` for agent features

## Development Workflow

### Making Changes to Ontology
1. Edit `ontology/mcbo.owl.ttl` manually
2. Run `make qc` to check for issues
3. Run `make demo` to verify demo data still builds
4. Commit changes (QC reports are git-ignored)

### Adding New Competency Questions
1. Create SPARQL query in `eval/queries/cqN.rq`
2. Add description to `orchestrator.py` → `CQ_DESCRIPTIONS`
3. Add template mapping in `sparql_templates.py` → `CQ_TEMPLATE_MAPPING`
4. Update `SYSTEM_PROMPT` workflow instructions
5. Test with `mcbo-run-eval --data-dir data.sample`

### Modifying CSV Schema
1. Update `csv_to_rdf.py` to handle new columns
2. Document new columns in `docs/cli.md`
3. Add sample data to `data.sample/studies/*/sample_metadata.csv`
4. Rebuild and verify: `make clean-demo && make demo`

### Working with Real Data
Real data goes in `.data/` (git-ignored):
```bash
# Build real data graph
make real-build

# Evaluate real data
make real-eval

# Generate statistics
make real-stats

# Full pipeline
make real
```

## Testing Guidelines

### Agent Testing
The agent has two test files:

1. **`test_stats_tools.py`**: Unit tests for statistical functions
   - No LLM calls, deterministic
   - Tests correlation, fold change, differential expression

2. **`test_agent_integration.py`**: Integration tests with LLM
   - Uses MockProvider by default (no API calls)
   - Can test with real providers via env vars

Run with mock provider (fast, no API key needed):
```bash
pytest python/tests/test_agent_integration.py -v
```

### Makefile Targets Reference

| Target | Description |
|--------|-------------|
| `make help` | Show all available targets |
| `make conda-env` | Create mcbo conda environment |
| `make install` | Install Python package + ROBOT |
| `make install-agent` | Install agent dependencies |
| `make install-ollama` | Install Ollama for local LLM |
| `make demo` | Build and evaluate demo data |
| `make real` | Build and evaluate real data |
| `make qc` | Run ROBOT QC checks |
| `make ci` | Run full CI pipeline |
| `make docs` | Build Sphinx documentation |
| `make clean` | Remove all generated files |
| `make robot` | Download ROBOT jar |

## Notes for AI Assistants

### When Adding Features
- Always use existing namespace definitions from `namespaces.py`
- Follow existing patterns in `csv_to_rdf.py` for new data columns
- Update system prompt in `orchestrator.py` when adding agent tools
- Add tests to `python/tests/` for new functionality

### When Debugging
- Use `--verbose` flag for agent debugging
- Check `make verify-demo` to ensure graph parses
- Run `mcbo-stats --data-dir <dir>` to inspect graph contents
- ROBOT warnings about "Unsafe IRIs" can be ignored (known issue)

### When Modifying Queries
- Test SPARQL queries with `mcbo-run-eval --data-dir data.sample`
- Use `robot query` for manual testing
- Ensure queries work on both demo and real data
- Check query performance with `mcbo-stats` first

### Common Pitfalls
- Don't edit `.data/` directory (git-ignored, user-specific)
- Don't commit generated files (`graph.ttl`, `results/`, `STATS.txt`)
- Don't hardcode namespaces (use `namespaces.py`)
- Don't run `make real` if `.data/` doesn't exist (will fail silently)
- Remember to activate conda environment: `conda activate mcbo`
