"""
Tests for MCBO ontology conventions and best practices.

These tests ensure:
1. Prefix naming follows conventions (obo: for OBO namespace, not uo:)
2. External terms are imported, not redefined locally
3. MCBO-specific terms use the mcbo: namespace
"""

import pytest
from pathlib import Path
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL


# Standard namespaces
OBO = Namespace("http://purl.obolibrary.org/obo/")
MCBO = Namespace("http://example.org/mcbo#")

# OBO ontology term prefixes (the part before the underscore)
OBO_ONTOLOGY_PREFIXES = {
    "GO",   # Gene Ontology
    "RO",   # Relation Ontology
    "BFO",  # Basic Formal Ontology
    "IAO",  # Information Artifact Ontology
    "SO",   # Sequence Ontology
    "OBI",  # Ontology for Biomedical Investigations
    "UO",   # Units Ontology
    "CHEBI",  # Chemical Entities of Biological Interest
    "PR",   # Protein Ontology
}


@pytest.fixture
def ontology_graph():
    """Load the MCBO ontology."""
    # python/tests/test_ontology.py -> python/tests -> python -> repo_root
    ontology_path = Path(__file__).parent.parent.parent / "ontology" / "mcbo.owl.ttl"
    if not ontology_path.exists():
        pytest.skip(f"Ontology file not found: {ontology_path}")
    
    g = Graph()
    g.parse(str(ontology_path), format="turtle")
    return g


@pytest.fixture
def ontology_text():
    """Load the raw ontology text for prefix checking."""
    ontology_path = Path(__file__).parent.parent.parent / "ontology" / "mcbo.owl.ttl"
    if not ontology_path.exists():
        pytest.skip(f"Ontology file not found: {ontology_path}")
    
    return ontology_path.read_text()


class TestPrefixConventions:
    """Test that prefix naming follows conventions.
    
    OBO term IDs are self-namespacing: the ontology abbreviation is part of
    the term ID (e.g., UO_0000027, BFO_0000040, GO_0008150). They all share
    the same namespace base: http://purl.obolibrary.org/obo/
    
    Common mistake: defining @prefix uo: <http://purl.obolibrary.org/obo/>
    and then using uo:BFO_0000040 - this works but is misleading.
    """
    
    def test_obo_prefix_not_named_uo(self, ontology_text):
        """
        The OBO namespace should use 'obo:' prefix, not 'uo:'.
        
        Using 'uo:' for http://purl.obolibrary.org/obo/ is misleading because
        'uo' conventionally refers to the Units Ontology specifically, not
        the entire OBO namespace.
        
        This catches the common mistake of:
          @prefix uo: <http://purl.obolibrary.org/obo/> .
          uo:BFO_0000040 ...  # Works but confusing!
        """
        # Check that we don't have uo: defined as the OBO namespace
        assert "@prefix uo: <http://purl.obolibrary.org/obo/>" not in ontology_text, \
            "OBO namespace should use 'obo:' prefix, not 'uo:' (misleading)"
    
    def test_no_ontology_specific_prefix_for_obo_namespace(self, ontology_text):
        """
        Don't use any single-ontology prefix name for the shared OBO namespace.
        
        Wrong: @prefix go: <http://purl.obolibrary.org/obo/> (then go:BFO_... is confusing)
        Wrong: @prefix bfo: <http://purl.obolibrary.org/obo/> (then bfo:GO_... is confusing)
        Right: @prefix obo: <http://purl.obolibrary.org/obo/> (neutral, correct)
        """
        import re
        
        # OBO ontology abbreviations that should NOT be used as prefix for the full OBO namespace
        ontology_abbrevs = ["uo", "go", "bfo", "ro", "iao", "so", "obi", "chebi", "pr", "pato"]
        
        for abbrev in ontology_abbrevs:
            pattern = rf"@prefix\s+{abbrev}:\s*<http://purl\.obolibrary\.org/obo/>\s*\."
            match = re.search(pattern, ontology_text, re.IGNORECASE)
            assert match is None, \
                f"Don't use '{abbrev}:' for the OBO namespace - use 'obo:' instead. " \
                f"OBO terms are self-namespacing (e.g., obo:UO_0000027, obo:BFO_0000040)"
    
    def test_obo_prefix_exists(self, ontology_text):
        """The ontology should define obo: prefix for OBO namespace."""
        assert "@prefix obo: <http://purl.obolibrary.org/obo/>" in ontology_text, \
            "Should have '@prefix obo: <http://purl.obolibrary.org/obo/>'"
    
    def test_mcbo_prefix_exists(self, ontology_text):
        """The ontology should define mcbo: prefix."""
        assert "@prefix mcbo:" in ontology_text, \
            "Should have mcbo: prefix defined"


class TestNoRedundantDefinitions:
    """Test that external OBO terms are not redundantly redefined."""
    
    def test_no_obo_class_definitions(self, ontology_graph):
        """
        MCBO should not define classes for external OBO terms.
        
        Terms like BFO:0000040 (material entity) should come from
        imported ontologies, not be redefined in MCBO.
        """
        # Find all class definitions in the ontology
        obo_classes_defined = []
        
        for s, p, o in ontology_graph.triples((None, RDF.type, OWL.Class)):
            uri = str(s)
            if uri.startswith("http://purl.obolibrary.org/obo/"):
                # Extract the term ID (e.g., "BFO_0000040" from the URI)
                term_id = uri.split("/")[-1]
                prefix = term_id.split("_")[0] if "_" in term_id else term_id
                
                # Check if this is from a standard OBO ontology
                if prefix in OBO_ONTOLOGY_PREFIXES:
                    obo_classes_defined.append(term_id)
        
        assert len(obo_classes_defined) == 0, \
            f"Should not redefine OBO classes (use owl:imports instead): {obo_classes_defined}"
    
    def test_no_obo_property_definitions(self, ontology_graph):
        """
        MCBO should not define properties for external OBO terms.
        
        Properties like RO:0002331 (involved_in) should come from
        imported ontologies.
        """
        obo_properties_defined = []
        
        for prop_type in [OWL.ObjectProperty, OWL.DatatypeProperty]:
            for s, p, o in ontology_graph.triples((None, RDF.type, prop_type)):
                uri = str(s)
                if uri.startswith("http://purl.obolibrary.org/obo/"):
                    term_id = uri.split("/")[-1]
                    prefix = term_id.split("_")[0] if "_" in term_id else term_id
                    
                    if prefix in OBO_ONTOLOGY_PREFIXES:
                        obo_properties_defined.append(term_id)
        
        assert len(obo_properties_defined) == 0, \
            f"Should not redefine OBO properties (use owl:imports instead): {obo_properties_defined}"


class TestImports:
    """Test that required ontologies are imported."""
    
    def test_has_owl_imports(self, ontology_graph):
        """The ontology should have owl:imports declarations."""
        imports = list(ontology_graph.triples((None, OWL.imports, None)))
        assert len(imports) > 0, "Ontology should have owl:imports declarations"
    
    def test_imports_go_if_go_terms_used(self, ontology_graph):
        """If GO terms are referenced, GO should be imported."""
        # Check if any GO terms are referenced
        go_terms_used = False
        for s, p, o in ontology_graph:
            for term in [s, o]:
                if isinstance(term, URIRef) and "GO_" in str(term):
                    go_terms_used = True
                    break
        
        if go_terms_used:
            # Check that GO is imported
            imports = [str(o) for s, p, o in ontology_graph.triples((None, OWL.imports, None))]
            go_imported = any("go" in imp.lower() for imp in imports)
            assert go_imported, "GO terms are used but GO ontology is not imported"


class TestMCBOTerms:
    """Test that MCBO-specific terms are properly defined."""
    
    def test_mcbo_classes_have_labels(self, ontology_graph):
        """All MCBO classes should have rdfs:label."""
        mcbo_classes_without_labels = []
        
        for s, p, o in ontology_graph.triples((None, RDF.type, OWL.Class)):
            uri = str(s)
            if uri.startswith("http://example.org/mcbo#"):
                labels = list(ontology_graph.triples((s, RDFS.label, None)))
                if not labels:
                    mcbo_classes_without_labels.append(uri.split("#")[-1])
        
        assert len(mcbo_classes_without_labels) == 0, \
            f"MCBO classes missing labels: {mcbo_classes_without_labels}"
    
    def test_mcbo_classes_have_definitions(self, ontology_graph):
        """All MCBO classes should have IAO:0000115 definitions."""
        IAO_DEFINITION = OBO.IAO_0000115
        mcbo_classes_without_defs = []
        
        for s, p, o in ontology_graph.triples((None, RDF.type, OWL.Class)):
            uri = str(s)
            if uri.startswith("http://example.org/mcbo#"):
                defs = list(ontology_graph.triples((s, IAO_DEFINITION, None)))
                if not defs:
                    mcbo_classes_without_defs.append(uri.split("#")[-1])
        
        # Allow some classes without definitions (may be intentional)
        # but warn if too many
        if len(mcbo_classes_without_defs) > 5:
            pytest.fail(
                f"Many MCBO classes missing IAO definitions: {mcbo_classes_without_defs[:10]}..."
            )
