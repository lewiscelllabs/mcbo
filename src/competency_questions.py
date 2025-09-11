#!/usr/bin/env python3
"""
Execute competency questions against MCBO ontology with real instance data
"""

import rdflib
from rdflib import Graph, Namespace
from rdflib.plugins.sparql import prepareQuery
import pandas as pd

# Define namespaces
MCBO = Namespace("http://example.org/mcbo#")
OBO = Namespace("http://purl.obolibrary.org/obo/")

class MCBOQueryEngine:
    def __init__(self, ontology_file="./ontology/mcbo.owl.ttl", instances_file="./data/processed/mcbo_instances.ttl"):
        """Initialize query engine with ontology and instance data"""
        self.graph = Graph()
        self.graph.bind("mcbo", MCBO)
        self.graph.bind("obo", OBO)
        
        # Load ontology schema
        print(f"Loading ontology: {ontology_file}")
        self.graph.parse(ontology_file, format="turtle")
        
        # Load instance data if available
        try:
            print(f"Loading instances: {instances_file}")
            self.graph.parse(instances_file, format="turtle") 
            print(f"Total triples loaded: {len(self.graph)}")
        except FileNotFoundError:
            print(f"Instance file {instances_file} not found. Using schema only.")

    def execute_cq1_high_productivity(self, cell_line_filter=None):
        print("CQ1: Culture conditions for HIGH productivity samples")

        query_str = """
        PREFIX mcbo: <http://example.org/mcbo#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?cellLine ?temperature ?pH ?dissolvedOxygen ?productivityType WHERE {
            ?process a ?processType .
            ?processType rdfs:subClassOf* mcbo:CellCultureProcess .

            ?process mcbo:usesCellLine ?cellLine .
            ?process mcbo:hasCultureConditions ?conditions .
            ?process mcbo:hasProductivityMeasurement ?prodMeasure .

            OPTIONAL { ?conditions mcbo:hasTemperature ?temperature }
            OPTIONAL { ?conditions mcbo:hasPH ?pH }
            OPTIONAL { ?conditions mcbo:hasDissolvedOxygen ?dissolvedOxygen }

            # Filter for high productivity classes only
            ?prodMeasure a ?productivityType .
            FILTER(?productivityType IN (
                mcbo:VeryHighProductivity, 
                mcbo:HighProductivity,
                mcbo:MediumProductivity
            ))
        }
        ORDER BY ?productivityType ?cellLine
        """

        if cell_line_filter:
            query_str = query_str.replace(
                "FILTER(?productivityType",
                f"FILTER(CONTAINS(STR(?cellLine), '{cell_line_filter}') && ?productivityType"
            )

        return self._execute_query(query_str, "CQ1: High Productivity Culture Conditions")


    def execute_cq1_culture_productivity(self, cell_line_filter=None):
        print("CQ1: Under what culture conditions (pH, dissolved oxygen, temperature) do cell line X cells reach peak product K productivity?")
        
        query_str = """
        PREFIX mcbo: <http://example.org/mcbo#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?cellLine ?temperature ?pH ?dissolvedOxygen ?productivity WHERE {
            ?process a ?processType .
            ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
            
            ?process mcbo:usesCellLine ?cellLine .
            ?process mcbo:hasCultureConditions ?conditions .
            ?process mcbo:hasProductivityMeasurement ?prodMeasure .
            
            OPTIONAL { ?conditions mcbo:hasTemperature ?temperature }
            OPTIONAL { ?conditions mcbo:hasPH ?pH }
            OPTIONAL { ?conditions mcbo:hasDissolvedOxygen ?dissolvedOxygen }
            
            ?prodMeasure mcbo:hasProductivityValue ?productivity .
            
            FILTER(?productivity > 0)
        }
        ORDER BY DESC(?productivity)
        """
        
        if cell_line_filter:
            # Add cell line filter
            query_str = query_str.replace(
                "FILTER(?productivity > 0)", 
                f"FILTER(?productivity > 0 && CONTAINS(STR(?cellLine), '{cell_line_filter}'))"
            )
        
        return self._execute_query(query_str, "CQ1: Culture Conditions vs Productivity")

    def execute_cq2_cho_engineering(self):
        """
        CQ2: Which CHO cell lines have been engineered to overexpress gene Y?
        """
        
        query_str = """
        PREFIX mcbo: <http://example.org/mcbo#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?choLine ?gene WHERE {
            ?choLine a ?cellLineType .
            ?cellLineType rdfs:subClassOf* mcbo:CHOCellLine .
            
            ?choLine mcbo:overexpressesGene ?gene .
        }
        """
        
        return self._execute_query(query_str, "CQ2: CHO Engineering")

    def execute_cq3_nutrient_viability(self, min_viability=90, target_day=7):
        """
        CQ3: Which nutrient concentrations are most associated with 
        viable cell density above Z at day N of culture?
        """
        
        query_str = f"""
        PREFIX mcbo: <http://example.org/mcbo#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?sample ?nutrientConc ?concValue ?viability ?viableDensity ?collectionDay WHERE {{
            ?process a ?processType .
            ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
            
            ?process mcbo:hasProcessOutput ?sample .
            ?process mcbo:usesMedium ?medium .
            
            ?medium mcbo:hasNutrientConcentration ?nutrientConc .
            ?nutrientConc mcbo:hasConcentrationValue ?concValue .
            
            ?sample mcbo:hasCellViabilityMeasurement ?viabMeasure .
            ?viabMeasure mcbo:hasViabilityPercentage ?viability .
            ?viabMeasure mcbo:hasViableCellDensity ?viableDensity .
            
            OPTIONAL {{ ?sample mcbo:hasCollectionDay ?collectionDay }}
            
            FILTER(?viability >= {min_viability})
            FILTER(?collectionDay = {target_day} || !BOUND(?collectionDay))
        }}
        ORDER BY DESC(?viableDensity)
        """
        
        return self._execute_query(query_str, f"CQ3: Nutrients vs Viability (>{min_viability}% at day {target_day})")

    def execute_cq5_process_comparison(self):
        """
        CQ5: What pathways are differentially expressed under Fed-batch vs Perfusion in cell line X?
        """

        
        # query_str = """
        # PREFIX mcbo: <http://example.org/mcbo#>
        # PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        # PREFIX obo:  <http://purl.obolibrary.org/obo/>
        # 
        # SELECT ?processType ?cellLine ?sample ?gene ?expression WHERE {
        # ?process a ?processType .
        # ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
        # 
        # ?process mcbo:usesCellLine ?cellLine .
        # ?process mcbo:hasProcessOutput ?sample .
        # 
        # ?sample mcbo:hasGeneExpression ?geneExpr .
        # ?geneExpr mcbo:hasExpressionValue ?expression .
        # ?geneExpr obo:IAO_0000136 ?gene .
        # 
        # FILTER(?processType = mcbo:FedBatchCultureProcess || 
        # ?processType = mcbo:PerfusionCultureProcess)
        # }
        # ORDER BY ?processType ?gene
        # """

        query_str = """
        PREFIX mcbo: <http://example.org/mcbo#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?processType (COUNT(?process) as ?count) WHERE {
          ?process a ?processType .
          ?processType rdfs:subClassOf* mcbo:CellCultureProcess .
        }
        GROUP BY ?processType
        """
        
        return self._execute_query(query_str, "CQ5: Process Type Comparison")

    def _execute_query(self, query_str, query_name):
        """Execute SPARQL query and return results"""
        print(f"\n{'='*60}")
        print(f"Executing: {query_name}")
        print(f"{'='*60}")
        
        try:
            query = prepareQuery(query_str)
            results = self.graph.query(query)
            
            # Convert to pandas DataFrame for easier analysis
            if len(results) > 0:
                df = pd.DataFrame([dict(row.asdict()) for row in results])
                print(f"Found {len(df)} results:")
                print(df.to_string(index=False))
                return df
            else:
                print("No results found. This may indicate:")
                print("- No instance data loaded")
                print("- Data doesn't match query patterns") 
                print("- Need to populate more instance properties")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"Query execution error: {e}")
            return pd.DataFrame()

    def generate_sample_data(self):
        """Generate some sample instances for testing CQs"""
        print("\nGenerating sample instance data...")
        
        # Sample CHO process with culture conditions and productivity
        sample_data = """
        @prefix mcbo: <http://example.org/mcbo#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        
        mcbo:run_001 a mcbo:FedBatchCultureProcess ;
            mcbo:usesCellLine mcbo:cho_k1_line ;
            mcbo:hasCultureConditions mcbo:conditions_001 ;
            mcbo:hasProductivityMeasurement mcbo:prod_001 ;
            mcbo:hasProcessOutput mcbo:sample_001 .
            
        mcbo:cho_k1_line a mcbo:CHOCellLine ;
            mcbo:overexpressesGene mcbo:gene_mab1 .
            
        mcbo:conditions_001 a mcbo:CultureConditions ;
            mcbo:hasTemperature "37.0"^^xsd:decimal ;
            mcbo:hasPH "7.1"^^xsd:decimal ;
            mcbo:hasDissolvedOxygen "50.0"^^xsd:decimal .
            
        mcbo:prod_001 a mcbo:ProductivityMeasurement ;
            mcbo:hasProductivityValue "2.5"^^xsd:decimal .
            
        mcbo:sample_001 a mcbo:BioprocessSample ;
            mcbo:hasCollectionDay "7"^^xsd:integer ;
            mcbo:hasCellViabilityMeasurement mcbo:viab_001 .
            
        mcbo:viab_001 a mcbo:CellViabilityMeasurement ;
            mcbo:hasViabilityPercentage "92.0"^^xsd:decimal ;
            mcbo:hasViableCellDensity "8500000.0"^^xsd:decimal .
        """
        
        self.graph.parse(data=sample_data, format="turtle")
        print("Sample data added to graph")

def main():
    """Main execution function"""
    
    # Initialize query engine
    engine = MCBOQueryEngine("./ontology/mcbo.owl.ttl", "./data/processed/mcbo_instances.ttl")  # Your ontology file
    
    # Generate sample data for testing
    #engine.generate_sample_data()
    
    # Execute competency questions
    print("Testing Competency Questions with Sample Data")
    print("=" * 60)
    
    # CQ1: Culture conditions vs productivity
    cq1_results = engine.execute_cq1_culture_productivity()
    cq1b_results = engine.execute_cq1_high_productivity()
    
    # CQ2: CHO engineering
    cq2_results = engine.execute_cq2_cho_engineering()
    
    # CQ3: Nutrient concentrations vs viability
    cq3_results = engine.execute_cq3_nutrient_viability(min_viability=90)
    
    # CQ5: Process type comparison
    cq5_results = engine.execute_cq5_process_comparison()
    
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"CQ1 results: {len(cq1_results)} rows")
    #print(f"CQ1b results: {len(cq1b_results)} rows")
    print(f"CQ2 results: {len(cq2_results)} rows") 
    print(f"CQ3 results: {len(cq3_results)} rows")
    print(f"CQ5 results: {len(cq5_results)} rows")

if __name__ == "__main__":
    main()
