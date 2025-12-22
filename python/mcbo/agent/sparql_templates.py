"""
Parameterized SPARQL templates for MCBO agent data fetching.

These templates are designed to fetch raw data that the agent can then
analyze using statistical tools. Parameters are denoted by {param_name}
and are filled in by the format_template function.
"""

from typing import Optional

# Standard prefixes used across all templates
PREFIXES = """
PREFIX mcbo: <http://example.org/mcbo#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ro: <http://purl.obolibrary.org/obo/RO_>
PREFIX bfo: <http://purl.obolibrary.org/obo/BFO_>
PREFIX uo: <http://purl.obolibrary.org/obo/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

SPARQL_TEMPLATES = {
    # CQ1: Culture conditions and productivity data
    "culture_conditions_productivity": """
SELECT ?runId ?cellLine ?cellLineLabel ?temperature ?pH ?dissolvedOxygen 
       ?productivityValue ?productivityCategory ?processType
WHERE {{
    ?process a ?processType .
    ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
    BIND(REPLACE(STR(?process), ".*#", "") AS ?runId)
    
    ?process mcbo:usesCellLine ?cellLine .
    OPTIONAL {{ ?cellLine rdfs:label ?cellLineLabel }}
    
    ?process ro:0000057 ?system .
    ?system a mcbo:CellCultureSystem .
    ?system ro:0000086 ?ccq .
    
    OPTIONAL {{ ?ccq mcbo:hasTemperature ?temperature }}
    OPTIONAL {{ ?ccq mcbo:hasPH ?pH }}
    OPTIONAL {{ ?ccq mcbo:hasDissolvedOxygen ?dissolvedOxygen }}
    
    ?process mcbo:hasProductivityMeasurement ?pm .
    ?pm mcbo:hasProductivityValue ?productivityValue .
    OPTIONAL {{ ?pm mcbo:hasProductivityCategory ?productivityCategory }}
    
    {filter_clause}
}}
ORDER BY DESC(?productivityValue)
""",

    # CQ2: Cell lines with overexpressed genes
    "cell_lines_overexpression": """
SELECT ?cellLine ?cellLineLabel ?cellLineType ?gene ?geneLabel 
       ?productivityValue ?productivityCategory
WHERE {{
    ?cellLine a ?cellLineType .
    ?cellLineType rdfs:subClassOf* mcbo:CellLine .
    OPTIONAL {{ ?cellLine rdfs:label ?cellLineLabel }}
    
    ?cellLine mcbo:overexpressesGene ?gene .
    OPTIONAL {{ ?gene rdfs:label ?geneLabel }}
    
    OPTIONAL {{
        ?process mcbo:usesCellLine ?cellLine ;
                 mcbo:hasProductivityMeasurement ?pm .
        ?pm mcbo:hasProductivityValue ?productivityValue .
        OPTIONAL {{ ?pm mcbo:hasProductivityCategory ?productivityCategory }}
    }}
    
    {filter_clause}
}}
ORDER BY ?cellLine ?gene
""",

    # CQ3: Nutrient concentrations with viability at specific day
    "nutrient_viability_by_day": """
SELECT ?cellLine ?cellLineLabel ?nutrientLabel ?concentrationValue ?concentrationUnit
       ?viableCellDensity ?collectionDay ?sampleId
WHERE {{
    ?viability a mcbo:CellViabilityMeasurement ;
               mcbo:hasViableCellDensity ?viableCellDensity .
    
    ?sample mcbo:hasCellViabilityMeasurement ?viability ;
            mcbo:hasCollectionDay ?collectionDay .
    BIND(STR(?sample) AS ?sampleId)
    
    ?process mcbo:hasProcessOutput ?sample .
    OPTIONAL {{ 
        ?process mcbo:usesCellLine ?cellLine .
        ?cellLine rdfs:label ?cellLineLabel .
    }}
    
    ?process ro:0000057 ?system .
    ?system a mcbo:CellCultureSystem ;
            bfo:0000051 ?medium .
    
    ?medium mcbo:hasNutrientConcentration ?nutrient .
    ?nutrient mcbo:hasConcentrationValue ?concentrationValue ;
              mcbo:hasConcentrationUnit ?concentrationUnit .
    OPTIONAL {{ ?nutrient rdfs:label ?nutrientLabel }}
    
    {filter_clause}
}}
ORDER BY DESC(?viableCellDensity) ?cellLine
""",

    # CQ4: Gene expression by clone
    "gene_expression_by_clone": """
SELECT ?gene ?geneLabel ?clone ?cloneLabel ?parentLine ?parentLineLabel
       ?expressionValue ?sampleId
WHERE {{
    ?clone a mcbo:Clone .
    ?clone rdfs:label ?cloneLabel .
    
    ?parentLine mcbo:hasClone ?clone .
    OPTIONAL {{ ?parentLine rdfs:label ?parentLineLabel }}
    
    ?process mcbo:usesCellLine ?parentLine ;
             mcbo:hasProcessOutput ?sample .
    BIND(STR(?sample) AS ?sampleId)
    
    ?sample mcbo:hasGeneExpression ?exprMeas .
    ?exprMeas uo:IAO_0000136 ?gene ;
              mcbo:hasExpressionValue ?expressionValue .
    OPTIONAL {{ ?gene rdfs:label ?geneLabel }}
    
    {filter_clause}
}}
ORDER BY ?gene ?clone
""",

    # CQ5: Gene expression by process type (for differential analysis)
    # Use cell_line_filter param like: FILTER(CONTAINS(?cellLineLabel, "HEK293"))
    "gene_expression_by_process_type": """
SELECT ?gene ?geneLabel ?expressionValue ?processType ?cellLine ?cellLineLabel ?sampleId
WHERE {{
    ?process a ?processType .
    ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
    
    ?process mcbo:hasProcessOutput ?sample .
    BIND(STR(?sample) AS ?sampleId)
    
    ?process mcbo:usesCellLine ?cellLine .
    ?cellLine rdfs:label ?cellLineLabel .
    
    ?sample mcbo:hasGeneExpression ?expr .
    ?expr uo:IAO_0000136 ?gene ;
          mcbo:hasExpressionValue ?expressionValue .
    OPTIONAL {{ ?gene rdfs:label ?geneLabel }}
    
    {filter_clause}
}}
ORDER BY ?gene ?processType
""",

    # CQ6: Gene expression with productivity in stationary phase
    "gene_expression_stationary_productivity": """
SELECT ?gene ?geneLabel ?expressionValue ?productivityValue ?productivityCategory
       ?cellLine ?cellLineLabel ?processType ?sampleId
WHERE {{
    ?process a ?processType .
    ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
    
    ?process mcbo:hasProductivityMeasurement ?prodMeas ;
             mcbo:hasProcessOutput ?sample .
    BIND(STR(?sample) AS ?sampleId)
    
    OPTIONAL {{ ?process mcbo:usesCellLine ?cellLine . ?cellLine rdfs:label ?cellLineLabel }}
    
    ?prodMeas mcbo:hasProductivityValue ?productivityValue .
    OPTIONAL {{ ?prodMeas mcbo:hasProductivityCategory ?productivityCategory }}
    
    ?sample a mcbo:BioprocessSample ;
            mcbo:inCulturePhase ?phase .
    ?phase a mcbo:StationaryPhase .
    
    ?sample mcbo:hasGeneExpression ?exprMeas .
    ?exprMeas uo:IAO_0000136 ?gene ;
              mcbo:hasExpressionValue ?expressionValue .
    OPTIONAL {{ ?gene rdfs:label ?geneLabel }}
    
    {filter_clause}
}}
ORDER BY DESC(?productivityValue) DESC(?expressionValue) ?gene
""",

    # CQ7: Gene expression with viability percentage
    "gene_expression_by_viability": """
SELECT ?gene ?geneLabel ?expressionValue ?viabilityPercentage ?sampleId ?cellLine
WHERE {{
    ?sample a mcbo:BioprocessSample ;
            mcbo:hasCellViabilityMeasurement ?viability .
    BIND(STR(?sample) AS ?sampleId)
    
    ?viability a mcbo:CellViabilityMeasurement ;
               mcbo:hasViabilityPercentage ?viabilityPercentage .
    
    ?sample mcbo:hasGeneExpression ?exprMeas .
    ?exprMeas uo:IAO_0000136 ?gene ;
              mcbo:hasExpressionValue ?expressionValue .
    OPTIONAL {{ ?gene rdfs:label ?geneLabel }}
    
    OPTIONAL {{
        ?process mcbo:hasProcessOutput ?sample ;
                 mcbo:usesCellLine ?cellLine .
    }}
    
    {filter_clause}
}}
ORDER BY DESC(?viabilityPercentage) ?gene
""",

    # CQ8: Cell lines/clones with product quality measurements
    "cell_lines_product_quality": """
SELECT ?cellLine ?cellLineLabel ?clone ?cloneLabel ?product ?productLabel
       ?qualityMeas ?qualityLabel ?titerValue ?processType
WHERE {{
    ?process a ?processType .
    ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
    
    ?process mcbo:usesCellLine ?cellLine .
    OPTIONAL {{ ?cellLine rdfs:label ?cellLineLabel }}
    
    OPTIONAL {{
        ?cellLine mcbo:hasClone ?clone .
        ?clone rdfs:label ?cloneLabel .
    }}
    
    ?process mcbo:hasProduct ?product .
    OPTIONAL {{ ?product rdfs:label ?productLabel }}
    OPTIONAL {{ ?product mcbo:hasTiterValue ?titerValue }}
    
    ?product mcbo:hasQualityMeasurement ?qualityMeas .
    OPTIONAL {{ ?qualityMeas rdfs:label ?qualityLabel }}
    
    {filter_clause}
}}
ORDER BY DESC(?titerValue) ?cellLine
""",

    # Utility: Get all genes in the graph
    "all_genes": """
SELECT ?gene ?geneLabel
WHERE {{
    ?gene a mcbo:Gene .
    OPTIONAL {{ ?gene rdfs:label ?geneLabel }}
}}
ORDER BY ?geneLabel
""",

    # Utility: Get all cell lines in the graph
    "all_cell_lines": """
SELECT ?cellLine ?cellLineLabel ?cellLineType
WHERE {{
    ?cellLine a ?cellLineType .
    ?cellLineType rdfs:subClassOf* mcbo:CellLine .
    OPTIONAL {{ ?cellLine rdfs:label ?cellLineLabel }}
}}
ORDER BY ?cellLineLabel
""",

    # Utility: Get all process types and counts
    "process_type_summary": """
SELECT ?processType (COUNT(?process) AS ?count)
WHERE {{
    ?process a ?processType .
    ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
}}
GROUP BY ?processType
ORDER BY DESC(?count)
""",
}


def get_template(template_name: str) -> str:
    """Get a SPARQL template by name.
    
    Args:
        template_name: Name of the template (key in SPARQL_TEMPLATES)
        
    Returns:
        The template string with prefixes prepended
        
    Raises:
        KeyError: If template_name is not found
    """
    if template_name not in SPARQL_TEMPLATES:
        available = ", ".join(sorted(SPARQL_TEMPLATES.keys()))
        raise KeyError(f"Unknown template '{template_name}'. Available: {available}")
    return PREFIXES + SPARQL_TEMPLATES[template_name]


def format_template(
    template_name: str,
    filter_clause: str = "",
    **kwargs
) -> str:
    """Format a SPARQL template with parameters.
    
    Args:
        template_name: Name of the template
        filter_clause: Optional FILTER clause to add (without FILTER keyword)
        **kwargs: Additional format parameters for the template
        
    Returns:
        Formatted SPARQL query ready for execution
        
    Example:
        >>> query = format_template(
        ...     "culture_conditions_productivity",
        ...     filter_clause="FILTER(?productivityValue > 3)"
        ... )
    """
    template = get_template(template_name)
    
    # Build filter clause
    if filter_clause:
        if not filter_clause.strip().upper().startswith("FILTER"):
            filter_clause = f"FILTER({filter_clause})"
    
    return template.format(filter_clause=filter_clause, **kwargs)


def list_templates() -> list[str]:
    """List all available template names."""
    return sorted(SPARQL_TEMPLATES.keys())


# CQ-specific template mappings for the orchestrator
CQ_TEMPLATE_MAPPING = {
    "CQ1": "culture_conditions_productivity",
    "CQ2": "cell_lines_overexpression", 
    "CQ3": "nutrient_viability_by_day",
    "CQ4": "gene_expression_by_clone",
    "CQ5": "gene_expression_by_process_type",
    "CQ6": "gene_expression_stationary_productivity",
    "CQ7": "gene_expression_by_viability",
    "CQ8": "cell_lines_product_quality",
}


__all__ = [
    "SPARQL_TEMPLATES",
    "PREFIXES",
    "get_template",
    "format_template",
    "list_templates",
    "CQ_TEMPLATE_MAPPING",
]

