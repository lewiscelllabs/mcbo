#!/usr/bin/env python3
"""
csv_to_rdf.py — Core CSV-to-RDF conversion logic for MCBO (ABox).

NOTE: This module is used by scripts/build_graph.py for multi-study workflows.
      You can also use it standalone for single-file conversion.

This version matches the updated MCBO design (NO backward-compat mcbo:hasCultureConditions):

  - A run is a process instance (BatchCultureProcess, FedBatchCultureProcess, ...)
  - The run obo:RO_0000057 (has participant) a mcbo:CellCultureSystem (material entity)
  - The CellCultureSystem obo:RO_0000086 (has quality) a mcbo:CultureConditionQuality instance
  - Temperature/pH/DO literals are attached to the CultureConditionQuality instance

CQ support - columns used:
  CQ1: Temperature, pH, DissolvedOxygen, Productivity
  CQ2: CellLine, Producer, ProductType (or OverexpressedGene for explicit column)
  CQ3: CellLine, GlutamineConcentration, CollectionDay, ViableCellDensity
  CQ4: CellLine, CloneID, GeneSymbol, ExpressionValue, CulturePhase
  CQ5: ProcessType
  CQ6: CulturePhase, Productivity, GeneSymbol, ExpressionValue
  CQ7: ViabilityPercentage, GeneSymbol, ExpressionValue
  CQ8: CellLine, CloneID, TiterValue, QualityType

Note: GeneSymbol is for expression MEASUREMENTS (CQ4/6/7).
      OverexpressedGene is for cell line ENGINEERING (CQ2).
      These are semantically different and use separate columns!

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

# Candidate columns (case-insensitive) for CQ2 overexpression (NOT gene expression measurements)
# Note: GeneSymbol is intentionally NOT here - it's used for expression measurements (CQ4/6/7)
OVEREXPRESSION_COLUMN_CANDIDATES = [
    "OverexpressedGene", "OverexpressedGenes",
    "EngineeringGene", "EngineeringGenes",
    "OverexpressesGene", "OverexpressesGenes",
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


def extract_overexpressed_genes(row) -> list[str]:
    """Extract overexpressed gene symbols from explicit overexpression columns (CQ2).
    
    Note: This is separate from GeneSymbol which is used for expression measurements (CQ4/6/7).
    """
    for c in OVEREXPRESSION_COLUMN_CANDIDATES:
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

        # 9) CollectionDay and ViableCellDensity (CQ3)
        collection_day = get_case_insensitive(row, "CollectionDay")
        if pd.notna(collection_day) and str(collection_day).strip() not in {"", "NA", "nan"}:
            try:
                g.add((sample_uri, MCBO.hasCollectionDay, Literal(int(float(str(collection_day))), datatype=XSD.integer)))
            except (ValueError, TypeError):
                pass

        viable_cell_density = get_case_insensitive(row, "ViableCellDensity")
        if pd.notna(viable_cell_density) and str(viable_cell_density).strip() not in {"", "NA", "nan"}:
            viability_uri = MCBO[f"viability_{iri_safe(sample_id)}"]
            g.add((viability_uri, RDF.type, MCBO.CellViabilityMeasurement))
            vcd_val, vcd_dt = safe_numeric(viable_cell_density)
            if vcd_val is not None:
                g.add((viability_uri, MCBO.hasViableCellDensity, Literal(vcd_val, datatype=vcd_dt)))
            g.add((sample_uri, MCBO.hasCellViabilityMeasurement, viability_uri))

        # 10) ViabilityPercentage (CQ7)
        viability_pct = get_case_insensitive(row, "ViabilityPercentage")
        if pd.notna(viability_pct) and str(viability_pct).strip() not in {"", "NA", "nan"}:
            # Reuse viability_uri if exists, else create
            if f"viability_{iri_safe(sample_id)}" not in str(sample_uri):
                viability_uri = MCBO[f"viability_{iri_safe(sample_id)}"]
                g.add((viability_uri, RDF.type, MCBO.CellViabilityMeasurement))
                g.add((sample_uri, MCBO.hasCellViabilityMeasurement, viability_uri))
            pct_val, pct_dt = safe_numeric(viability_pct)
            if pct_val is not None:
                g.add((viability_uri, MCBO.hasViabilityPercentage, Literal(pct_val, datatype=pct_dt)))

        # 11) CloneID (CQ4, CQ8)
        clone_id = get_case_insensitive(row, "CloneID")
        clone_uri = None
        if pd.notna(clone_id) and str(clone_id).strip() not in {"", "NA", "nan"}:
            clone_str = str(clone_id).strip()
            clone_uri = MCBO[f"clone_{iri_safe(clone_str)}"]
            if clone_uri not in created_cell_lines:  # reuse created_cell_lines for clones
                g.add((clone_uri, RDF.type, MCBO.Clone))
                g.add((clone_uri, RDFS.label, Literal(clone_str)))
                if cell_line_uri is not None:
                    g.add((cell_line_uri, MCBO.hasClone, clone_uri))
                created_cell_lines.add(clone_uri)
            g.add((run_uri, MCBO.usesCellLine, clone_uri))

        # 12) GeneSymbol and ExpressionValue (CQ4, CQ6, CQ7)
        gene_symbol = get_case_insensitive(row, "GeneSymbol")
        expr_value = get_case_insensitive(row, "ExpressionValue")
        if pd.notna(gene_symbol) and str(gene_symbol).strip() not in {"", "NA", "nan"}:
            gene_str = str(gene_symbol).strip()
            # Handle multiple genes separated by ; or ,
            gene_list = [gs.strip() for gs in re.split(r'[;,]', gene_str) if gs.strip()]
            for gene_sym in gene_list:
                gene_uri = MCBO[f"gene_{iri_safe(gene_sym)}"]
                if gene_uri not in created_genes:
                    g.add((gene_uri, RDF.type, MCBO.Gene))
                    g.add((gene_uri, RDFS.label, Literal(gene_sym)))
                    created_genes.add(gene_uri)

                # Create gene expression measurement
                expr_uri = MCBO[f"expr_{iri_safe(sample_id)}_{iri_safe(gene_sym)}"]
                g.add((expr_uri, RDF.type, MCBO.GeneExpressionMeasurement))
                g.add((expr_uri, OBO.IAO_0000136, gene_uri))  # is about
                if pd.notna(expr_value) and str(expr_value).strip() not in {"", "NA", "nan"}:
                    ev_val, ev_dt = safe_numeric(expr_value)
                    if ev_val is not None:
                        g.add((expr_uri, MCBO.hasExpressionValue, Literal(ev_val, datatype=ev_dt)))
                g.add((sample_uri, MCBO.hasGeneExpression, expr_uri))

        # 13) TiterValue (CQ8)
        titer_value = get_case_insensitive(row, "TiterValue")
        if pd.notna(titer_value) and str(titer_value).strip() not in {"", "NA", "nan"}:
            product_uri = MCBO[f"product_{iri_safe(run_id)}"]
            g.add((product_uri, RDF.type, MCBO.TherapeuticProtein))
            titer_val, titer_dt = safe_numeric(titer_value)
            if titer_val is not None:
                g.add((product_uri, MCBO.hasTiterValue, Literal(titer_val, datatype=titer_dt)))
            g.add((run_uri, MCBO.hasProduct, product_uri))

            # Link product type if available
            if pd.notna(get_case_insensitive(row, "ProductType")):
                pt = str(get_case_insensitive(row, "ProductType")).strip()
                if pt and pt.lower() not in {"na", "nan", "control"}:
                    g.add((product_uri, RDFS.label, Literal(pt)))

        # 14) QualityType (CQ8)
        quality_type = get_case_insensitive(row, "QualityType")
        if pd.notna(quality_type) and str(quality_type).strip() not in {"", "NA", "nan"}:
            quality_str = str(quality_type).strip()
            quality_uri = MCBO[f"quality_{iri_safe(run_id)}_{iri_safe(quality_str)}"]
            g.add((quality_uri, RDF.type, MCBO.QualityMeasurement))
            g.add((quality_uri, RDFS.label, Literal(quality_str)))
            # Link to product if exists
            if pd.notna(titer_value):
                g.add((product_uri, MCBO.hasQualityMeasurement, quality_uri))
            else:
                # Create product just for quality
                product_uri = MCBO[f"product_{iri_safe(run_id)}"]
                g.add((product_uri, RDF.type, MCBO.TherapeuticProtein))
                g.add((product_uri, MCBO.hasQualityMeasurement, quality_uri))
                g.add((run_uri, MCBO.hasProduct, product_uri))

        # 15) Nutrient concentrations for CQ3 (glutamine - medium component)
        glut_conc = get_case_insensitive(row, "GlutamineConcentration")
        if pd.notna(glut_conc) and str(glut_conc).strip() not in {"", "NA", "nan"}:
            # Create nutrient concentration instance
            nutrient_uri = MCBO[f"glutamine_{iri_safe(run_id)}"]
            g.add((nutrient_uri, RDF.type, MCBO.GlutamineConcentration))
            g.add((nutrient_uri, RDF.type, MCBO.NutrientConcentration))  # Explicit for simple queries
            conc_val, conc_dt = safe_numeric(glut_conc)
            if conc_val is not None:
                g.add((nutrient_uri, MCBO.hasConcentrationValue, Literal(conc_val, datatype=conc_dt)))
                g.add((nutrient_uri, MCBO.hasConcentrationUnit, Literal("mM")))
            g.add((nutrient_uri, RDFS.label, Literal(f"Glutamine {glut_conc}mM")))

            # Link to medium if exists
            medium_val = row.get("CultureMedium") or row.get("Medium")
            if pd.notna(medium_val) and str(medium_val).strip() != "":
                medium_str = str(medium_val).strip()
                medium_uri = MCBO[f"medium_{iri_safe(medium_str)}"]
                g.add((medium_uri, MCBO.hasNutrientConcentration, nutrient_uri))
            else:
                # Create a generic medium
                medium_uri = MCBO[f"medium_{iri_safe(run_id)}"]
                if medium_uri not in created_media:
                    g.add((medium_uri, RDF.type, MCBO.CultureMedium))
                    g.add((medium_uri, RDFS.label, Literal("Culture Medium")))
                    created_media.add(medium_uri)
                g.add((medium_uri, MCBO.hasNutrientConcentration, nutrient_uri))
                g.add((system_uri, BFO_HAS_PART, medium_uri))

        # 16) CQ2 engineering: infer overexpressed gene from explicit overexpression columns or (Producer, ProductType)
        if cell_line_uri is not None:
            genes = extract_overexpressed_genes(row)

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


def load_expression_matrix(expr_file: str) -> dict:
    """Load expression matrix CSV and return dict: {sample_accession: {gene: value, ...}}
    
    Expected format:
        SampleAccession,GeneX,GeneY,GeneZ,...
        ERS4805133,150,200,50,...
        ERS4805134,180,220,45,...
    """
    df = pd.read_csv(expr_file)
    result = {}
    sample_col = None
    for col in ["SampleAccession", "Sample", "sample_id", "SampleID"]:
        if col in df.columns:
            sample_col = col
            break
    if sample_col is None:
        raise ValueError(f"Expression matrix must have a sample identifier column (SampleAccession, Sample, etc.)")
    
    gene_cols = [c for c in df.columns if c != sample_col]
    for _, row in df.iterrows():
        sample_id = str(row[sample_col]).strip()
        result[sample_id] = {}
        for gene in gene_cols:
            val = row[gene]
            if pd.notna(val):
                try:
                    result[sample_id][gene] = float(val)
                except (ValueError, TypeError):
                    pass
    return result


def add_expression_data(g: Graph, sample_uri, sample_id: str, expr_data: dict, created_genes: set):
    """Add gene expression measurements from expression matrix to the graph."""
    if sample_id not in expr_data:
        return
    
    for gene_sym, expr_val in expr_data[sample_id].items():
        gene_uri = MCBO[f"gene_{iri_safe(gene_sym)}"]
        if gene_uri not in created_genes:
            g.add((gene_uri, RDF.type, MCBO.Gene))
            g.add((gene_uri, RDFS.label, Literal(gene_sym)))
            created_genes.add(gene_uri)
        
        expr_uri = MCBO[f"expr_{iri_safe(sample_id)}_{iri_safe(gene_sym)}"]
        g.add((expr_uri, RDF.type, MCBO.GeneExpressionMeasurement))
        g.add((expr_uri, OBO.IAO_0000136, gene_uri))  # is about
        g.add((expr_uri, MCBO.hasExpressionValue, Literal(expr_val, datatype=XSD.decimal)))
        g.add((sample_uri, MCBO.hasGeneExpression, expr_uri))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert CSV metadata to RDF (MCBO instances)")
    parser.add_argument("--csv_file", type=str, default="data/sample_metadata.csv", help="Input CSV file")
    parser.add_argument("--output_file", type=str, default="data/processed/mcbo_instances.ttl", help="Output TTL file")
    parser.add_argument("--expression_matrix", type=str, default=None, 
                        help="Optional expression matrix CSV (genes as columns, samples as rows)")
    args = parser.parse_args()
    
    # Load expression matrix if provided
    expr_data = {}
    if args.expression_matrix:
        print(f"Loading expression matrix from: {args.expression_matrix}")
        expr_data = load_expression_matrix(args.expression_matrix)
        print(f"  Loaded expression data for {len(expr_data)} samples")
    
    g = convert_csv_to_rdf(args.csv_file, args.output_file)
    
    # If expression matrix provided, add expression data
    if expr_data:
        # Re-parse to add expression data (slightly inefficient but keeps convert_csv_to_rdf clean)
        df = pd.read_csv(args.csv_file)
        created_genes = set()
        for _, row in df.iterrows():
            sample_id = str(row.get("SampleAccession", "")).strip()
            if sample_id and sample_id in expr_data:
                sample_uri = MCBO[f"sample_{iri_safe(sample_id)}"]
                add_expression_data(g, sample_uri, sample_id, expr_data, created_genes)
        
        # Re-serialize with expression data
        g.serialize(destination=args.output_file, format="turtle")
        print(f"Added expression data for {len([s for s in expr_data if s in df['SampleAccession'].astype(str).values])} samples")
