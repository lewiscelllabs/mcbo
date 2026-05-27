"""
Parameterized DuckDB SQL templates for MCBO agent data fetching.

Parallel to ``sparql_templates.py`` - the SPARQL templates query the merged
RDF graph (``graph.ttl``); these query the DuckDB ingest produced by
``mcbo-build-duckdb`` from the same CSVs.

Each template is a SQL string with two named substitutions:

    {filter_clause}   -- inserted verbatim (already includes 'AND ...' or '')
    {limit_clause}    -- inserted verbatim (e.g. 'LIMIT 1000' or '')

Templates target tables/views created by ``mcbo.duckdb_io.build_duckdb``:
  - samples
  - expression_long(study_id, sample_id, gene_symbol, value)
  - samples_with_expression  (view; LEFT JOIN of samples + expression_long)

Column names follow the CSV headers, so they are case-sensitive and match
``sample_metadata.csv`` (RunAccession, SampleAccession, CellLine, ProcessType,
Temperature, pH, DissolvedOxygen, Productivity, CulturePhase,
ViabilityPercentage, ViableCellDensity, CollectionDay, CloneID, TiterValue,
QualityType, ProductType, Producer, GlutamineConcentration, ...).
"""

from __future__ import annotations

from typing import List


SQL_TEMPLATES = {
    # CQ1: Culture conditions and productivity data
    "culture_conditions_productivity": """
SELECT RunAccession        AS runId,
       CellLine            AS cellLine,
       Temperature         AS temperature,
       pH                  AS pH,
       DissolvedOxygen     AS dissolvedOxygen,
       Productivity        AS productivityCategory,
       ProcessType         AS processType,
       study_id
  FROM samples
 WHERE Productivity IS NOT NULL
   {filter_clause}
 ORDER BY CASE Productivity
            WHEN 'VeryHigh'  THEN 5
            WHEN 'High'      THEN 4
            WHEN 'Medium'    THEN 3
            WHEN 'LowMedium' THEN 2
            WHEN 'Low'       THEN 1
            ELSE 0 END DESC
 {limit_clause}
""",

    # CQ2: Cell lines engineered to produce/overexpress something
    "cell_lines_overexpression": """
SELECT DISTINCT
       CellLine            AS cellLine,
       Producer            AS producer,
       ProductType         AS productType,
       EnsemblGeneID       AS ensemblGeneID,
       study_id
  FROM samples
 WHERE Producer IS NOT NULL
   AND CellLine IS NOT NULL
   {filter_clause}
 ORDER BY cellLine, productType
 {limit_clause}
""",

    # CQ3: Nutrient (glutamine) concentration vs viable cell density at day
    "nutrient_viability_by_day": """
SELECT RunAccession          AS runId,
       SampleAccession       AS sampleId,
       CellLine              AS cellLine,
       GlutamineConcentration AS concentrationValue,
       'mM'                  AS concentrationUnit,
       ViableCellDensity     AS viableCellDensity,
       CollectionDay         AS collectionDay,
       study_id
  FROM samples
 WHERE GlutamineConcentration IS NOT NULL
   AND ViableCellDensity     IS NOT NULL
   {filter_clause}
 ORDER BY viableCellDensity DESC
 {limit_clause}
""",

    # CQ4: Gene expression by clone
    "gene_expression_by_clone": """
SELECT s.SampleAccession   AS sampleId,
       s.CellLine          AS cellLine,
       s.CloneID           AS clone,
       e.gene_symbol       AS gene,
       e.value             AS expressionValue,
       s.study_id
  FROM samples s
  JOIN expression_long e
    ON s.SampleAccession = e.sample_id
 WHERE s.CloneID IS NOT NULL
   {filter_clause}
 ORDER BY gene, clone
 {limit_clause}
""",

    # CQ5: Gene expression by process type (Fed-batch vs Perfusion etc.)
    "gene_expression_by_process_type": """
SELECT s.SampleAccession   AS sampleId,
       s.CellLine          AS cellLine,
       s.ProcessType       AS processType,
       e.gene_symbol       AS gene,
       e.value             AS expressionValue,
       s.study_id
  FROM samples s
  JOIN expression_long e
    ON s.SampleAccession = e.sample_id
 WHERE s.ProcessType IS NOT NULL
   {filter_clause}
 ORDER BY gene, processType
 {limit_clause}
""",

    # CQ6: Gene expression with productivity in stationary phase
    "gene_expression_stationary_productivity": """
SELECT s.SampleAccession   AS sampleId,
       s.CellLine          AS cellLine,
       s.ProcessType       AS processType,
       s.Productivity      AS productivityCategory,
       CASE s.Productivity
            WHEN 'VeryHigh'  THEN 5
            WHEN 'High'      THEN 4
            WHEN 'Medium'    THEN 3
            WHEN 'LowMedium' THEN 2
            WHEN 'Low'       THEN 1
            ELSE NULL END   AS productivityValue,
       e.gene_symbol       AS gene,
       e.value             AS expressionValue,
       s.study_id
  FROM samples s
  JOIN expression_long e
    ON s.SampleAccession = e.sample_id
 WHERE s.CulturePhase = 'Stationary'
   AND s.Productivity IS NOT NULL
   {filter_clause}
 ORDER BY productivityValue DESC, expressionValue DESC
 {limit_clause}
""",

    # CQ7: Gene expression with viability percentage
    "gene_expression_by_viability": """
SELECT s.SampleAccession      AS sampleId,
       s.CellLine             AS cellLine,
       s.ViabilityPercentage  AS viabilityPercentage,
       e.gene_symbol          AS gene,
       e.value                AS expressionValue,
       s.study_id
  FROM samples s
  JOIN expression_long e
    ON s.SampleAccession = e.sample_id
 WHERE s.ViabilityPercentage IS NOT NULL
   {filter_clause}
 ORDER BY viabilityPercentage DESC, gene
 {limit_clause}
""",

    # CQ8: Cell lines / clones with product quality + titer
    "cell_lines_product_quality": """
SELECT RunAccession   AS runId,
       CellLine       AS cellLine,
       CloneID        AS clone,
       ProductType    AS product,
       QualityType    AS qualityLabel,
       TiterValue     AS titerValue,
       ProcessType    AS processType,
       study_id
  FROM samples
 WHERE QualityType IS NOT NULL
   {filter_clause}
 ORDER BY titerValue DESC NULLS LAST
 {limit_clause}
""",

    # "Which cell lines produce a given product class?" — DuckDB mirror of
    # the SPARQL cell_lines_by_product_class template. Uses the same set of
    # keywords (mAb / IgG / BsAb / nanobody / Fc-fusion / antibody) the
    # csv_to_rdf classifier uses to populate the AntibodyProduct RDF class.
    # Pass product_class to switch keyword sets; default is "AntibodyProduct".
    "cell_lines_by_product_class": """
SELECT CellLine             AS cellLine,
       COUNT(DISTINCT ProductType) AS distinct_products,
       COUNT(*)             AS sample_count
  FROM samples
 WHERE ProductType IS NOT NULL
   AND (
     LOWER(ProductType) LIKE '%mab%'
     OR LOWER(ProductType) LIKE '%antibody%'
     OR ProductType LIKE '%IgG%'
     OR LOWER(ProductType) LIKE '%bsab%'
     OR LOWER(ProductType) LIKE '%bispecific%'
     OR LOWER(ProductType) LIKE '%nanobody%'
     OR LOWER(ProductType) LIKE '%fc-fusion%'
   )
   {filter_clause}
 GROUP BY CellLine
 ORDER BY sample_count DESC
 {limit_clause}
""",

    # Utility: all genes that have expression measurements
    "all_genes": """
SELECT DISTINCT gene_symbol AS gene
  FROM expression_long
 ORDER BY gene
 {limit_clause}
""",

    # Utility: all cell lines
    "all_cell_lines": """
SELECT DISTINCT CellLine AS cellLine, study_id
  FROM samples
 WHERE CellLine IS NOT NULL
 ORDER BY cellLine
 {limit_clause}
""",

    # Utility: per-process-type counts
    "process_type_summary": """
SELECT ProcessType AS processType, COUNT(*) AS count
  FROM samples
 WHERE ProcessType IS NOT NULL
 GROUP BY ProcessType
 ORDER BY count DESC
""",

    # Utility: schema introspection (handy for the agent)
    "list_tables": """
SELECT table_name
  FROM information_schema.tables
 WHERE table_schema = 'main'
 ORDER BY table_name
""",
    "describe_samples": """
SELECT column_name, data_type
  FROM information_schema.columns
 WHERE table_schema = 'main' AND table_name = 'samples'
 ORDER BY ordinal_position
""",
}


# Keep the CQ -> template mapping aligned with the SPARQL side so agents can
# pick either backend by the same key.
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


def get_template(template_name: str) -> str:
    if template_name not in SQL_TEMPLATES:
        available = ", ".join(sorted(SQL_TEMPLATES.keys()))
        raise KeyError(f"Unknown SQL template '{template_name}'. Available: {available}")
    return SQL_TEMPLATES[template_name]


def format_template(
    template_name: str,
    filter_clause: str = "",
    limit: int | None = None,
) -> str:
    """Format a SQL template.

    ``filter_clause`` is appended to the WHERE block. The caller should give
    a bare predicate (no leading ``AND``); we prepend ``AND`` automatically
    when non-empty. ``limit`` becomes ``LIMIT N`` or empty.
    """
    template = get_template(template_name)

    filt = filter_clause.strip()
    if filt:
        upper = filt.upper()
        if not (upper.startswith("AND ") or upper.startswith("OR ")):
            filt = "AND " + filt
    limit_clause = f"LIMIT {int(limit)}" if limit else ""

    return template.format(filter_clause=filt, limit_clause=limit_clause)


def list_templates() -> List[str]:
    return sorted(SQL_TEMPLATES.keys())


__all__ = [
    "SQL_TEMPLATES",
    "CQ_TEMPLATE_MAPPING",
    "get_template",
    "format_template",
    "list_templates",
]
