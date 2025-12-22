# python/mcbo/agent/mcp_server.py
"""
MCP Server for MCBO Agent.

Run with:
  python -m mcbo.agent.mcp_server --data-dir data.sample
"""

import asyncio
import json
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ..graph_utils import load_graphs
from .tools import ToolExecutor, TOOL_DEFINITIONS
from .orchestrator import AgentOrchestrator, get_provider, CQ_DESCRIPTIONS

app = Server("mcbo-agent")

# Global state
_graph = None
_executor = None

@app.list_tools()
async def list_tools():
    """List available MCBO tools."""
    tools = []
    
    # Add the main "ask" tool
    tools.append(Tool(
        name="mcbo_ask",
        description="Ask a question about mammalian cell bioprocessing data. "
                    "Supports competency questions (CQ1-CQ8) or natural language.",
        inputSchema={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "A question about the bioprocess data (e.g., 'What conditions give peak productivity?')"
                },
            },
            "required": ["question"],
        },
    ))
    
    # Add individual analysis tools
    for tool_def in TOOL_DEFINITIONS:
        tools.append(Tool(
            name=f"mcbo_{tool_def['name']}",
            description=tool_def["description"],
            inputSchema=tool_def["input_schema"],
        ))
    
    return tools

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """Execute an MCBO tool."""
    global _executor
    
    if name == "mcbo_ask":
        # Use orchestrator for natural language questions
        orchestrator = AgentOrchestrator(_graph, get_provider())
        result = orchestrator.answer_question(arguments["question"])
        return [TextContent(type="text", text=result.get("answer", str(result)))]
    
    # Direct tool execution
    tool_name = name.replace("mcbo_", "")
    result = _executor.execute(tool_name, arguments)
    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

async def main(data_dir: str):
    global _graph, _executor
    
    # Load graph
    graph_path = Path(data_dir) / "graph.ttl"
    _graph = load_graphs([graph_path])
    _executor = ToolExecutor(_graph)
    
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.data_dir))
