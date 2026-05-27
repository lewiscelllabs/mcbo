# Demo-card prompt backups

Working backups of demo-card `q` strings (in `templates/index.html` →
`demoCards` array) so we can roll back if a "natural-language" rewrite
turns out to be less reliable than the prescriptive original.

To restore a backup, copy the JS-escaped string back into the
corresponding card's `q:` value in `templates/index.html`.

---

## Orchestrator system-prompt block — "DEFAULT RECIPE FOR EXPRESSION-MATRIX PLOTS" (2026-05-27, full 70-line version)

Restore into `python/mcbo/agent/orchestrator.py` between the `PLOTTING (optional):`
block and `CROSS-TURN MEMORY VIA save_df:` if the lean version regresses on
PCA / UMAP / t-SNE / heatmap workflows. Requires a server restart.

```
DEFAULT RECIPE FOR EXPRESSION-MATRIX PLOTS (PCA / UMAP / t-SNE / heatmap):
When the user asks for a PCA / UMAP / t-SNE / heatmap / clustering of
expression data, apply this recipe AUTOMATICALLY -- the user is unlikely
to know the data shape and you will fail without it.

CRITICAL DATA-SHAPE FACTS (skipping any of these reliably breaks the pivot):
- `expression_long(sample_id, gene_symbol, value)` is the ONLY clean
  source. It has ONE row per (sample_id, gene_symbol). Zero duplicates.
- `samples_with_expression` is a JOIN view with `(sample_id, gene_symbol)`
  DUPLICATES because `samples` has multiple `RunAccession` rows per
  `SampleAccession` (some samples have up to 7 runs). NEVER use it for
  matrix-shaped operations.
- `samples` itself ALSO has multiple rows per `SampleAccession` for the
  same reason. If you `JOIN expression_long e ON e.sample_id =
  s.SampleAccession` against the raw `samples` table, you re-create
  exactly the duplicate-pivot bug that `samples_with_expression` has --
  each expression row gets multiplied by the number of runs.
- Therefore: ANY join from `expression_long` to per-sample metadata
  (CellLine, ProcessType, StudyID, ...) MUST go through a DEDUPLICATED
  subquery, NOT the raw `samples` table.

CANONICAL SQL PATTERN for "get expression of top-N variable genes for
samples matching <filter>":

   WITH cho_samples AS (
       -- DISTINCT is load-bearing: collapses multi-run dupes.
       SELECT DISTINCT SampleAccession, CellLine
       FROM samples
       WHERE CellLine LIKE 'CHO%'
   ),
   top_genes AS (
       SELECT gene_symbol
       FROM (
           SELECT gene_symbol, VAR_POP(value) AS v
           FROM expression_long e
           JOIN cho_samples c ON e.sample_id = c.SampleAccession
           GROUP BY gene_symbol
           ORDER BY v DESC
           LIMIT 200
       ) t
   )
   SELECT e.sample_id, e.gene_symbol, e.value
   FROM expression_long e
   JOIN cho_samples c   ON e.sample_id  = c.SampleAccession
   JOIN top_genes  t    ON e.gene_symbol = t.gene_symbol;

After fetching, pivot is duplicate-free because every join is against a
DISTINCT-keyed CTE. If you ever see "duplicate (sample_id, gene_symbol)"
when pivoting, you forgot the DISTINCT and joined against raw `samples`.

PIPELINE STEPS:
1. Sample scope: write a DISTINCT-keyed CTE on `samples` (see pattern above).
2. Gene scope: top-N most-variable genes (default N=200) computed OVER
   the sample-scope CTE -- never the global ranking.
3. Fetch expression for those (sample, gene) pairs via the canonical
   pattern above.
4. Pivot in pandas: `pivot_table(index='sample_id', columns='gene_symbol',
   values='value', aggfunc='mean').fillna(0)` -- aggfunc='mean' is a belt
   on top of suspenders, .fillna(0) handles sparse genes.
5. Standardize: z-score each column (subtract mean, divide by std with
   zero-std columns set to 1) before PCA / clustering. Raw expression
   spans ~5 orders of magnitude per sample; without z-score, one high-
   magnitude gene dominates PC1 and the plot looks like noise.
6. Compute PCA / clustering / etc.
7. Save the intermediate result with `save_df('snake_case_name', df)`
   so follow-up questions can query it.
8. Color/legend: look up the grouping variable from the same DISTINCT
   CTE you built in step 1 (NOT from a fresh JOIN against raw `samples`).

Even when the user's request is one short sentence (e.g. "make a PCA
of CHO cell line samples colored by cell line"), follow this recipe.
Do not ask for clarification on the recipe.
```

---

## Card 3 — Plot (PCA) — TECHNICAL VERSION (2026-05-27, proven to work)

This is the prescriptive recipe that successfully produced a clean
PCA on the real `.data/mcbo.duckdb` (CHO-K1=154, CHO-S=84,
CHO-DXB11=83 samples, 200 top-variance genes, z-scored). Restore if
the natural-language version regresses.

```js
q: "Make a PCA scatter of all CHO cell line samples, colored by cell line. "
 + "Important specifics so it works on the first try: "
 + "(1) Use expression_long DIRECTLY (NOT samples_with_expression -- its join fans out across multiple RunAccessions per SampleAccession, creating (sample_id, gene_symbol) duplicates that break the pivot). "
 + "(2) Use the top 200 most-variable genes only, computed over CHO samples only "
 + "(join through (SELECT DISTINCT SampleAccession FROM samples WHERE CellLine LIKE 'CHO%')). "
 + "(3) Pivot with aggfunc='mean' and .fillna(0). "
 + "(4) Standardize each gene column (z-score) before PCA so a single high-magnitude gene doesn't dominate PC1. "
 + "(5) Color the three CHO subtypes (CHO-K1, CHO-S, CHO-DXB11) with distinct colors and add a legend. "
 + "Title: \"PCA of CHO cell lines (top 200 variable genes, z-scored)\".",
```
