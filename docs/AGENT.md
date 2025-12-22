# MCBO LLM Agent

The MCBO Agent is an LLM-powered system that answers competency questions about bioprocessing data using tool-calling and SPARQL queries.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Usage](#usage)
4. [MCP Server](#mcp-server)
5. [Customization Guide](#customization-guide)
6. [Architecture](#architecture)

---

## Quick Start

```bash
# 1. Install agent dependencies
make install-agent

# 2. Set your API key (choose one)
export OPENAI_API_KEY=sk-...        # OpenAI
# OR
export ANTHROPIC_API_KEY=sk-ant-... # Anthropic

# 3. Run a query
mcbo-agent-eval --data-dir data.sample --cq CQ1

# Or with local LLM (no API key needed)
make install-ollama
mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider ollama
```

---

## Installation

### Option 1: OpenAI (Recommended for accuracy)

```bash
# Install agent dependencies
make install-agent

# Set API key
export OPENAI_API_KEY=sk-...

# Test
mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider openai
```

### Option 2: Anthropic Claude

```bash
# Install agent dependencies
make install-agent

# Set API key
export ANTHROPIC_API_KEY=sk-ant-api03-...

# Test
mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider anthropic
```

### Option 3: Ollama (Local, Free, Private)

Best for: Privacy-sensitive data, offline use, no API costs.

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Install Ollama (macOS)
brew install ollama

# Pull a model (qwen2.5:3b is fast and good at tool calling)
ollama pull qwen2.5:3b

# Start Ollama server (in background)
ollama serve &

# Install agent deps
make install-agent

# Test
mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider ollama --model qwen2.5:3b
```

**Recommended Ollama Models:**

| Model | Size | Speed | Accuracy | GPU VRAM |
|-------|------|-------|----------|----------|
| `qwen2.5:3b` | 2GB | ⚡ Fast | Good | 4GB+ |
| `qwen2.5:7b` | 4.5GB | Medium | Better | 8GB+ |
| `mistral:7b` | 4.5GB | Medium | Good | 8GB+ |
| `llama3.1:8b` | 4.7GB | Medium | Better | 8GB+ |

---

## Usage

### Running Competency Questions

```bash
# Run a predefined CQ (CQ1-CQ8)
mcbo-agent-eval --data-dir data.sample --cq CQ1

# Run a natural language question
mcbo-agent-eval --data-dir data.sample \
  --cq "What genes are differentially expressed under Fed-batch vs Perfusion in HEK293?"

# Run on your real data
mcbo-agent-eval --data-dir .data --cq CQ1

# Verbose mode (see tool calls)
mcbo-agent-eval --data-dir data.sample --cq CQ1 --verbose

# Limit iterations
mcbo-agent-eval --data-dir data.sample --cq CQ1 --max-iterations 5
```

### Predefined Competency Questions

| CQ | Question |
|----|----------|
| CQ1 | Under what culture conditions (pH, dissolved oxygen, temperature) do the cells reach peak recombinant protein productivity? |
| CQ2 | Which cell lines have been engineered to overexpress gene Y? |
| CQ3 | Which nutrient concentrations in cell line K are most associated with viable cell density above Z at day 6? |
| CQ4 | How does the expression of gene X vary between clone A and clone B? |
| CQ5 | What pathways are differentially expressed under Fed-batch vs Perfusion in cell line K? |
| CQ6 | Which are the top genes correlated with recombinant protein productivity in the stationary phase? |
| CQ7 | Which genes have the highest fold change between cells with viability >90% and those with <50%? |
| CQ8 | Which cell lines or subclones are best suited for glycosylation profiles required for therapeutic protein X? |

### Command-Line Options

```
mcbo-agent-eval [OPTIONS]

Options:
  --data-dir PATH      Data directory with graph.ttl (default: data.sample)
  --cq TEXT            CQ identifier (CQ1-CQ8) or natural language question
  --provider TEXT      LLM provider: openai, anthropic, ollama, mock (default: auto-detect from env)
  --model TEXT         Model name (e.g., gpt-4-turbo-preview, claude-3-opus, qwen2.5:3b)
  --verbose, -v        Show detailed tool calls and reasoning
  --max-iterations N   Max tool-calling iterations (default: 10)
```

---

## MCP Server

The agent can run as an MCP (Model Context Protocol) server, allowing integration with Claude Desktop, Cursor, or other MCP-compatible clients.

### Starting the Server

```bash
# Install MCP dependencies (requires Python 3.10+)
pip install -e python/[mcp]

# Start the server
python -m mcbo.agent.mcp_server
```

### Claude Desktop Configuration

Add to `~/.config/claude/claude_desktop_config.json` (Linux) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "mcbo": {
      "command": "python",
      "args": ["-m", "mcbo.agent.mcp_server"],
      "cwd": "/path/to/mcbo",
      "env": {
        "DATA_DIR": "/path/to/mcbo/data.sample"
      }
    }
  }
}
```

### Testing with MCP Inspector

```bash
# Install the inspector
npx @anthropic/mcp-inspector

# Point it at your server
# Then navigate to http://localhost:5173
```

---

## Customization Guide

### How the System Prompt Works

The agent's behavior is controlled by `SYSTEM_PROMPT` in:

```
python/mcbo/agent/orchestrator.py (line ~34)
```

The prompt has these sections:

1. **SPARQL TEMPLATES** - Maps question types to template names
2. **WORKFLOWS** - Step-by-step instructions for each CQ type
3. **CRITICAL RULES** - Guardrails to prevent hallucination

**To modify the prompt:**

```python
# In orchestrator.py
SYSTEM_PROMPT = """You are an expert bioprocess data analyst...

# Add new workflows:
For MY_NEW_QUESTION_TYPE:
1. execute_sparql with template "my_template"
2. my_analysis_tool with params...

# Add new rules:
CRITICAL RULES:
- Always cite specific run IDs
- Never make up gene names
"""
```

### SPARQL Templates

Templates are parameterized SPARQL queries in:

```
python/mcbo/agent/sparql_templates.py
```

**Structure:**

```python
SPARQL_TEMPLATES = {
    "template_name": {
        "description": "What this template fetches",
        "params": ["optional", "parameters"],
        "query": """
            PREFIX mcbo: <http://example.org/mcbo#>
            SELECT ?var1 ?var2
            WHERE {
                ?process a ?processType .
                ...
            }
        """
    },
    ...
}
```

**To add a new template:**

```python
# In sparql_templates.py
SPARQL_TEMPLATES["my_new_template"] = {
    "description": "Fetches custom data for my use case",
    "params": ["cell_line"],  # Optional parameters
    "query": """
        PREFIX mcbo: <http://example.org/mcbo#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?gene ?expressionValue ?cellLine
        WHERE {
            ?process mcbo:usesCellLine ?cl .
            ?cl rdfs:label ?cellLine .
            FILTER(CONTAINS(?cellLine, "{cell_line}"))
            ?process mcbo:hasProcessOutput ?sample .
            ?sample mcbo:hasGeneExpression ?expr .
            ?expr mcbo:hasExpressionValue ?expressionValue .
            ?expr <http://purl.obolibrary.org/obo/IAO_0000136> ?g .
            ?g rdfs:label ?gene .
        }
    """
}
```

**Then update the system prompt to use it:**

```python
# In orchestrator.py, add to WORKFLOWS section:
For MY_QUESTION_TYPE:
1. execute_sparql with template "my_new_template" and params {"cell_line": "HEK293"}
```

### Adding New Tools

Tools are defined in:

```
python/mcbo/agent/tools.py
```

**Structure:**

```python
TOOL_DEFINITIONS = [
    {
        "name": "tool_name",
        "description": "What this tool does",
        "input_schema": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "..."},
                "param2": {"type": "number", "description": "..."}
            },
            "required": ["param1"]
        }
    },
    ...
]
```

**To add a new tool:**

1. Define the tool schema in `tools.py`:

```python
TOOL_DEFINITIONS.append({
    "name": "my_new_tool",
    "description": "Performs custom analysis on bioprocess data",
    "input_schema": {
        "type": "object",
        "properties": {
            "data": {"type": "array", "description": "Input data"},
            "threshold": {"type": "number", "description": "Threshold value"}
        },
        "required": ["data"]
    }
})
```

2. Add the implementation in `ToolExecutor`:

```python
# In tools.py, in ToolExecutor._execute_single_tool()
elif tool_name == "my_new_tool":
    return self._my_new_tool(**args)

def _my_new_tool(self, data: list, threshold: float = 0.5) -> dict:
    """Custom analysis implementation."""
    # Your logic here
    return {"result": processed_data}
```

3. Update the system prompt to explain when to use it.

### Statistical Tools

Available in `python/mcbo/agent/stats_tools.py`:

| Function | Description |
|----------|-------------|
| `compute_correlation(data, x_col, y_col, method)` | Pearson/Spearman correlation |
| `compute_fold_change(data, group_col, val_col, g1, g2)` | Log2 fold change between groups |
| `differential_expression(data, group_col, g1, g2, ...)` | T-test with fold change |
| `find_peak_conditions(data, condition_cols, metric)` | Find optimal conditions |
| `summarize_by_group(data, group_col, val_col, agg)` | Group-wise aggregation |

### Pathway Tools

Available in `python/mcbo/agent/pathway_tools.py`:

| Function | Description |
|----------|-------------|
| `get_kegg_pathways(gene_list)` | Query KEGG for pathways |
| `get_reactome_pathways(gene_list)` | Query Reactome for pathways |
| `perform_enrichment_analysis(gene_list, ...)` | Fisher's exact enrichment |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Orchestrator                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    System Prompt                         ││
│  │  - SPARQL template selection guide                       ││
│  │  - Workflow instructions by question type                ││
│  │  - Critical rules (no hallucination)                     ││
│  └─────────────────────────────────────────────────────────┘│
│                            │                                 │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                   LLM Provider                           ││
│  │  - OpenAIProvider (gpt-4-turbo-preview)                  ││
│  │  - AnthropicProvider (claude-3-opus)                     ││
│  │  - OllamaProvider (qwen2.5:3b, mistral:7b, etc.)         ││
│  │  - MockProvider (for testing)                            ││
│  └─────────────────────────────────────────────────────────┘│
│                            │                                 │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                   Tool Executor                          ││
│  │                                                          ││
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     ││
│  │  │execute_sparql│ │  stats_tools │ │pathway_tools │     ││
│  │  │              │ │              │ │              │     ││
│  │  │ - Templates  │ │ - correlation│ │ - KEGG       │     ││
│  │  │ - RDF Graph  │ │ - fold_change│ │ - Reactome   │     ││
│  │  │              │ │ - diff_expr  │ │ - enrichment │     ││
│  │  └──────────────┘ └──────────────┘ └──────────────┘     ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      RDF Graph                               │
│                    (graph.ttl)                               │
│                                                              │
│  - Cell culture processes (Batch, Fed-batch, Perfusion)     │
│  - Cell lines and clones                                     │
│  - Culture conditions (temp, pH, DO)                         │
│  - Gene expression measurements                              │
│  - Productivity and viability data                           │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
python/mcbo/agent/
├── __init__.py           # Module exports
├── orchestrator.py       # Main agent logic, system prompt, LLM providers
├── tools.py              # Tool definitions and executor
├── sparql_templates.py   # Parameterized SPARQL queries
├── stats_tools.py        # Statistical analysis functions
├── pathway_tools.py      # Pathway enrichment (KEGG, Reactome)
├── agent_eval.py         # CLI entry point
└── mcp_server.py         # MCP server implementation
```

---

## Troubleshooting

### "No data found" errors

1. Check that the graph exists: `ls -la data.sample/graph.ttl`
2. Rebuild if needed: `mcbo-build-graph build --data-dir data.sample`
3. Verify data: `mcbo-stats --data-dir data.sample`

### Ollama 404 errors

```bash
# Make sure Ollama is running
ollama serve

# Make sure model is pulled
ollama list
ollama pull qwen2.5:3b
```

### Model hallucinating

Try:
1. Use a larger model: `--model qwen2.5:7b`
2. Use OpenAI: `--provider openai`
3. Add `--verbose` to see what's happening

### Slow performance

For Ollama:
- Use smaller model: `qwen2.5:3b` instead of `7b`
- Check GPU is being used: `nvidia-smi`
- Try quantized versions: `ollama pull qwen2.5:3b-q4_0`

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `DATA_DIR` | Default data directory | `/path/to/data.sample` |

---

## Testing

```bash
# Run agent tests
pytest python/tests/test_agent_integration.py -v

# Run with mock provider (no LLM needed)
mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider mock
```

