#!/usr/bin/env python3
"""
csv_to_rdf.py — Convert bioprocess metadata CSV to RDF instances for MCBO (ABox).

This version matches the updated MCBO design (NO backward-compat mcbo:hasCultureConditions):

  - A run is a process instance (BatchCultureProcess, FedBatchCultureProcess, ...)
  - The run obo:RO_0000057 (has participant) a mcbo:CellCultureSystem (material entity)
  - The CellCultureSystem obo:RO_0000086 (has quality) a mcbo:CultureConditionQuality instance
  - Temperature/pH/DO literals are attached to the CultureConditionQuality instance

CQ2 support (CHO engineering / overexpression):
  The public sample_metadata.csv does not contain a dedicated "OverexpressedGene" column.
  Instead, it includes:
    - Producer (boolean): whether the line is a producer/engineered line
    - ProductType (string): product identifier; often a gene/protein symbol (e.g., HGF, CXCL13),
      and sometimes broader categories (e.g., mAb, BsAb, Control).
  This script therefore asserts mcbo:overexpressesGene based on:
    - If Producer==True AND ProductType is non-empty and not "Control", then:
        cellLine mcbo:overexpressesGene gene_<ProductType>
      For mAb/BsAb, it uses a shared placeholder gene individual mcbo:AntibodyProductGene.

If you later add a dedicated gene column (e.g., OverexpressedGene), this script will
use it automatically (see GENE_COLUMN_CANDIDATES).

Output:
  - ABox only (instances). To run CQs that rely on subclass hierarchies (rdfs:subClassOf*),
    query a merged graph (ontology + instances) or load both in your SPARQL runner.

"""

import argparse
import re
from pathlib import Path

import pandas as pd
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS, XSD

MCBO = Namespace("http://example.org/mcbo#")
OBO  = Namespace("http://purl.obolibrary.org/obo/")

# Relations (OBO IRIs so SPARQL engines behave consistently)
BFO_HAS_PART       = OBO.BFO_0000051   # has part
RO_HAS_PARTICIPANT = OBO.RO_0000057    # has participant
RO_HAS_QUALITY     = OBO.RO_0000086    # has quality

# Candidate columns (case-insensitive) if you later add explicit gene fields
GENE_COLUMN_CANDIDATES = [
    "OverexpressedGene", "OverexpressedGenes",
    "EngineeringGene", "EngineeringGenes",
    "OverexpressesGene", "OverexpressesGenes",
    "Gene", "Genes", "GeneSymbol", "GeneSymbols",
]

# Split multiple genes / products in a cell by these separators
GENE_SPLIT_RE = re.compile(r"[;,|/]+|\s+")


def iri_safe(s: str) -> str:
    s = str(s).strip()
    if not s:
        return "EMPTY"
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in s)


def safe_numeric(value):
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
    g = Graph()
    g.bind("mcbo", MCBO)
    g.bind("obo", OBO)
    return g


def map_process_type(process_type_str):
    s = str(process_type_str).strip() if process_type_str is not None else ""
    mapping = {
        "Batch": MCBO.BatchCultureProcess,
        "Plate": MCBO.BatchCultureProcess,
        "FedBatch": MCBO.FedBatchCultureProcess,
        "Fed-batch": MCBO.FedBatchCultureProcess,
        "Fed Batch": MCBO.FedBatchCultureProcess,
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


def map_cell_line_class(cell_line_str: str):
    s = str(cell_line_str).upper()
    if "CHO" in s:
        return MCBO.CHOCellLine
    if "HEK293" in s or "HEK-293" in s:
        return MCBO.HEK293CellLine
    return MCBO.CellLine


def get_case_insensitive(row, colname: str):
    """Return row value for a column name case-insensitively, else None."""
    if colname in row:
        return row.get(colname)
    # pandas Series supports .index
    for c in row.index:
        if str(c).strip().lower() == colname.strip().lower():
            return row.get(c)
    return None


def extract_gene_symbols(row) -> list[str]:
    """Extract gene symbols from any explicit gene columns if present."""
    for c in GENE_COLUMN_CANDIDATES:
        v = get_case_insensitive(row, c)
        if pd.notna(v) and str(v).strip():
            raw = str(v).strip()
            parts = [p for p in GENE_SPLIT_RE.split(raw) if p]
            return parts
    return []


def is_truthy(v) -> bool:
    if pd.isna(v):
        return False
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"true", "t", "1", "yes", "y"}


def convert_csv_to_rdf(csv_file_path: str, output_file: str) -> Graph:
    df = pd.read_csv(csv_file_path)
    g = create_graph()

    created_samples = set()
    created_cell_lines = set()
    created_media = set()
    created_genes = set()

    # A shared placeholder gene for antibody-like products
    antibody_gene = MCBO.AntibodyProductGene
    g.add((antibody_gene, RDF.type, MCBO.Gene))
    g.add((antibody_gene, RDFS.label, Literal("antibody product gene")))

    for idx, row in df.iterrows():
        run_id = row.get("RunAccession", idx)
        sample_id = row.get("SampleAccession", idx)

        run_uri = MCBO[f"run_{iri_safe(run_id)}"]
        sample_uri = MCBO[f"sample_{iri_safe(sample_id)}"]

        # 1) Process instance (run)
        process_class = map_process_type(row.get("ProcessType", ""))
        g.add((run_uri, RDF.type, process_class))

        # 2) Cell culture system (material entity participant)
        system_uri = MCBO[f"system_{iri_safe(run_id)}"]
        g.add((system_uri, RDF.type, MCBO.CellCultureSystem))
        g.add((run_uri, RO_HAS_PARTICIPANT, system_uri))

        # 3) Sample instance + link as process output
        if sample_uri not in created_samples:
            g.add((sample_uri, RDF.type, MCBO.BioprocessSample))
            created_samples.add(sample_uri)
        g.add((run_uri, MCBO.hasProcessOutput, sample_uri))

        # 4) Cell line (participant + system part)
        cell_line_val = row.get("CellLine")
        cell_line_uri = None
        if pd.notna(cell_line_val) and str(cell_line_val).strip() != "":
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

        # 5) Culture medium (system part)
        medium_val = row.get("CultureMedium") or row.get("Medium")
        if pd.notna(medium_val) and str(medium_val).strip() != "":
            medium_str = str(medium_val).strip()
            medium_uri = MCBO[f"medium_{iri_safe(medium_str)}"]
            if medium_uri not in created_media:
                g.add((medium_uri, RDF.type, MCBO.CultureMedium))
                g.add((medium_uri, RDFS.label, Literal(medium_str)))
                created_media.add(medium_uri)
            g.add((system_uri, BFO_HAS_PART, medium_uri))

        # 6) Culture condition quality (quality of the system)
        ccq_uri = MCBO[f"culture_condition_quality_{iri_safe(run_id)}"]
        g.add((ccq_uri, RDF.type, MCBO.CultureConditionQuality))
        g.add((system_uri, RO_HAS_QUALITY, ccq_uri))

        temp_val, temp_dt = safe_numeric(row.get("Temperature"))
        if temp_val is not None:
            g.add((ccq_uri, MCBO.hasTemperature, Literal(temp_val, datatype=temp_dt)))

        ph_raw = row.get("pH") if "pH" in row else row.get("PH")
        ph_val, ph_dt = safe_numeric(ph_raw)
        if ph_val is not None:
            g.add((ccq_uri, MCBO.hasPH, Literal(ph_val, datatype=ph_dt)))

        do_raw = row.get("DissolvedOxygen") or row.get("DO")
        do_val, do_dt = safe_numeric(do_raw)
        if do_val is not None:
            g.add((ccq_uri, MCBO.hasDissolvedOxygen, Literal(do_val, datatype=do_dt)))

        # 7) Culture phase (attach to sample)
        phase_val = row.get("CulturePhase")
        if pd.notna(phase_val) and str(phase_val).strip() != "":
            phase_str = str(phase_val).lower()
            phase_uri = MCBO[f"phase_{iri_safe(run_id)}"]
            # Map some common abbreviations in sample_metadata.csv
            if "stationary" in phase_str or "stat" in phase_str:
                g.add((phase_uri, RDF.type, MCBO.StationaryPhase))
            elif "exponential" in phase_str or "log" in phase_str or "exp" in phase_str:
                g.add((phase_uri, RDF.type, MCBO.ExponentialPhase))
            else:
                g.add((phase_uri, RDF.type, MCBO.CulturePhase))
            g.add((sample_uri, MCBO.inCulturePhase, phase_uri))

        # 8) Productivity measurement (attach to run)
        prod_val = row.get("Productivity")
        if pd.notna(prod_val) and str(prod_val).strip() != "":
            prod_str = str(prod_val).strip()
            prod_uri = MCBO[f"productivity_{iri_safe(run_id)}"]

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
            else:
                g.add((prod_uri, RDF.type, MCBO.ProductivityMeasurement))
                # Try parse numeric
                pval, pdt = safe_numeric(prod_str)
                g.add((prod_uri, MCBO.hasProductivityValue, Literal(pval if pval is not None else prod_str, datatype=pdt or XSD.string)))

            g.add((run_uri, MCBO.hasProductivityMeasurement, prod_uri))

        # 9) CQ2 engineering: infer overexpressed gene from explicit gene columns or (Producer, ProductType)
        if cell_line_uri is not None:
            genes = extract_gene_symbols(row)

            producer = get_case_insensitive(row, "Producer")
            product_type = get_case_insensitive(row, "ProductType")

            # If no explicit gene columns, infer from Producer+ProductType
            if not genes and is_truthy(producer) and pd.notna(product_type) and str(product_type).strip():
                pt = str(product_type).strip()
                if pt.lower() != "control":
                    if pt.lower() in {"mab", "bsab"}:
                        genes = ["antibody product gene"]
                    else:
                        genes = [pt]

            for gene_sym in genes:
                gene_sym = gene_sym.strip()
                if not gene_sym:
                    continue
                if gene_sym.lower() == "antibody product gene":
                    gene_uri = antibody_gene
                else:
                    gene_uri = MCBO[f"gene_{iri_safe(gene_sym)}"]

                if gene_uri not in created_genes:
                    g.add((gene_uri, RDF.type, MCBO.Gene))
                    # Use the original string as label
                    g.add((gene_uri, RDFS.label, Literal(gene_sym)))
                    created_genes.add(gene_uri)

                g.add((cell_line_uri, MCBO.overexpressesGene, gene_uri))

                # Optional: keep a simple product string; do not invent product ontology individuals here
                if pd.notna(product_type) and str(product_type).strip():
                    g.add((cell_line_uri, MCBO.producesProduct, Literal(str(product_type).strip())))

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out_path), format="turtle")
    print(f"Converted {len(df)} rows to RDF. Output: {output_file}")
    return g


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert CSV metadata to RDF (MCBO instances)")
    parser.add_argument("--csv_file", type=str, default="data/sample_metadata.csv", help="Input CSV file")
    parser.add_argument("--output_file", type=str, default="data/processed/mcbo_instances.ttl", help="Output TTL file")
    args = parser.parse_args()
    convert_csv_to_rdf(args.csv_file, args.output_file)
