"""
LLM Orchestrator for MCBO agent.

Manages the interaction between the LLM and the analysis tools,
supporting both Anthropic Claude and OpenAI GPT-4.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Generator, Optional

from rdflib import Graph

from .tools import TOOL_DEFINITIONS, ToolExecutor
from .sparql_templates import CQ_TEMPLATE_MAPPING


# CQ descriptions for the LLM to understand what each competency question asks
CQ_DESCRIPTIONS = {
    "CQ1": "Under what culture conditions (pH, dissolved oxygen, temperature) do the cells reach peak recombinant protein productivity?",
    "CQ2": "Which cell lines have been engineered to overexpress gene Y?",
    "CQ3": "Which nutrient concentrations in cell line K are most associated with viable cell density above Z at day 6 of culture?",
    "CQ4": "How does the expression of gene X vary between clone A and clone B?",
    "CQ5": "What pathways are differentially expressed under Fed-batch vs Perfusion in cell line K?",
    "CQ6": "Which are the top genes correlated with recombinant protein productivity in the stationary phase of all experiments?",
    "CQ7": "Which genes have the highest fold change between cells with viability (>90%) and those without (<50%)?",
    "CQ8": "Which cell lines or subclones are best suited for glycosylation profiles required for therapeutic protein X?",
}


SYSTEM_PROMPT = """You are an expert bioprocess data analyst assistant. You help answer competency questions about mammalian cell bioprocessing data stored in an RDF knowledge graph.

You have access to the following tools:
{tools}

SPARQL TEMPLATES - Use the correct one for each question type:
| Question type | template_name to use |
|---------------|---------------------|
| productivity, culture conditions | culture_conditions_productivity |
| gene expression, differential expression | gene_expression_by_process_type |
| viability, cell health | gene_expression_by_viability |
| cell line overexpression | cell_lines_overexpression |
| product quality | cell_lines_product_quality |

FILTER SYNTAX for filtering by cell line:
- To filter by cell line, use: filter_clause="CONTAINS(?cellLineLabel, \"HEK293\")"
- To filter by process type, use: filter_clause="?processType = mcbo:FedBatchCultureProcess"
- Leave filter_clause empty or omit to get all data

Available templates: {templates}

WORKFLOWS BY QUESTION TYPE:

For CULTURE CONDITIONS questions (CQ1):
1. execute_sparql with template "culture_conditions_productivity"
2. find_peak_conditions with condition_cols and metric_col

For GENE EXPRESSION / DIFFERENTIAL EXPRESSION questions (CQ5):
1. execute_sparql with template "gene_expression_by_process_type"  
2. differential_expression with group_col="processType", group1="FedBatchCultureProcess", group2="PerfusionCultureProcess", cell_line="HEK293" (or whatever cell line is mentioned)
3. Optionally: get_pathway_enrichment with the significant gene list

IMPORTANT: When a cell line is mentioned (e.g., "in HEK293"), pass cell_line="HEK293" to differential_expression!

For CORRELATION questions (CQ3, CQ6):
1. execute_sparql with appropriate template
2. compute_correlation with x_col and y_col

For VIABILITY questions (CQ7):
1. execute_sparql with template "gene_expression_by_viability"
2. differential_expression or compute_fold_change

CRITICAL RULES:
- ALWAYS start by fetching data with execute_sparql
- Only report genes, values, and statistics that appear in the tool results
- NEVER make up gene names, run IDs, or numerical values
- Cite specific evidence: run IDs, sample IDs, cell line names
- If data is missing, explain what's needed

The graph contains MCBO (Mammalian Cell Bioprocessing Ontology) data including:
- Cell culture processes (Batch, Fed-batch, Perfusion, Chemostat)
- Cell lines (CHO-K1, CHO-DG44, HEK293) and clones
- Culture conditions (temperature, pH, dissolved oxygen)
- Gene expression measurements (linked to samples)
- Productivity measurements (categorical: VeryHigh, High, Medium, Low)
- Cell viability data
"""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def create_message(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> dict:
        """Create a message with the LLM.
        
        Args:
            messages: Conversation history
            system: System prompt
            tools: Tool definitions
            max_tokens: Maximum tokens in response
            
        Returns:
            Response dict with 'content' and optional 'tool_calls'
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get provider name."""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        """Initialize Anthropic provider.
        
        Args:
            api_key: API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic library required. Install with: pip install anthropic")
        return self._client
    
    def get_name(self) -> str:
        return f"Anthropic ({self.model})"
    
    def create_message(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> dict:
        # Convert tools to Anthropic format
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            })
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=anthropic_tools,
            messages=messages,
        )
        
        # Parse response
        result = {
            "content": "",
            "tool_calls": [],
            "stop_reason": response.stop_reason,
        }
        
        for block in response.content:
            if block.type == "text":
                result["content"] += block.text
            elif block.type == "tool_use":
                result["tool_calls"].append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })
        
        return result


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview"):
        """Initialize OpenAI provider.
        
        Args:
            api_key: API key (defaults to OPENAI_API_KEY env var)
            model: Model to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai library required. Install with: pip install openai")
        return self._client
    
    def get_name(self) -> str:
        return f"OpenAI ({self.model})"
    
    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert messages from Anthropic format to OpenAI format."""
        converted = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "user":
                # Check if this is tool results (Anthropic format)
                if isinstance(content, list) and content and isinstance(content[0], dict):
                    if content[0].get("type") == "tool_result":
                        # Convert tool results to OpenAI format
                        for item in content:
                            if item.get("type") == "tool_result":
                                converted.append({
                                    "role": "tool",
                                    "tool_call_id": item.get("tool_use_id"),
                                    "content": item.get("content", ""),
                                })
                    else:
                        # Other list content, extract text
                        text_parts = [p.get("text", "") for p in content if p.get("type") == "text"]
                        converted.append({"role": "user", "content": " ".join(text_parts)})
                else:
                    converted.append({"role": "user", "content": content})
            
            elif role == "assistant":
                # Check if this has tool calls (Anthropic format)
                if isinstance(content, list):
                    text_parts = []
                    tool_calls = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif item.get("type") == "tool_use":
                                tool_calls.append({
                                    "id": item.get("id"),
                                    "type": "function",
                                    "function": {
                                        "name": item.get("name"),
                                        "arguments": json.dumps(item.get("input", {})),
                                    },
                                })
                    
                    msg_dict = {"role": "assistant", "content": " ".join(text_parts) or None}
                    if tool_calls:
                        msg_dict["tool_calls"] = tool_calls
                    converted.append(msg_dict)
                else:
                    converted.append({"role": "assistant", "content": content})
            else:
                converted.append(msg)
        
        return converted
    
    def create_message(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> dict:
        # Convert tools to OpenAI format
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            })
        
        # Convert messages from Anthropic format to OpenAI format
        converted_messages = self._convert_messages(messages)
        
        # Add system message to conversation
        full_messages = [{"role": "system", "content": system}] + converted_messages
        
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=full_messages,
            tools=openai_tools if openai_tools else None,
        )
        
        # Parse response
        message = response.choices[0].message
        result = {
            "content": message.content or "",
            "tool_calls": [],
            "stop_reason": response.choices[0].finish_reason,
        }
        
        if message.tool_calls:
            for tc in message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })
        
        return result


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider.
    
    Ollama runs open-source models locally on your GPU.
    Install: curl -fsSL https://ollama.com/install.sh | sh
    Pull a model: ollama pull llama3.1:8b
    """
    
    def __init__(
        self, 
        model: Optional[str] = None, 
        base_url: str = "http://localhost:11434",
    ):
        """Initialize Ollama provider.
        
        Args:
            model: Model name (defaults to OLLAMA_MODEL env var or 'llama3.1:8b')
            base_url: Ollama server URL
        """
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.base_url = base_url
    
    def get_name(self) -> str:
        return f"Ollama ({self.model})"
    
    def create_message(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> dict:
        import requests
        
        # Build Ollama messages
        ollama_messages = [{"role": "system", "content": system}]
        
        # Add tool descriptions to system prompt (Ollama doesn't have native tool support)
        if tools:
            tool_instructions = """

YOU ARE A TOOL-USING AGENT. You MUST respond with JSON tool calls, not explanations.

FORMAT - Respond with ONLY this JSON, no other text:
{"tool": "tool_name", "arguments": {...}}

WORKFLOW:
1. FIRST call: {"tool": "execute_sparql", "arguments": {"template_name": "culture_conditions_productivity"}}
2. THEN call: {"tool": "find_peak_conditions", "arguments": {"condition_cols": ["temperature", "pH", "dissolvedOxygen"], "metric_col": "productivityValue"}}
3. FINALLY: Give your answer in plain text (no JSON)

AVAILABLE TOOLS AND TEMPLATES:
- execute_sparql: Fetch data from graph
  Templates: culture_conditions_productivity, gene_expression_by_process_type, 
             cell_lines_overexpression, gene_expression_by_viability
- find_peak_conditions: Find optimal conditions
- compute_correlation: Compute correlation between columns
- differential_expression: Compare gene expression between groups
- get_pathway_enrichment: Find enriched pathways from gene list

TEMPLATE SELECTION:
| Question type | template_name |
| productivity, conditions | culture_conditions_productivity |
| gene expression, differential | gene_expression_by_process_type |
| viability | gene_expression_by_viability |

FOR GENE EXPRESSION QUESTIONS (Fed-batch vs Perfusion, etc.):
Step 1: {"tool": "execute_sparql", "arguments": {"template_name": "gene_expression_by_process_type"}}
Step 2: {"tool": "differential_expression", "arguments": {"group_col": "processType", "group1": "FedBatchCultureProcess", "group2": "PerfusionCultureProcess"}}

CRITICAL RULES:
- Only report genes that appear in the tool results
- NEVER make up gene names or values
- Use EXACT values from the data

RULES:
- If you see "No data loaded" error, call execute_sparql first
- After tool results, either call another tool OR give final answer
- Do NOT explain what you will do - just DO it with a tool call

EVIDENCE REQUIREMENTS:
- Always cite specific data points from the results
- Include run IDs, cell line names, or sample IDs when available
- Format evidence as: "Evidence: [runID/cellLine] showed [value]"
- List the top 3-5 data points that support your conclusions

WHEN WRITING YOUR FINAL ANSWER:
- Summarize the key findings in plain English
- Do NOT output JSON or tool calls in your final answer
- Do NOT just say what tool you called - explain the RESULTS
- If a tool returned an error, explain what data is missing
"""
            ollama_messages[0]["content"] += tool_instructions
        
        # Convert messages from Anthropic format
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if isinstance(content, list):
                # Handle structured content (tool results, etc.)
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                        elif item.get("type") == "tool_result":
                            text_parts.append(f"Tool result: {item.get('content', '')}")
                        elif item.get("type") == "tool_use":
                            text_parts.append(f"[Called tool: {item.get('name')}]")
                content = "\n".join(text_parts)
            
            if content:
                ollama_messages.append({"role": role, "content": content})
        
        # Call Ollama API
        try:
            # Try /api/chat first (Ollama 0.1.14+)
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                    },
                },
                timeout=120,
            )
            
            # If 404, try /api/generate (older Ollama versions)
            if response.status_code == 404:
                # Combine messages into a single prompt
                prompt = "\n\n".join(
                    f"{m['role'].upper()}: {m['content']}" 
                    for m in ollama_messages
                )
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                        },
                    },
                    timeout=120,
                )
            
            response.raise_for_status()
            data = response.json()
            
        except requests.exceptions.ConnectionError:
            return {
                "content": f"Error: Cannot connect to Ollama at {self.base_url}. "
                          "Make sure Ollama is running: ollama serve",
                "tool_calls": [],
                "stop_reason": "error",
            }
        except requests.exceptions.HTTPError as e:
            if "404" in str(e) or response.status_code == 404:
                return {
                    "content": f"Error: Model '{self.model}' not found. "
                              f"Pull it with: ollama pull {self.model}\n"
                              f"Or try a different model: --model mistral:7b",
                    "tool_calls": [],
                    "stop_reason": "error",
                }
            return {
                "content": f"Error calling Ollama: {e}",
                "tool_calls": [],
                "stop_reason": "error",
            }
        except Exception as e:
            return {
                "content": f"Error calling Ollama: {e}",
                "tool_calls": [],
                "stop_reason": "error",
            }
        
        # Handle both /api/chat and /api/generate response formats
        if "message" in data:
            content = data["message"].get("content", "")
        else:
            content = data.get("response", "")
        
        # Try to parse tool calls from the response
        tool_calls = []
        import re
        
        # Look for JSON tool call pattern
        json_pattern = r'\{[^{}]*"tool"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                parsed = json.loads(match)
                if "tool" in parsed and "arguments" in parsed:
                    tool_calls.append({
                        "id": f"ollama_{len(tool_calls)}",
                        "name": parsed["tool"],
                        "arguments": parsed["arguments"],
                    })
                    # Remove the JSON from content
                    content = content.replace(match, "").strip()
            except json.JSONDecodeError:
                pass
        
        return {
            "content": content,
            "tool_calls": tool_calls,
            "stop_reason": "end_turn" if not tool_calls else "tool_use",
        }


class MockProvider(LLMProvider):
    """Mock provider for testing without API calls."""
    
    def __init__(self, responses: Optional[list[dict]] = None):
        """Initialize mock provider.
        
        Args:
            responses: Pre-defined responses to return
        """
        self.responses = responses or []
        self.call_count = 0
    
    def get_name(self) -> str:
        return "Mock Provider"
    
    def create_message(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> dict:
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        
        # Default response if no more pre-defined responses
        return {
            "content": "I don't have a response configured for this message.",
            "tool_calls": [],
            "stop_reason": "end_turn",
        }


def get_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """Get an LLM provider by name.
    
    Args:
        provider_name: Provider name ('anthropic', 'openai', 'ollama', or 'mock')
                      Defaults to MCBO_LLM_PROVIDER env var or 'anthropic'
    
    Returns:
        Configured LLM provider
    
    Environment variables:
        MCBO_LLM_PROVIDER: Default provider name
        ANTHROPIC_API_KEY: Anthropic API key
        OPENAI_API_KEY: OpenAI API key  
        OLLAMA_MODEL: Ollama model name (default: llama3.1:8b)
    """
    if provider_name is None:
        provider_name = os.getenv("MCBO_LLM_PROVIDER", "anthropic")
    
    provider_name = provider_name.lower()
    
    if provider_name == "anthropic":
        return AnthropicProvider()
    elif provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "ollama":
        return OllamaProvider()
    elif provider_name == "mock":
        return MockProvider()
    else:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            "Use 'anthropic', 'openai', 'ollama', or 'mock'."
        )


class AgentOrchestrator:
    """Orchestrates LLM and tool execution for answering CQs."""
    
    def __init__(
        self,
        graph: Graph,
        provider: Optional[LLMProvider] = None,
        max_iterations: int = 10,
        verbose: bool = False,
    ):
        """Initialize the orchestrator.
        
        Args:
            graph: RDF graph containing MCBO data
            provider: LLM provider (defaults to get_provider())
            max_iterations: Maximum tool call iterations
            verbose: Print debug information
        """
        self.graph = graph
        self.provider = provider or get_provider()
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.executor = ToolExecutor(graph)
        
        # Build system prompt
        tools_desc = "\n".join(f"- {t['name']}: {t['description']}" for t in TOOL_DEFINITIONS)
        templates_desc = "\n".join(f"- {name}" for name in CQ_TEMPLATE_MAPPING.values())
        self.system_prompt = SYSTEM_PROMPT.format(tools=tools_desc, templates=templates_desc)
    
    def answer_cq(self, cq_id: str, parameters: Optional[dict] = None) -> dict:
        """Answer a specific competency question.
        
        Args:
            cq_id: CQ identifier (e.g., 'CQ1', 'CQ2')
            parameters: Optional parameters for the CQ (e.g., gene name, cell line)
            
        Returns:
            dict with 'answer', 'tool_calls', and 'iterations'
        """
        cq_upper = cq_id.upper()
        if cq_upper not in CQ_DESCRIPTIONS:
            return {"error": f"Unknown CQ: {cq_id}. Valid: {list(CQ_DESCRIPTIONS.keys())}"}
        
        description = CQ_DESCRIPTIONS[cq_upper]
        
        # Build the question with parameters
        if parameters:
            for key, value in parameters.items():
                description = description.replace(f"gene {key.upper()}", f"gene {value}")
                description = description.replace(f"clone {key.upper()}", f"clone {value}")
                description = description.replace(f"cell line {key.upper()}", f"cell line {value}")
        
        return self.answer_question(description)
    
    def answer_question(self, question: str) -> dict:
        """Answer a natural language question about the data.
        
        Args:
            question: Natural language question
            
        Returns:
            dict with 'answer', 'tool_calls', and 'iterations'
        """
        messages = [{"role": "user", "content": question}]
        tool_call_history = []
        
        for iteration in range(self.max_iterations):
            if self.verbose:
                print(f"\n--- Iteration {iteration + 1} ---")
            
            # Get LLM response
            response = self.provider.create_message(
                messages=messages,
                system=self.system_prompt,
                tools=TOOL_DEFINITIONS,
            )
            
            if self.verbose:
                print(f"Content: {response.get('content', '')[:200]}...")
                print(f"Tool calls: {len(response.get('tool_calls', []))}")
            
            # If no tool calls, we're done
            if not response.get("tool_calls"):
                return {
                    "answer": response["content"],
                    "tool_calls": tool_call_history,
                    "iterations": iteration + 1,
                }
            
            # Execute tool calls
            tool_results = []
            for tool_call in response["tool_calls"]:
                tool_name = tool_call["name"]
                arguments = tool_call["arguments"]
                
                if self.verbose:
                    print(f"  Executing: {tool_name}({json.dumps(arguments)[:100]}...)")
                
                result = self.executor.execute(tool_name, arguments)
                
                tool_call_history.append({
                    "tool": tool_name,
                    "arguments": arguments,
                    "result_summary": self._summarize_result(result),
                })
                
                tool_results.append({
                    "id": tool_call["id"],
                    "name": tool_name,
                    "result": result,
                })
            
            # Add assistant message and tool results to conversation
            assistant_content = []
            if response.get("content"):
                assistant_content.append({"type": "text", "text": response["content"]})
            for tc in response["tool_calls"]:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["arguments"],
                })
            
            messages.append({"role": "assistant", "content": assistant_content})
            
            # Add tool results
            tool_result_content = []
            for tr in tool_results:
                tool_result_content.append({
                    "type": "tool_result",
                    "tool_use_id": tr["id"],
                    "content": json.dumps(tr["result"], default=str),
                })
            messages.append({"role": "user", "content": tool_result_content})
        
        return {
            "answer": "Maximum iterations reached. Partial answer: " + response.get("content", ""),
            "tool_calls": tool_call_history,
            "iterations": self.max_iterations,
            "warning": "Max iterations reached",
        }
    
    def _summarize_result(self, result: dict) -> str:
        """Create a brief summary of a tool result."""
        if "error" in result:
            return f"Error: {result['error']}"
        if "row_count" in result:
            return f"{result['row_count']} rows returned"
        if "correlation" in result:
            return f"r={result['correlation']:.3f}" if result['correlation'] else "No correlation"
        if "fold_change" in result:
            return f"FC={result['fold_change']:.2f}" if result['fold_change'] else "No fold change"
        if "enriched_pathways" in result:
            return f"{len(result['enriched_pathways'])} enriched pathways"
        return str(result)[:100]


def run_all_cqs(
    graph: Graph,
    provider: Optional[LLMProvider] = None,
    verbose: bool = False,
) -> dict:
    """Run all competency questions and return results.
    
    Args:
        graph: RDF graph
        provider: LLM provider
        verbose: Print debug info
        
    Returns:
        dict mapping CQ ID to result
    """
    orchestrator = AgentOrchestrator(graph, provider, verbose=verbose)
    results = {}
    
    for cq_id in CQ_DESCRIPTIONS.keys():
        print(f"\n{'='*60}")
        print(f"Running {cq_id}: {CQ_DESCRIPTIONS[cq_id][:60]}...")
        print('='*60)
        
        result = orchestrator.answer_cq(cq_id)
        results[cq_id] = result
        
        if "answer" in result:
            print(f"\nAnswer ({result.get('iterations', 0)} iterations):")
            print(result["answer"][:500])
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
    
    return results


__all__ = [
    "LLMProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "MockProvider",
    "get_provider",
    "AgentOrchestrator",
    "run_all_cqs",
    "CQ_DESCRIPTIONS",
]

