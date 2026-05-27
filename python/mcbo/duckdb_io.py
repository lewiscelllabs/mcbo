#!/usr/bin/env python3
"""
duckdb_io.py - Ingest MCBO CSV data into a local DuckDB database.

This is the SQL-side parallel to ``csv_to_rdf.py`` / ``build_graph.py``.
The SPARQL pipeline still owns the OWL-aware path (TBox + ABox in
``graph.ttl``); this module gives agents a fast, schema-on-read SQL view
of the *same* CSV inputs that drive the CQs.

Config-by-convention (matches ``build_graph.py`` / ``run_eval.py``):

    <data-dir>/
      sample_metadata.csv          # root metadata (foundation)
      studies/<study>/sample_metadata.csv
      studies/<study>/expression_matrix.csv
      expression/<file>.csv        # optional per-study expression matrices
      gene_annotations.csv         # optional gene symbol -> Ensembl
      mcbo.duckdb                  # OUTPUT: this module writes here

The DuckDB file is local only - no S3 / httpfs is used.

Resulting schema:

    samples(study_id TEXT, <all CSV columns from sample_metadata>)
    expression_long(study_id TEXT, sample_id TEXT, gene_symbol TEXT, value DOUBLE)
    gene_annotations(<all CSV columns from gene_annotations.csv>)    -- optional

    -- View, only created when SampleAccession column exists:
    samples_with_expression  AS samples LEFT JOIN expression_long
                                ON samples.SampleAccession = expression_long.sample_id

Usage (after ``pip install -e 'python/[duckdb]'``)::

    mcbo-build-duckdb --data-dir data.sample
    mcbo-build-duckdb --data-dir data.sample --duckdb /tmp/mcbo.duckdb
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd


# Mirror the convention used in build_graph.py / run_eval.py / csv_to_rdf.py.
# Keep keys identical where they overlap so future refactors can share.
DEFAULT_PATHS = {
    "duckdb": "mcbo.duckdb",
    "metadata": "sample_metadata.csv",
    "studies": "studies",
    "expression": "expression",
    "gene_annotations": "gene_annotations.csv",
}


def resolve_data_dir_path(data_dir: Path, key: str) -> Path:
    """Resolve a path relative to ``data_dir`` using the conventional defaults."""
    return Path(data_dir) / DEFAULT_PATHS[key]


_SAMPLE_ID_CANDIDATES = ("SampleAccession", "Sample", "SampleID", "sample_id")
_STUDY_METADATA_NAMES = ("sample_metadata.csv", "metadata.csv", "samples.csv")
_STUDY_EXPRESSION_NAMES = (
    "expression_matrix.csv",
    "expression.csv",
    "counts.csv",
    "tpm.csv",
)


def _find_study_files(study_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """Locate ``(metadata_csv, expression_csv)`` inside a study directory."""
    meta = next(
        (study_dir / n for n in _STUDY_METADATA_NAMES if (study_dir / n).exists()),
        None,
    )
    expr = next(
        (study_dir / n for n in _STUDY_EXPRESSION_NAMES if (study_dir / n).exists()),
        None,
    )
    return meta, expr


def _read_metadata(csv_path: Path, study_id: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Prepend study_id so concat across heterogeneous studies stays sane.
    if "study_id" in df.columns:
        df = df.drop(columns=["study_id"])
    df.insert(0, "study_id", study_id)
    return df


def _melt_expression(expr_path: Path, study_id: str) -> pd.DataFrame:
    df = pd.read_csv(expr_path)
    sample_col = next((c for c in _SAMPLE_ID_CANDIDATES if c in df.columns), None)
    if sample_col is None:
        return pd.DataFrame(
            columns=["study_id", "sample_id", "gene_symbol", "value"]
        )
    gene_cols = [c for c in df.columns if c != sample_col]
    if not gene_cols:
        return pd.DataFrame(
            columns=["study_id", "sample_id", "gene_symbol", "value"]
        )
    long = df.melt(
        id_vars=[sample_col],
        value_vars=gene_cols,
        var_name="gene_symbol",
        value_name="value",
    ).rename(columns={sample_col: "sample_id"})
    long.insert(0, "study_id", study_id)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    return long.dropna(subset=["value"]).reset_index(drop=True)


def _collect_metadata(data_dir: Path) -> pd.DataFrame:
    frames = []

    root_meta = resolve_data_dir_path(data_dir, "metadata")
    if root_meta.exists():
        frames.append(_read_metadata(root_meta, study_id="root"))

    studies_dir = resolve_data_dir_path(data_dir, "studies")
    if studies_dir.exists():
        for study_dir in sorted(p for p in studies_dir.iterdir() if p.is_dir()):
            meta, _ = _find_study_files(study_dir)
            if meta is not None:
                frames.append(_read_metadata(meta, study_id=study_dir.name))

    if not frames:
        raise FileNotFoundError(
            f"No sample_metadata.csv found at {root_meta} or under "
            f"{resolve_data_dir_path(data_dir, 'studies')}"
        )

    return pd.concat(frames, ignore_index=True, sort=False)


def _collect_expression(data_dir: Path) -> pd.DataFrame:
    frames = []

    expr_dir = resolve_data_dir_path(data_dir, "expression")
    if expr_dir.exists():
        for f in sorted(expr_dir.glob("*.csv")):
            frames.append(_melt_expression(f, study_id=f.stem))

    studies_dir = resolve_data_dir_path(data_dir, "studies")
    if studies_dir.exists():
        for study_dir in sorted(p for p in studies_dir.iterdir() if p.is_dir()):
            _, expr = _find_study_files(study_dir)
            if expr is not None:
                frames.append(_melt_expression(expr, study_id=study_dir.name))

    if not frames:
        return pd.DataFrame(
            columns=["study_id", "sample_id", "gene_symbol", "value"]
        )
    return pd.concat(frames, ignore_index=True, sort=False)


def _collect_annotations(data_dir: Path) -> pd.DataFrame:
    annot_path = resolve_data_dir_path(data_dir, "gene_annotations")
    if annot_path.exists():
        return pd.read_csv(annot_path)
    return pd.DataFrame()


def build_duckdb(
    data_dir: Path,
    db_path: Optional[Path] = None,
    overwrite: bool = True,
) -> Path:
    """Ingest a ``<data-dir>`` into a local DuckDB file.

    Returns the path to the written database.
    """
    try:
        import duckdb
    except ImportError as e:  # pragma: no cover - import-time guidance
        raise ImportError(
            "duckdb is required. Install with: pip install -e 'python/[duckdb]'"
        ) from e

    data_dir = Path(data_dir)
    db_path = Path(db_path) if db_path else resolve_data_dir_path(data_dir, "duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if overwrite and db_path.exists():
        db_path.unlink()

    print(f"Building DuckDB at: {db_path}")
    samples = _collect_metadata(data_dir)
    print(f"  samples: {len(samples):,} rows, {len(samples.columns)} columns")

    expression = _collect_expression(data_dir)
    print(
        f"  expression_long: {len(expression):,} rows "
        f"({expression['sample_id'].nunique() if len(expression) else 0} samples, "
        f"{expression['gene_symbol'].nunique() if len(expression) else 0} genes)"
    )

    annotations = _collect_annotations(data_dir)
    if not annotations.empty:
        print(f"  gene_annotations: {len(annotations):,} rows")

    con = duckdb.connect(str(db_path))
    try:
        con.register("df_samples", samples)
        con.execute("CREATE OR REPLACE TABLE samples AS SELECT * FROM df_samples")
        con.unregister("df_samples")

        con.register("df_expression", expression)
        con.execute(
            "CREATE OR REPLACE TABLE expression_long AS SELECT * FROM df_expression"
        )
        con.unregister("df_expression")

        if not annotations.empty:
            con.register("df_annot", annotations)
            con.execute(
                "CREATE OR REPLACE TABLE gene_annotations AS SELECT * FROM df_annot"
            )
            con.unregister("df_annot")

        # Convenience view only when the canonical sample identifier exists
        if "SampleAccession" in samples.columns:
            con.execute(
                """
                CREATE OR REPLACE VIEW samples_with_expression AS
                SELECT s.*, e.gene_symbol, e.value AS expression_value
                  FROM samples s
                  LEFT JOIN expression_long e
                    ON s.SampleAccession = e.sample_id
                """
            )
    finally:
        con.close()

    print(f"Done. Open with: duckdb {db_path}")
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest MCBO CSV data into a local DuckDB database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Config-by-convention: writes <data-dir>/mcbo.duckdb
  mcbo-build-duckdb --data-dir data.sample
  mcbo-build-duckdb --data-dir .data

  # Explicit output location
  mcbo-build-duckdb --data-dir data.sample --duckdb /tmp/mcbo.duckdb

Tables created:
  samples                  -- one row per metadata CSV row (study_id added)
  expression_long          -- melted (study_id, sample_id, gene_symbol, value)
  gene_annotations         -- (only if gene_annotations.csv present)
  samples_with_expression  -- view; only if SampleAccession column exists
""",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Data directory (uses config-by-convention; same as mcbo-build-graph).",
    )
    parser.add_argument(
        "--duckdb",
        type=Path,
        default=None,
        help="Output DuckDB path (default: <data-dir>/mcbo.duckdb).",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Do not delete an existing DuckDB file before writing.",
    )
    args = parser.parse_args()
    build_duckdb(args.data_dir, db_path=args.duckdb, overwrite=not args.no_overwrite)


__all__ = [
    "DEFAULT_PATHS",
    "resolve_data_dir_path",
    "build_duckdb",
    "main",
]


if __name__ == "__main__":
    main()
