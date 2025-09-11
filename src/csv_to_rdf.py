#!/usr/bin/env python3
"""
Convert bioprocessing metadata CSV to RDF instances for MCBO ontology
Assumes CSV with columns like: RunAccession, SampleAccession, CellLine, ProcessType, etc.
"""

import pandas as pd
import rdflib
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, XSD

def safe_numeric_conversion(value, default_type=XSD.string):
    """Safely convert a value to numeric, falling back to string if needed"""
    if pd.isna(value):
        return None, None
    
    value_str = str(value).strip()
    if value_str.lower() in ['na', 'nan', '', 'null']:
        return None, None
    
    # Try to convert to float
    try:
        numeric_val = float(value_str)
        return numeric_val, XSD.decimal
    except (ValueError, TypeError):
        # Return as string if not numeric
        return value_str, default_type

# Define namespaces
MCBO = Namespace("http://example.org/mcbo#")
OBO = Namespace("http://purl.obolibrary.org/obo/")

def create_graph():
    """Initialize RDF graph with ontology import"""
    g = Graph()
    g.bind("mcbo", MCBO)
    g.bind("obo", OBO)
    
    # Import the ontology schema
    g.add((URIRef("http://example.org/mcbo"), RDF.type, URIRef("http://www.w3.org/2002/07/owl#Ontology")))
    
    return g

def map_process_type(process_type_str):
    """Map CSV process type strings to ontology classes"""
    mapping = {
        'Fed-batch': MCBO.FedBatchCultureProcess,
        'Batch': MCBO.BatchCultureProcess, 
        'Perfusion': MCBO.PerfusionCultureProcess,
        'Chemostat': MCBO.ChemostatCultureProcess,
        # Add more mappings as needed
    }
    return mapping.get(process_type_str, MCBO.CellCultureProcess)

def map_cell_line(cell_line_str):
    """Map cell line strings to ontology classes"""
    if 'CHO' in cell_line_str.upper():
        return MCBO.CHOCellLine
    elif 'HEK293' in cell_line_str.upper():
        return MCBO.HEK293CellLine
    else:
        return MCBO.CellLine

def convert_csv_to_rdf(csv_file_path, output_file):
    """Convert CSV metadata to RDF instances"""
    
    # Read CSV
    df = pd.read_csv(csv_file_path)
    
    # Create RDF graph
    g = create_graph()
    
    # Process each row
    for idx, row in df.iterrows():
        # Create unique URIs for instances
        run_uri = MCBO[f"run_{row.get('RunAccession', idx)}"]
        sample_uri = MCBO[f"sample_{row.get('SampleAccession', idx)}"] 
        
        # Create process instance
        process_class = map_process_type(row.get('ProcessType', ''))
        g.add((run_uri, RDF.type, process_class))
        
        # Add process properties
        if pd.notna(row.get('Temperature')):
            conditions_uri = MCBO[f"conditions_{idx}"]
            g.add((conditions_uri, RDF.type, MCBO.CultureConditions))
            g.add((conditions_uri, MCBO.hasTemperature, Literal(row['Temperature'], datatype=XSD.decimal)))
            g.add((run_uri, MCBO.hasCultureConditions, conditions_uri))
        
        # Create sample instance
        g.add((sample_uri, RDF.type, MCBO.BioprocessSample))
        g.add((sample_uri, MCBO.hasSampleId, Literal(row.get('SampleAccession', f'sample_{idx}'))))
        
        # Link process to sample
        g.add((run_uri, MCBO.hasProcessOutput, sample_uri))
        
        # Add cell line
        if pd.notna(row.get('CellLine')):
            cell_line_uri = MCBO[f"cellline_{row['CellLine'].replace(' ', '_')}"]
            cell_line_class = map_cell_line(row['CellLine'])
            g.add((cell_line_uri, RDF.type, cell_line_class))
            g.add((run_uri, MCBO.usesCellLine, cell_line_uri))
        
        # Add culture phase if available
        if pd.notna(row.get('CulturePhase')):
            if 'stationary' in row['CulturePhase'].lower():
                phase_uri = MCBO[f"phase_{idx}"]
                g.add((phase_uri, RDF.type, MCBO.StationaryPhase))
                g.add((sample_uri, MCBO.inCulturePhase, phase_uri))
        
        # Add productivity if available
        if pd.notna(row.get('Productivity')):
            productivity_uri = MCBO[f"productivity_{idx}"]

            prod_value = str(row['Productivity']).strip()

            # Map to specific productivity classes from your TTL
            productivity_class_mapping = {
                'VeryHigh': MCBO.VeryHighProductivity,
                'High': MCBO.HighProductivity,
                'Medium': MCBO.MediumProductivity,
                'LowMedium': MCBO.LowMediumProductivity,
                'Low': MCBO.LowProductivity
            }
            # Numeric mapping for analysis
            productivity_numeric_mapping = { 
                'VeryHigh': 5,
                'High': 4,
                'Medium': 3,
                'LowMedium': 2,
                'Low': 1    
            }
            if prod_value in productivity_class_mapping:
                # use the specific productivity class from the TTL
                g.add((productivity_uri, RDF.type, productivity_class_mapping[prod_value]))
                # Add the categorical value as a string
                g.add((productivity_uri, MCBO.hasProductivityCategory, Literal(prod_value)))
                # Add the numeric value for analysis
                numeric_val = productivity_numeric_mapping[prod_value]
                g.add((productivity_uri, MCBO.hasProductivityValue, Literal(numeric_val, datatype=XSD.decimal)))

            elif prod_value not in ['NA', 'na', 'NaN', 'nan', 'Null', 'null', 'NONE','none', 'None', '']:
                # fall back for unexpected values
                g.add((productivity_uri, RDF.type, MCBO.ProductivityMeasurement))
                g.add((productivity_uri, MCBO.hasProductivityValue, Literal(prod_value)))

            g.add((run_uri, MCBO.hasProductivityMeasurement, productivity_uri))

            #g.add((productivity_uri, RDF.type, productivity_class_mapping.get(prod_val, MCBO.ProductivityMeasurement)))
            #g.add((productivity_uri, RDF.type, MCBO.ProductivityMeasurement))
            #g.add((productivity_uri, MCBO.hasProductivityValue, Literal(row['Productivity'], datatype=XSD.decimal)))
            #g.add((run_uri, MCBO.hasProductivityMeasurement, productivity_uri))
        
        # Add glutamine concentration with safe conversion
        glut_val, glut_type = safe_numeric_conversion(row.get('GlutamineConcentration'))
        if glut_val is not None:
            glut_uri = MCBO[f"glutamine_{idx}"]
            g.add((glut_uri, RDF.type, MCBO.GlutamineConcentration))
            g.add((glut_uri, MCBO.hasConcentrationValue, Literal(glut_val, datatype=glut_type)))
            if pd.notna(row.get('Glutamine')):  # Unit
                g.add((glut_uri, MCBO.hasConcentrationUnit, Literal(row['Glutamine'])))
    
    # Serialize to file
    g.serialize(destination=output_file, format='turtle')
    print(f"Converted {len(df)} rows to RDF. Output: {output_file}")
    
    return g

def validate_conversion(graph):
    """Simple validation of converted data"""
    
    # Count instances by type
    print("\nValidation Results:")
    
    process_count = len(list(graph.subjects(RDF.type, MCBO.CellCultureProcess)))
    print(f"Total processes: {process_count}")
    
    sample_count = len(list(graph.subjects(RDF.type, MCBO.BioprocessSample)))
    print(f"Total samples: {sample_count}")
    
    cho_count = len(list(graph.subjects(RDF.type, MCBO.CHOCellLine)))
    print(f"CHO cell lines: {cho_count}")

if __name__ == "__main__":
    print("Starting CSV to RDF conversion...")

    # make the output file a command line argument
    import argparse
    parser = argparse.ArgumentParser(description='Convert CSV to RDF')
    parser.add_argument('--csv_file', type=str, help='The CSV file to convert', default="data/sample_metadata.csv")
    # make output file default ="data/processed/mcbo_instances.ttl"
    parser.add_argument('--output_file', type=str, help='The output file to save the RDF to', default="data/processed/mcbo_instances.ttl")
    parser.add_argument('--validate', type=bool, help='Validate the conversion', default=True)
    args = parser.parse_args()
    csv_file = args.csv_file
    output_file = args.output_file

    print(f"Converting CSV file: {csv_file}")
    
    # Convert CSV to RDF
    graph = convert_csv_to_rdf(csv_file, output_file)
    
    print("Conversion complete. Validating...")
    
    # Validate conversion
    if args.validate:
        validate_conversion(graph)
