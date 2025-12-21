"""
MCBO - Mammalian Cell BioProcess Ontology Python Package

This package provides utilities for working with MCBO RDF data:
- Namespace definitions
- Graph utilities (loading, creation, serialization)
- CSV to RDF conversion
"""

from .namespaces import (
    MCBO,
    OBO,
    BFO_HAS_PART,
    RO_HAS_PARTICIPANT,
    RO_HAS_QUALITY,
    IAO_IS_ABOUT,
    RDF,
    RDFS,
    XSD,
)

from .graph_utils import (
    iri_safe,
    safe_numeric,
    create_graph,
    load_graph,
    load_graphs,
    ensure_dir,
    ensure_parent_dir,
    get_case_insensitive,
    is_truthy,
)

from .csv_to_rdf import (
    convert_csv_to_rdf,
    load_expression_matrix,
    load_expression_dir,
    add_expression_data,
)

__version__ = "0.1.0"

__all__ = [
    # Namespaces
    "MCBO",
    "OBO",
    "BFO_HAS_PART",
    "RO_HAS_PARTICIPANT",
    "RO_HAS_QUALITY",
    "IAO_IS_ABOUT",
    "RDF",
    "RDFS",
    "XSD",
    # Graph utilities
    "iri_safe",
    "safe_numeric",
    "create_graph",
    "load_graph",
    "load_graphs",
    "ensure_dir",
    "ensure_parent_dir",
    "get_case_insensitive",
    "is_truthy",
    # CSV conversion
    "convert_csv_to_rdf",
    "load_expression_matrix",
    "load_expression_dir",
    "add_expression_data",
]

