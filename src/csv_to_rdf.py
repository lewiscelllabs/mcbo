#!/usr/bin/env python3
"""
Convert bioprocessing metadata CSV to RDF instances for the MCBO ontology.

Key design change (BFO-aligned):
- Culture conditions are modeled as qualities of a *CellCultureSystem* (a material entity),
  not as qualities of the process.
- Each run/process has_participant a CellCultureSystem.
- The CellCultureSystem has_quality CultureConditions (quality) with temperature/pH/DO literals.

For backward compatibility with earlier CQs, we ALSO assert:
- run mcbo:hasCultureConditions conditions
so existing SPARQL can still run while the ontology/refactor converges.
"""

import argparse
from pathlib import Path

import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

# Namespaces
MCBO = Namespace("http://example.org/mcbo#")
OBO  = Namespace("http://purl.obolibrary.org/obo/")
OWL  = Namespace("http://www.w3.org/2002/07/owl#")
RO   = Namespace("http://purl.obolibrary.org/obo/RO_")

# Common OBO relations
BFO_HAS_PART = OBO.BFO_0000051           # has part
RO_HAS_PARTICIPANT = RO["0000057"]     # has participant
RO_HAS_QUALITY = RO["0000086"]         # has quality


def safe_numeric_conversion(value, default_type=XSD.string):
    """Safely convert a value to float when possible; otherwise return string."""
    if pd.isna(value):
        return None, None
    value_str = str(value).strip()
    if value_str.lower() in {"na", "nan", "", "null"}:
        return None, None
    try:
        return float(value_str), XSD.decimal
    except (ValueError, TypeError):
        return value_str, default_type


def create_graph() -> Graph:
    """Initialize RDF graph."""
    g = Graph()
    g.bind("mcbo", MCBO)
    g.bind("obo", OBO)
    g.bind("owl", OWL)
    g.bind("ro", RO)
    return g


def map_process_type(process_type_str):
    """Map CSV process type strings to ontology classes."""
    s = str(process_type_str).strip() if process_type_str is not None else ""
    mapping = {
        "Batch": MCBO.BatchCultureProcess,
        "Plate": MCBO.BatchCultureProcess,
        "FedBatch": MCBO.FedBatchCultureProcess,
        "Fed-batch": MCBO.FedBatchCultureProcess,
        "Continuous": MCBO.ContinuousCultureProcess,
        "Continuous culture": MCBO.ContinuousCultureProcess,
        "Perfusion": MCBO.PerfusionCultureProcess,
        "Pefusion": MCBO.PerfusionCultureProcess,  # common typo
        "Chemostat": MCBO.ChemostatCultureProcess,
        "Unknown": MCBO.UnknownCultureProcess,
        "NA": MCBO.UnknownCultureProcess,
        "nan": MCBO.UnknownCultureProcess,
        "NAN": MCBO.UnknownCultureProcess,
        "": MCBO.UnknownCultureProcess,
    }
    return mapping.get(s, MCBO.UnknownCultureProcess)


def map_cell_line_class(cell_line_str):
    """Map cell line strings to ontology classes."""
    s = str(cell_line_str).upper()
    if "CHO" in s:
        return MCBO.CHOCellLine
    if "HEK293" in s or "HEK-293" in s:
        return MCBO.HEK293CellLine
    return MCBO.CellLine


def iri_safe(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in s)


def convert_csv_to_rdf(csv_file_path: str, output_file: str) -> Graph:
    df = pd.read_csv(csv_file_path)
    g = create_graph()

    created_samples = set()
    created_cell_lines = set()

    for idx, row in df.iterrows():
        run_id = row.get("RunAccession", idx)
        sample_id = row.get("SampleAccession", idx)

        run_uri = MCBO[f"run_{iri_safe(str(run_id))}"]
        sample_uri = MCBO[f"sample_{iri_safe(str(sample_id))}"]

        # Process instance (run)
        process_class = map_process_type(row.get("ProcessType", ""))
        g.add((run_uri, RDF.type, process_class))

        # Cell culture system (material entity participating in the process)
        system_uri = MCBO[f"system_{idx}"]
        g.add((system_uri, RDF.type, MCBO.CellCultureSystem))
        g.add((run_uri, RO_HAS_PARTICIPANT, system_uri))

        # Sample instance (avoid duplicates)
        if sample_uri not in created_samples:
            g.add((sample_uri, RDF.type, MCBO.BioprocessSample))
            g.add((sample_uri, MCBO.hasSampleId, Literal(str(sample_id))))
            created_samples.add(sample_uri)

        # Link process to sample (output)
        g.add((run_uri, MCBO.hasProcessOutput, sample_uri))

        # Cell line (participant + system part)
        cell_line_val = row.get("CellLine")
        if pd.notna(cell_line_val):
            cell_line_str = str(cell_line_val).strip()
            cell_line_uri = MCBO[f"cellline_{iri_safe(cell_line_str)}"]
            cell_line_class = map_cell_line_class(cell_line_str)

            if cell_line_uri not in created_cell_lines:
                g.add((cell_line_uri, RDF.type, cell_line_class))
                g.add((cell_line_uri, RDFS.label, Literal(cell_line_str)))
                created_cell_lines.add(cell_line_uri)

            g.add((run_uri, MCBO.usesCellLine, cell_line_uri))
            g.add((run_uri, RO_HAS_PARTICIPANT, cell_line_uri))
            g.add((system_uri, BFO_HAS_PART, cell_line_uri))

            # Product type heuristic (if present)
            product_type = row.get("ProductType")
            if pd.notna(product_type) and str(product_type).strip().lower() not in {"na", "nan", ""}:
                if str(product_type).strip().lower() == "mab":
                    g.add((cell_line_uri, MCBO.overexpressesGene, MCBO.antibodyGene))
                    g.add((cell_line_uri, MCBO.producesProduct, Literal("mAb")))

        # Culture medium as part of system (if present)
        medium_val = row.get("CultureMedium") or row.get("Medium")
        if pd.notna(medium_val):
            medium_str = str(medium_val).strip()
            medium_uri = MCBO[f"medium_{iri_safe(medium_str)}"]
            g.add((medium_uri, RDF.type, MCBO.CultureMedium))
            g.add((medium_uri, RDFS.label, Literal(medium_str)))
            g.add((system_uri, BFO_HAS_PART, medium_uri))

        # Culture conditions as qualities of the system
        # We create a CultureConditions individual (typed as a quality in the ontology)
        conditions_uri = MCBO[f"conditions_{idx}"]
        g.add((conditions_uri, RDF.type, MCBO.CultureConditions))
        g.add((system_uri, RO_HAS_QUALITY, conditions_uri))

        # Backward-compatibility shortcut for existing CQs
        g.add((run_uri, MCBO.hasCultureConditions, conditions_uri))

        temp_val, temp_type = safe_numeric_conversion(row.get("Temperature"))
        if temp_val is not None:
            g.add((conditions_uri, MCBO.hasTemperature, Literal(temp_val, datatype=temp_type)))

        ph_val, ph_type = safe_numeric_conversion(row.get("pH") if "pH" in row else row.get("PH"))
        if ph_val is not None:
            g.add((conditions_uri, MCBO.hasPH, Literal(ph_val, datatype=ph_type)))

        do_val, do_type = safe_numeric_conversion(row.get("DissolvedOxygen") or row.get("DO"))
        if do_val is not None:
            g.add((conditions_uri, MCBO.hasDissolvedOxygen, Literal(do_val, datatype=do_type)))

        # Culture phase (attach to sample)
        phase_val = row.get("CulturePhase")
        if pd.notna(phase_val):
            phase_str = str(phase_val).lower()
            phase_uri = MCBO[f"phase_{idx}"]
            if "stationary" in phase_str:
                g.add((phase_uri, RDF.type, MCBO.StationaryPhase))
            elif "exponential" in phase_str or "log" in phase_str:
                g.add((phase_uri, RDF.type, MCBO.ExponentialPhase))
            else:
                g.add((phase_uri, RDF.type, MCBO.CulturePhase))
            g.add((sample_uri, MCBO.inCulturePhase, phase_uri))

        # Productivity measurement (attach to run)
        prod_val = row.get("Productivity")
        if pd.notna(prod_val):
            prod_str = str(prod_val).strip()
            prod_uri = MCBO[f"productivity_{idx}"]

            category_to_class = {
                "VeryHigh": MCBO.VeryHighProductivity,
                "High": MCBO.HighProductivity,
                "Medium": MCBO.MediumProductivity,
                "LowMedium": MCBO.LowMediumProductivity,
                "Low": MCBO.LowProductivity,
            }
            category_to_numeric = {"VeryHigh": 5, "High": 4, "Medium": 3, "LowMedium": 2, "Low": 1}

            if prod_str in category_to_class:
                g.add((prod_uri, RDF.type, category_to_class[prod_str]))
                g.add((prod_uri, MCBO.hasProductivityCategory, Literal(prod_str)))
                g.add((prod_uri, MCBO.hasProductivityValue, Literal(category_to_numeric[prod_str], datatype=XSD.decimal)))
            elif prod_str.lower() not in {"na", "nan", "null", "none", ""}:
                # Fallback: preserve the raw value
                g.add((prod_uri, RDF.type, MCBO.ProductivityMeasurement))
                g.add((prod_uri, MCBO.hasProductivityValue, Literal(prod_str)))

            g.add((run_uri, MCBO.hasProductivityMeasurement, prod_uri))

        # Glutamine concentration (example nutrient concentration)
        glut_val, glut_type = safe_numeric_conversion(row.get("GlutamineConcentration"))
        if glut_val is not None:
            glut_uri = MCBO[f"glutamine_{idx}"]
            g.add((glut_uri, RDF.type, MCBO.GlutamineConcentration))
            g.add((glut_uri, MCBO.hasConcentrationValue, Literal(glut_val, datatype=glut_type)))

            unit_val = row.get("GlutamineUnit") or row.get("Glutamine")
            if pd.notna(unit_val):
                g.add((glut_uri, MCBO.hasConcentrationUnit, Literal(str(unit_val).strip())))

            # Optionally associate to the system as a measured quality/context
            g.add((system_uri, RO_HAS_QUALITY, glut_uri))

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out_path), format="turtle")
    print(f"Converted {len(df)} rows to RDF. Output: {output_file}")
    return g


def validate_conversion(graph: Graph) -> None:
    print("\nValidation Results:")
    # NOTE: these counts depend on how classes are asserted in the TBox; for data-level checks,
    # we count instances of the concrete process subclasses.
    process_instances = set(graph.subjects(RDF.type, None))
    print(f"Total rdf:type assertions: {len(list(process_instances))}")

    sample_count = len(set(graph.subjects(RDF.type, MCBO.BioprocessSample)))
    print(f"Total samples: {sample_count}")

    cho_count = len(set(graph.subjects(RDF.type, MCBO.CHOCellLine)))
    print(f"CHO cell lines: {cho_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert CSV metadata to RDF")
    parser.add_argument("--csv_file", type=str, default="data/sample_metadata.csv",
                        help="Input CSV file")
    parser.add_argument("--output_file", type=str, default="data/processed/mcbo_instances.ttl",
                        help="Output TTL file")
    parser.add_argument("--validate", action="store_true", help="Run basic validation")

    args = parser.parse_args()

    print(f"Converting CSV file: {args.csv_file}")
    graph = convert_csv_to_rdf(args.csv_file, args.output_file)

    if args.validate:
        print("Conversion complete. Validating...")
        validate_conversion(graph)
