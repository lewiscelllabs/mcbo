"""
Integration tests for MCBO agent.

These tests verify the full agent workflow with mock LLM responses.
"""

import pytest
import json
from pathlib import Path

from rdflib import Graph, Literal, Namespace

from mcbo.agent.sparql_templates import (
    get_template,
    format_template,
    list_templates,
    CQ_TEMPLATE_MAPPING,
)
from mcbo.agent.tools import ToolExecutor, TOOL_DEFINITIONS
from mcbo.agent.orchestrator import (
    AgentOrchestrator,
    MockProvider,
    CQ_DESCRIPTIONS,
)


# Test namespaces
MCBO = Namespace("http://example.org/mcbo#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
RO = Namespace("http://purl.obolibrary.org/obo/RO_")


@pytest.fixture
def sample_graph():
    """Create a minimal test graph with sample data."""
    g = Graph()
    
    # Bind namespaces
    g.bind("mcbo", MCBO)
    g.bind("rdfs", RDFS)
    
    # Add a simple process with productivity
    process = MCBO.run_001
    g.add((process, RO["0000057"], MCBO.system_001))  # has participant
    g.add((MCBO.system_001, RO["0000086"], MCBO.ccq_001))  # has quality
    
    # Add cell line
    g.add((MCBO.cellline_CHO_K1, RDFS.label, Literal("CHO-K1")))
    g.add((process, MCBO.usesCellLine, MCBO.cellline_CHO_K1))
    
    # Add culture conditions
    g.add((MCBO.ccq_001, MCBO.hasTemperature, Literal(37.0)))
    g.add((MCBO.ccq_001, MCBO.hasPH, Literal(7.2)))
    
    # Add productivity
    g.add((MCBO.prod_001, MCBO.hasProductivityValue, Literal(4.5)))
    g.add((process, MCBO.hasProductivityMeasurement, MCBO.prod_001))
    
    return g


class TestSparqlTemplates:
    """Tests for SPARQL template system."""
    
    def test_list_templates(self):
        """Test listing available templates."""
        templates = list_templates()
        assert len(templates) > 0
        assert "culture_conditions_productivity" in templates
        assert "cell_lines_overexpression" in templates
    
    def test_get_template(self):
        """Test getting a template by name."""
        template = get_template("culture_conditions_productivity")
        assert "SELECT" in template
        assert "mcbo:hasProductivityValue" in template
    
    def test_get_invalid_template(self):
        """Test error handling for invalid template name."""
        with pytest.raises(KeyError):
            get_template("nonexistent_template")
    
    def test_format_template_with_filter(self):
        """Test formatting template with filter clause."""
        query = format_template(
            "culture_conditions_productivity",
            filter_clause="?productivityValue > 3"
        )
        assert "FILTER" in query
        assert "productivityValue > 3" in query
    
    def test_cq_template_mapping(self):
        """Test CQ to template mapping exists for all CQs."""
        for cq_id in CQ_DESCRIPTIONS.keys():
            assert cq_id in CQ_TEMPLATE_MAPPING, f"Missing template for {cq_id}"


class TestToolDefinitions:
    """Tests for tool definitions."""
    
    def test_all_tools_have_required_fields(self):
        """Test that all tool definitions have required fields."""
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool, f"Tool missing 'name'"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "input_schema" in tool, f"Tool {tool.get('name')} missing 'input_schema'"
    
    def test_tool_names_unique(self):
        """Test that all tool names are unique."""
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert len(names) == len(set(names)), "Duplicate tool names found"


class TestToolExecutor:
    """Tests for ToolExecutor class."""
    
    def test_execute_sparql(self, sample_graph):
        """Test SPARQL query execution."""
        executor = ToolExecutor(sample_graph)
        
        result = executor.execute("execute_sparql", {
            "raw_query": """
                SELECT ?cellLine ?label
                WHERE {
                    ?process mcbo:usesCellLine ?cellLine .
                    OPTIONAL { ?cellLine rdfs:label ?label }
                }
            """
        })
        
        assert "error" not in result
        assert result["row_count"] >= 1
    
    def test_execute_unknown_tool(self, sample_graph):
        """Test handling of unknown tool."""
        executor = ToolExecutor(sample_graph)
        result = executor.execute("unknown_tool", {})
        
        assert "error" in result
        assert "Unknown tool" in result["error"]
    
    def test_find_peak_conditions_no_data(self, sample_graph):
        """Test find_peak_conditions with no prior data."""
        executor = ToolExecutor(sample_graph)
        result = executor.execute("find_peak_conditions", {
            "condition_cols": ["temperature"],
            "metric_col": "productivity",
        })
        
        assert "error" in result
        assert "No data loaded" in result["error"]


class TestMockProvider:
    """Tests for MockProvider."""
    
    def test_mock_returns_configured_response(self):
        """Test that mock provider returns configured responses."""
        responses = [
            {"content": "First response", "tool_calls": [], "stop_reason": "end_turn"},
            {"content": "Second response", "tool_calls": [], "stop_reason": "end_turn"},
        ]
        provider = MockProvider(responses)
        
        result1 = provider.create_message([], "", [])
        assert result1["content"] == "First response"
        
        result2 = provider.create_message([], "", [])
        assert result2["content"] == "Second response"
    
    def test_mock_with_tool_calls(self):
        """Test mock provider with tool call responses."""
        responses = [{
            "content": "",
            "tool_calls": [{
                "id": "call_1",
                "name": "execute_sparql",
                "arguments": {"template_name": "culture_conditions_productivity"},
            }],
            "stop_reason": "tool_use",
        }]
        provider = MockProvider(responses)
        
        result = provider.create_message([], "", [])
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "execute_sparql"


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator."""
    
    def test_init_with_mock_provider(self, sample_graph):
        """Test orchestrator initialization with mock provider."""
        provider = MockProvider([])
        orchestrator = AgentOrchestrator(sample_graph, provider)
        
        assert orchestrator.graph is sample_graph
        assert orchestrator.provider is provider
    
    def test_answer_unknown_cq(self, sample_graph):
        """Test handling of unknown CQ ID."""
        provider = MockProvider([])
        orchestrator = AgentOrchestrator(sample_graph, provider)
        
        result = orchestrator.answer_cq("CQ99")
        assert "error" in result
        assert "Unknown CQ" in result["error"]
    
    def test_simple_answer_flow(self, sample_graph):
        """Test simple answer flow with mock responses."""
        responses = [
            # First response: final answer (no tool calls)
            {
                "content": "Based on my analysis, the peak productivity occurs at 37°C.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            }
        ]
        provider = MockProvider(responses)
        orchestrator = AgentOrchestrator(sample_graph, provider)
        
        result = orchestrator.answer_question("What temperature gives peak productivity?")
        
        assert "answer" in result
        assert "37°C" in result["answer"]
        assert result["iterations"] == 1
    
    def test_tool_call_flow(self, sample_graph):
        """Test flow with tool calls."""
        responses = [
            # First response: request tool call
            {
                "content": "",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "execute_sparql",
                    "arguments": {"template_name": "all_cell_lines"},
                }],
                "stop_reason": "tool_use",
            },
            # Second response: final answer after seeing tool results
            {
                "content": "The database contains CHO-K1 cell line.",
                "tool_calls": [],
                "stop_reason": "end_turn",
            }
        ]
        provider = MockProvider(responses)
        orchestrator = AgentOrchestrator(sample_graph, provider)
        
        result = orchestrator.answer_question("What cell lines are in the database?")
        
        assert "answer" in result
        assert result["iterations"] == 2
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "execute_sparql"
    
    def test_max_iterations(self, sample_graph):
        """Test that max iterations is respected."""
        # Create infinite tool call loop
        responses = [
            {
                "content": "",
                "tool_calls": [{
                    "id": f"call_{i}",
                    "name": "execute_sparql",
                    "arguments": {"template_name": "all_genes"},
                }],
                "stop_reason": "tool_use",
            }
            for i in range(20)  # More than max_iterations
        ]
        provider = MockProvider(responses)
        orchestrator = AgentOrchestrator(sample_graph, provider, max_iterations=3)
        
        result = orchestrator.answer_question("Test")
        
        assert result["iterations"] == 3
        assert "warning" in result


class TestCQDescriptions:
    """Tests for CQ descriptions."""
    
    def test_all_cqs_have_descriptions(self):
        """Test that all standard CQs have descriptions."""
        expected_cqs = ["CQ1", "CQ2", "CQ3", "CQ4", "CQ5", "CQ6", "CQ7", "CQ8"]
        for cq_id in expected_cqs:
            assert cq_id in CQ_DESCRIPTIONS, f"Missing description for {cq_id}"
    
    def test_descriptions_are_not_empty(self):
        """Test that CQ descriptions are not empty."""
        for cq_id, desc in CQ_DESCRIPTIONS.items():
            assert len(desc) > 10, f"{cq_id} description too short"

