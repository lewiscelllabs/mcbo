"""
Shared RDF namespace definitions for MCBO.
"""

from rdflib import Namespace
from rdflib.namespace import RDF, RDFS, XSD

# Core namespaces
MCBO = Namespace("http://example.org/mcbo#")
OBO = Namespace("http://purl.obolibrary.org/obo/")

# Common OBO relations (as URIRefs for consistency)
BFO_HAS_PART = OBO.BFO_0000051        # has part
RO_HAS_PARTICIPANT = OBO.RO_0000057   # has participant
RO_HAS_QUALITY = OBO.RO_0000086       # has quality
IAO_IS_ABOUT = OBO.IAO_0000136        # is about

# Re-export commonly used rdflib namespaces
__all__ = [
    "MCBO",
    "OBO", 
    "BFO_HAS_PART",
    "RO_HAS_PARTICIPANT",
    "RO_HAS_QUALITY",
    "IAO_IS_ABOUT",
    "RDF",
    "RDFS",
    "XSD",
]

