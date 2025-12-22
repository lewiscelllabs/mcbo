#!/usr/bin/env python3
"""
MCBO Agent Evaluation CLI.

Run competency questions using an LLM agent that can execute SPARQL queries
and perform statistical analysis.

Usage:
  mcbo-agent-eval --data-dir data.sample --cq CQ1
  mcbo-agent-eval --data-dir data.sample --cq "Which culture conditions produce peak productivity?"
  mcbo-agent-eval --data-dir data.sample --all
  mcbo-agent-eval --data-dir data.sample --all --provider openai

Environment variables:
  MCBO_LLM_PROVIDER     - LLM provider: 'anthropic' (default), 'openai', or 'mock'
  ANTHROPIC_API_KEY     - Anthropic API key (for Claude)
  OPENAI_API_KEY        - OpenAI API key (for GPT-4)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from ..graph_utils import load_graphs, ensure_dir
from .orchestrator import (
    AgentOrchestrator,
    get_provider,
    run_all_cqs,
    CQ_DESCRIPTIONS,
)


# Configuration by convention defaults
DEFAULT_PATHS = {
    "graph": "graph.ttl",
    "results": "agent_results",
}


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def resolve_data_dir_path(data_dir: Path, key: str) -> Path:
    """Resolve a path relative to data_dir using convention defaults."""
    return data_dir / DEFAULT_PATHS[key]


def print_cq_list():
    """Print list of available competency questions."""
    print("\nAvailable Competency Questions:")
    print("-" * 60)
    for cq_id, desc in CQ_DESCRIPTIONS.items():
        print(f"  {cq_id}: {desc}")
    print()


def run_single_cq(
    orchestrator: AgentOrchestrator,
    cq_input: str,
    verbose: bool = False,
) -> dict:
    """Run a single competency question or natural language query.
    
    Args:
        orchestrator: Configured agent orchestrator
        cq_input: Either a CQ ID ('CQ1') or natural language question
        verbose: Print debug information
        
    Returns:
        Result dict with answer and metadata
    """
    # Check if input is a CQ ID
    cq_upper = cq_input.upper().strip()
    if cq_upper in CQ_DESCRIPTIONS:
        print(f"\n{'='*60}")
        print(f"{cq_upper}: {CQ_DESCRIPTIONS[cq_upper]}")
        print('='*60)
        return orchestrator.answer_cq(cq_upper)
    else:
        # Treat as natural language question
        print(f"\n{'='*60}")
        print(f"Question: {cq_input}")
        print('='*60)
        return orchestrator.answer_question(cq_input)


def write_results(
    results: dict,
    output_dir: Path,
    format: str = "json",
) -> None:
    """Write results to output directory.
    
    Args:
        results: Dict mapping CQ ID to result
        output_dir: Directory to write results
        format: Output format ('json' or 'txt')
    """
    ensure_dir(output_dir)
    
    # Write individual CQ results
    for cq_id, result in results.items():
        if format == "json":
            out_file = output_dir / f"{cq_id.lower()}.json"
            with open(out_file, "w") as f:
                json.dump(result, f, indent=2, default=str)
        else:
            out_file = output_dir / f"{cq_id.lower()}.txt"
            with open(out_file, "w") as f:
                f.write(f"# {cq_id}\n")
                if cq_id in CQ_DESCRIPTIONS:
                    f.write(f"# {CQ_DESCRIPTIONS[cq_id]}\n\n")
                f.write(result.get("answer", "No answer generated"))
                f.write("\n\n---\n")
                f.write(f"Iterations: {result.get('iterations', 'N/A')}\n")
                f.write(f"Tool calls: {len(result.get('tool_calls', []))}\n")
    
    # Write summary
    summary_file = output_dir / "SUMMARY.json"
    summary = {
        "total_cqs": len(results),
        "successful": sum(1 for r in results.values() if "answer" in r and "error" not in r),
        "cqs": {cq_id: {
            "iterations": r.get("iterations"),
            "tool_calls": len(r.get("tool_calls", [])),
            "has_error": "error" in r,
        } for cq_id, r in results.items()},
    }
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nResults written to: {output_dir}")


def check_api_key(provider_name: str) -> bool:
    """Check if the required API key is set."""
    if provider_name in ("mock", "ollama"):
        return True  # No API key needed
    
    key_var = f"{provider_name.upper()}_API_KEY"
    if not os.getenv(key_var):
        print(f"Error: {key_var} environment variable not set.")
        print(f"\nSet it with:")
        print(f"  export {key_var}=your-api-key")
        print(f"\nOr use --provider ollama for local inference (no API key needed).")
        print(f"Or use --provider mock for testing without any LLM.")
        return False
    return True


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run MCBO competency questions with LLM agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a specific CQ
  mcbo-agent-eval --data-dir data.sample --cq CQ1
  
  # Ask a natural language question
  mcbo-agent-eval --data-dir data.sample --cq "Which culture conditions produce peak productivity?"
  
  # Run all CQs
  mcbo-agent-eval --data-dir data.sample --all
  
  # Use OpenAI instead of Anthropic
  mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider openai
  
  # Test without API (mock provider)
  mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider mock
  
  # List available CQs
  mcbo-agent-eval --list-cqs

Environment Variables:
  MCBO_LLM_PROVIDER     - Default provider ('anthropic', 'openai', 'mock')
  ANTHROPIC_API_KEY     - Anthropic API key
  OPENAI_API_KEY        - OpenAI API key
"""
    )
    
    # Data source arguments
    parser.add_argument("--data-dir", type=str, default=None,
                        help="Data directory (uses config-by-convention for graph.ttl)")
    parser.add_argument("--graph", type=str, default=None,
                        help="Path to the merged evaluation graph TTL file")
    parser.add_argument("--ontology", type=str, default=None,
                        help="Path to ontology TTL (if not using merged graph)")
    parser.add_argument("--instances", type=str, default=None,
                        help="Path to instances TTL (if not using merged graph)")
    
    # Query arguments
    parser.add_argument("--cq", type=str, default=None,
                        help="CQ ID (e.g., 'CQ1') or natural language question")
    parser.add_argument("--all", action="store_true",
                        help="Run all competency questions")
    parser.add_argument("--list-cqs", action="store_true",
                        help="List available competency questions and exit")
    
    # Provider arguments
    parser.add_argument("--provider", type=str, default=None,
                        choices=["anthropic", "openai", "ollama", "mock"],
                        help="LLM provider (default: from MCBO_LLM_PROVIDER or 'anthropic')")
    parser.add_argument("--model", type=str, default=None,
                        help="Model name (provider-specific)")
    
    # Output arguments
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory for results")
    parser.add_argument("--format", type=str, default="json",
                        choices=["json", "txt"],
                        help="Output format (default: json)")
    
    # Misc arguments
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output (show tool calls)")
    parser.add_argument("--max-iterations", type=int, default=10,
                        help="Maximum tool call iterations (default: 10)")
    
    args = parser.parse_args()
    
    # Handle --list-cqs
    if args.list_cqs:
        print_cq_list()
        return
    
    # Validate arguments
    if not args.cq and not args.all:
        parser.error("Provide --cq <question> or --all to run queries. Use --list-cqs to see options.")
    
    # Resolve data paths
    data_dir = Path(args.data_dir) if args.data_dir else None
    
    if data_dir:
        graph_path = args.graph or str(resolve_data_dir_path(data_dir, "graph"))
        output_dir = Path(args.output) if args.output else resolve_data_dir_path(data_dir, "results")
    else:
        graph_path = args.graph
        output_dir = Path(args.output) if args.output else Path("agent_results")
    
    # Check provider and API key
    provider_name = args.provider or os.getenv("MCBO_LLM_PROVIDER", "anthropic")
    if not check_api_key(provider_name):
        sys.exit(1)
    
    # Get provider
    try:
        provider = get_provider(provider_name)
        if args.model:
            provider.model = args.model
        print(f"Using LLM provider: {provider.get_name()}")
    except Exception as e:
        print(f"Error initializing provider: {e}")
        sys.exit(1)
    
    # Load graph
    print("Loading graph...", end="", flush=True)
    load_start = time.time()
    try:
        if graph_path:
            ontology_path = Path("ontology/mcbo.owl.ttl")
            graph_paths = [Path(graph_path)]
            if ontology_path.exists() and str(ontology_path) != graph_path:
                graph_paths.insert(0, ontology_path)
            g = load_graphs(graph_paths)
        elif args.ontology and args.instances:
            g = load_graphs([Path(args.ontology), Path(args.instances)])
        else:
            parser.error("Provide --graph, --data-dir, or both --ontology and --instances")
            return
        
        load_time = time.time() - load_start
        print(f" loaded {len(g):,} triples in {format_duration(load_time)}")
    except Exception as e:
        print(f"\nError loading graph: {e}")
        sys.exit(1)
    
    # Create orchestrator
    orchestrator = AgentOrchestrator(
        graph=g,
        provider=provider,
        max_iterations=args.max_iterations,
        verbose=args.verbose,
    )
    
    # Run queries
    results = {}
    total_start = time.time()
    
    if args.all:
        # Run all CQs
        print(f"\nRunning all {len(CQ_DESCRIPTIONS)} competency questions...")
        for cq_id in CQ_DESCRIPTIONS.keys():
            cq_start = time.time()
            result = run_single_cq(orchestrator, cq_id, args.verbose)
            cq_time = time.time() - cq_start
            result["duration"] = cq_time
            results[cq_id] = result
            
            # Print answer preview
            if "answer" in result:
                print(f"\nAnswer ({result.get('iterations', 0)} iterations, {format_duration(cq_time)}):")
                answer = result["answer"]
                if len(answer) > 500:
                    print(answer[:500] + "...")
                else:
                    print(answer)
            else:
                print(f"Error: {result.get('error', 'Unknown error')}")
    else:
        # Run single CQ or question
        cq_start = time.time()
        result = run_single_cq(orchestrator, args.cq, args.verbose)
        cq_time = time.time() - cq_start
        result["duration"] = cq_time
        
        # Use CQ ID as key if it's a known CQ, otherwise use 'query'
        cq_upper = args.cq.upper().strip()
        key = cq_upper if cq_upper in CQ_DESCRIPTIONS else "query"
        results[key] = result
        
        # Print full answer
        if "answer" in result:
            print(f"\nAnswer ({result.get('iterations', 0)} iterations, {format_duration(cq_time)}):")
            print(result["answer"])
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
    
    total_time = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Total time: {format_duration(total_time)}")
    
    # Write results
    if output_dir:
        write_results(results, output_dir, args.format)


if __name__ == "__main__":
    main()

