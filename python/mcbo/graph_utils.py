"""
Shared graph utilities for MCBO.
"""

import re
from pathlib import Path
from typing import List, Optional

import pandas as pd
from rdflib import Graph

from .namespaces import MCBO, OBO, XSD


def iri_safe(s: str) -> str:
    """Convert a string to a safe IRI fragment."""
    s = str(s).strip()
    if not s:
        return "EMPTY"
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in s)


def safe_numeric(value):
    """Parse a value as numeric, returning (value, datatype) or (None, None)."""
    if pd.isna(value):
        return None, None
    s = str(value).strip()
    if s.lower() in {"", "na", "nan", "null", "none"}:
        return None, None
    try:
        return float(s), XSD.decimal
    except (ValueError, TypeError):
        return s, XSD.string


def create_graph() -> Graph:
    """Create a new RDF graph with MCBO namespace bindings."""
    g = Graph()
    g.bind("mcbo", MCBO)
    g.bind("obo", OBO)
    return g


def load_graph(path: Path, format: str = "turtle") -> Graph:
    """Load an RDF graph from a file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    g = Graph()
    g.parse(str(path), format=format)
    return g


def load_graphs(paths: List[Path], format: str = "turtle") -> Graph:
    """Load multiple RDF files into a single graph."""
    g = Graph()
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        g.parse(str(p), format=format)
    return g


def ensure_dir(path: Path) -> None:
    """Ensure a directory exists, creating parent directories as needed."""
    path.mkdir(parents=True, exist_ok=True)


def ensure_parent_dir(path: Path) -> None:
    """Ensure the parent directory of a file path exists."""
    path.parent.mkdir(parents=True, exist_ok=True)


def get_case_insensitive(row, colname: str):
    """Return row value for a column name case-insensitively, else None."""
    if colname in row:
        return row.get(colname)
    # pandas Series supports .index
    for c in row.index:
        if str(c).strip().lower() == colname.strip().lower():
            return row.get(c)
    return None


def is_truthy(v) -> bool:
    """Check if a value is truthy (handles pandas NA, bool, string)."""
    if pd.isna(v):
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"true", "t", "1", "yes", "y"}


__all__ = [
    "iri_safe",
    "safe_numeric",
    "create_graph",
    "load_graph",
    "load_graphs",
    "ensure_dir",
    "ensure_parent_dir",
    "get_case_insensitive",
    "is_truthy",
]

