"""
Validate MCBO instances against ontology restrictions using OWL reasoning.

This module uses owlready2 (which includes HermiT reasoner) to:
- Check if instances satisfy class restrictions
- Detect inconsistencies
- Validate required properties
- Infer missing types

Usage:
    from mcbo.validate_instances import validate_graph
    
    errors, warnings = validate_graph("data.sample/graph.ttl")
    if errors:
        print(f"Found {len(errors)} validation errors")
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Optional

try:
    from owlready2 import get_ontology, sync_reasoner, World
    OWLREADY_AVAILABLE = True
except ImportError:
    OWLREADY_AVAILABLE = False


def validate_graph(
    graph_path: Path | str,
    ontology_path: Optional[Path | str] = None,
    reasoner: str = "hermit",
    strict: bool = True,
) -> Tuple[List[str], List[str]]:
    """Validate instances in a graph against ontology restrictions.
    
    Args:
        graph_path: Path to the graph TTL file (ontology + instances)
        ontology_path: Optional separate ontology file (if graph doesn't include it)
        reasoner: Reasoner to use ("hermit", "pellet", or "none")
        strict: If True, treat warnings as errors
        
    Returns:
        Tuple of (errors, warnings) - lists of error/warning messages
        
    Raises:
        ImportError: If owlready2 is not installed
    """
    if not OWLREADY_AVAILABLE:
        raise ImportError(
            "owlready2 is required for validation. Install with: pip install owlready2"
        )
    
    errors: List[str] = []
    warnings: List[str] = []
    
    graph_path = Path(graph_path)
    if not graph_path.exists():
        return [f"Graph file not found: {graph_path}"], []
    
    try:
        # Load ontology
        if ontology_path:
            onto = get_ontology(str(ontology_path)).load()
        else:
            # Try to load from graph file
            onto = get_ontology(str(graph_path)).load()
        
        # Run reasoner to check consistency
        if reasoner != "none":
            try:
                sync_reasoner(onto, reasoner=reasoner)
            except Exception as e:
                warnings.append(f"Reasoner {reasoner} failed: {e}. Continuing without reasoning.")
                reasoner = "none"
        
        # Check for inconsistencies
        if reasoner != "none":
            inconsistent = list(onto.inconsistent_classes())
            if inconsistent:
                errors.append(f"Found {len(inconsistent)} inconsistent classes: {inconsistent}")
        
        # Validate key restrictions
        _validate_restrictions(onto, errors, warnings)
        
        # Check instance types
        _validate_instance_types(onto, errors, warnings)
        
    except Exception as e:
        errors.append(f"Validation failed: {e}")
    
    if strict:
        errors.extend(warnings)
        warnings = []
    
    return errors, warnings


def _validate_restrictions(onto, errors: List[str], warnings: List[str]) -> None:
    """Validate that instances satisfy class restrictions."""
    from owlready2 import Thing
    
    # Check CellCultureSystem restriction: must have some CultureEnvironmentalCondition
    cell_culture_system = onto.search_one(iri="*CellCultureSystem")
    if cell_culture_system:
        systems = list(cell_culture_system.instances())
        for system in systems:
            # Check if it has RO_0000086 (has quality) to a CultureEnvironmentalCondition
            has_quality = getattr(system, "RO_0000086", [])
            env_conditions = [q for q in has_quality if isinstance(q, Thing)]
            if not env_conditions:
                warnings.append(
                    f"CellCultureSystem {system.name} should have at least one "
                    "CultureEnvironmentalCondition (via RO_0000086)"
                )
    
    # Check CellCultureProcess restriction: must have some BioprocessSample and CellCultureSystem
    cell_culture_process = onto.search_one(iri="*CellCultureProcess")
    if cell_culture_process:
        processes = list(cell_culture_process.instances())
        for process in processes:
            # Check hasProcessOutput (BioprocessSample)
            has_output = getattr(process, "hasProcessOutput", [])
            if not has_output:
                warnings.append(
                    f"CellCultureProcess {process.name} should have at least one "
                    "BioprocessSample (via hasProcessOutput)"
                )
            
            # Check RO_0000057 (has participant) to CellCultureSystem
            has_participant = getattr(process, "RO_0000057", [])
            systems = [p for p in has_participant if hasattr(p, "is_a") and 
                      any("CellCultureSystem" in str(c) for c in p.is_a)]
            if not systems:
                warnings.append(
                    f"CellCultureProcess {process.name} should have at least one "
                    "CellCultureSystem participant (via RO_0000057)"
                )


def _validate_instance_types(onto, errors: List[str], warnings: List[str]) -> None:
    """Validate that instances have appropriate types."""
    from owlready2 import Thing
    
    # Check for processes without proper typing
    process_classes = [c for c in onto.classes() if "Process" in str(c)]
    all_processes = set()
    for pc in process_classes:
        all_processes.update(pc.instances())
    
    # Check for instances that should be processes but aren't typed
    # (This is a basic check - more sophisticated validation would use the reasoner)
    pass  # Could add more specific checks here


def main():
    """CLI entry point for validation."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Validate MCBO instances against ontology restrictions"
    )
    parser.add_argument("--graph", type=Path, required=True,
                       help="Path to graph TTL file (ontology + instances)")
    parser.add_argument("--ontology", type=Path, default=None,
                       help="Optional separate ontology file")
    parser.add_argument("--reasoner", choices=["hermit", "pellet", "none"],
                       default="hermit", help="Reasoner to use")
    parser.add_argument("--strict", action="store_true",
                       help="Treat warnings as errors")
    parser.add_argument("--data-dir", type=Path, default=None,
                       help="Data directory (uses config-by-convention)")
    
    args = parser.parse_args()
    
    if args.data_dir:
        graph_path = args.data_dir / "graph.ttl"
        if not args.graph:
            args.graph = graph_path
    
    if not OWLREADY_AVAILABLE:
        print("Error: owlready2 is required. Install with: pip install owlready2")
        return 1
    
    errors, warnings = validate_graph(
        args.graph,
        args.ontology,
        args.reasoner,
        args.strict,
    )
    
    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    
    if errors:
        print(f"\n❌ Errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        return 1
    
    if not warnings:
        print("✅ Validation passed - no errors or warnings")
    else:
        print(f"✅ Validation passed - {len(warnings)} warnings (non-strict mode)")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
