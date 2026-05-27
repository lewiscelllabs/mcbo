"""Scan a directory for CSV/Parquet/JSON files and import them into DuckDB.

Public API:
    discover_files(data_dir)            -> list[Path]
    load_directory(db_path, data_dir)   -> list[dict]
    get_schema(db_path)                 -> dict
    get_slice_options(db_path, ...)     -> dict
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb


_SNAKE_RE = re.compile(r"[^a-zA-Z0-9]+")
_SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".parquet", ".json", ".ndjson"}


def _table_name_for(path: Path) -> str:
    """Convert a file path into a safe snake_case DuckDB table name."""
    snake = _SNAKE_RE.sub("_", path.stem).strip("_").lower()
    if not snake:
        snake = "table"
    if snake[0].isdigit():
        snake = "t_" + snake
    return snake


def discover_files(data_dir: Path) -> list[Path]:
    """Recursively find supported data files under ``data_dir``."""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return []
    return sorted(
        p for p in data_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
    )


def _import_one(con: duckdb.DuckDBPyConnection, path: Path) -> tuple[str, int]:
    table = _table_name_for(path)
    posix = str(path).replace("'", "''")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        sql = (
            f'CREATE OR REPLACE TABLE "{table}" AS '
            f"SELECT * FROM read_csv_auto('{posix}', SAMPLE_SIZE=-1)"
        )
    elif suffix == ".tsv":
        sql = (
            f'CREATE OR REPLACE TABLE "{table}" AS '
            f"SELECT * FROM read_csv_auto('{posix}', SAMPLE_SIZE=-1, delim='\t')"
        )
    elif suffix == ".parquet":
        sql = (
            f'CREATE OR REPLACE TABLE "{table}" AS '
            f"SELECT * FROM read_parquet('{posix}')"
        )
    elif suffix in (".json", ".ndjson"):
        sql = (
            f'CREATE OR REPLACE TABLE "{table}" AS '
            f"SELECT * FROM read_json_auto('{posix}')"
        )
    else:
        raise ValueError(f"Unsupported extension: {suffix}")

    con.execute(sql)
    nrows = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    return table, int(nrows)


# Known data-curation fixes applied at import time. Each tuple is
# (table, column, from_value, to_value). Idempotent: only updates rows
# whose current value matches ``from_value``; silently skipped if the
# table or column doesn't exist (so non-MCBO data isn't touched).
_KNOWN_TYPOS: list[tuple[str, str, str, str]] = [
    ("samples", "ProcessType", "Pefusion", "Perfusion"),
    # PolyA vs polyA inconsistency in LibraryStrategy: fold the lower-case
    # variant into the dominant spelling so SQL filters don't miss rows.
    ("samples", "LibraryStrategy", "polyA", "PolyA"),
]


def _normalize_known_typos(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Apply ``_KNOWN_TYPOS`` post-import. Returns one note per rewrite."""
    notes: list[str] = []
    try:
        existing = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()}
    except Exception:
        return notes
    for table, col, frm, to in _KNOWN_TYPOS:
        if table not in existing:
            continue
        try:
            cols = {r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()}
            if col not in cols:
                continue
            n = con.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" = ?', [frm]
            ).fetchone()[0]
            if n > 0:
                con.execute(
                    f'UPDATE "{table}" SET "{col}" = ? WHERE "{col}" = ?',
                    [to, frm],
                )
                notes.append(
                    f"Normalized {n} rows: {table}.{col} {frm!r} -> {to!r}"
                )
        except Exception as e:  # pragma: no cover - never break import on a typo fix
            notes.append(f"Skipped {table}.{col}: {e}")
    return notes


def load_directory(db_path: Path, data_dir: Path) -> dict:
    """Scan ``data_dir`` and import every supported file into ``db_path``.

    Always opens (and therefore creates) the DuckDB file, even when no files
    are discovered, so downstream read-only connections don't fail with
    "file does not exist".

    Returns ``{files: [...], normalizations: [...]}``: one ``files`` record
    per imported file (``{table, file, rows}`` on success or
    ``{table: None, file, error}`` on failure) plus any data-curation notes
    from ``_normalize_known_typos`` (empty list if nothing applied).
    """
    db_path = Path(db_path)
    data_dir = Path(data_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    files_out: list[dict] = []
    files = discover_files(data_dir)

    con = duckdb.connect(str(db_path))
    try:
        for f in files:
            try:
                table, nrows = _import_one(con, f)
                files_out.append({"table": table, "file": str(f), "rows": nrows})
            except Exception as e:  # pragma: no cover - surface importer errors to UI
                files_out.append({"table": None, "file": str(f), "error": str(e)})
        normalizations = _normalize_known_typos(con)
    finally:
        con.close()
    return {"files": files_out, "normalizations": normalizations}


def coverage_report(db_path: Path) -> dict:
    """Compute per-column non-null coverage for every table.

    Returns ``{table: {col: {non_null, total, pct}}}``. Useful for spotting
    silently-empty columns ("the column exists but is 100% NULL") before a
    demo or before a user blames the agent for a missing-data answer.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return {}
    con = duckdb.connect(str(db_path), read_only=True)
    out: dict[str, dict] = {}
    try:
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main' ORDER BY 1"
        ).fetchall()]
        for table in tables:
            try:
                total = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except Exception:
                continue
            cols_info = con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='main' AND table_name=? "
                "ORDER BY ordinal_position",
                [table],
            ).fetchall()
            cols: dict[str, dict] = {}
            for (cname,) in cols_info:
                try:
                    n = con.execute(
                        f'SELECT COUNT(*) FROM "{table}" WHERE "{cname}" IS NOT NULL'
                    ).fetchone()[0]
                except Exception:
                    continue
                cols[cname] = {
                    "non_null": int(n),
                    "total": int(total),
                    "pct": (n / total) if total else 0.0,
                }
            out[table] = cols
    finally:
        con.close()
    return out


def empty_columns(db_path: Path, min_table_rows: int = 1) -> list[tuple[str, str]]:
    """Convenience: list ``(table, column)`` pairs that are 100% NULL.

    Only considers tables with ``>= min_table_rows`` rows so a brand-new
    empty table doesn't fire false alarms.
    """
    report = coverage_report(db_path)
    out: list[tuple[str, str]] = []
    for table, cols in report.items():
        # Use first col's total as table row count (all cols share total).
        if not cols:
            continue
        total = next(iter(cols.values()))["total"]
        if total < min_table_rows:
            continue
        for cname, info in cols.items():
            if info["non_null"] == 0:
                out.append((table, cname))
    return out


def get_schema(db_path: Path) -> dict:
    """Return ``{tables: [{name, columns: [{name, type}], rows}]}``."""
    db_path = Path(db_path)
    if not db_path.exists():
        return {"tables": []}
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        names = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main' ORDER BY table_name"
        ).fetchall()]
        tables: list[dict] = []
        for t in names:
            cols = con.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema='main' AND table_name=? "
                "ORDER BY ordinal_position",
                [t],
            ).fetchall()
            try:
                nrows = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            except Exception:
                nrows = None
            tables.append({
                "name": t,
                "columns": [{"name": c, "type": ty} for c, ty in cols],
                "rows": nrows,
            })
        return {"tables": tables}
    finally:
        con.close()


_NUMERIC_TYPES = {
    "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
    "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
    "FLOAT", "DOUBLE", "REAL", "DECIMAL", "NUMERIC",
}
_STRING_TYPES = {"VARCHAR", "TEXT", "STRING", "CHAR"}


def _is_numeric(dtype: str) -> bool:
    base = dtype.upper().split("(")[0]
    return base in _NUMERIC_TYPES


def _is_string(dtype: str) -> bool:
    base = dtype.upper().split("(")[0]
    return base in _STRING_TYPES


def get_slice_options(
    db_path: Path,
    max_categories: int = 50,
) -> dict:
    """Per-table slice metadata for the Slice panel UI.

    For each table returns:
      - categorical: {col: [distinct values, ...]} for string columns with
        <= ``max_categories`` distinct non-null values
      - numeric:     {col: {min, max}} for numeric columns

    Skipped quietly if a column query fails (heterogeneous data).
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return {"tables": {}}
    schema = get_schema(db_path)
    out: dict[str, Any] = {"tables": {}}
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for t in schema["tables"]:
            name = t["name"]
            categorical: dict[str, list] = {}
            numeric: dict[str, dict] = {}
            for col in t["columns"]:
                cname = col["name"]
                ctype = col["type"]
                try:
                    if _is_string(ctype):
                        cnt = con.execute(
                            f'SELECT COUNT(DISTINCT "{cname}") FROM "{name}"'
                        ).fetchone()[0]
                        if cnt is not None and 0 < cnt <= max_categories:
                            vals = [
                                r[0] for r in con.execute(
                                    f'SELECT DISTINCT "{cname}" FROM "{name}" '
                                    f'WHERE "{cname}" IS NOT NULL '
                                    f'ORDER BY 1 LIMIT {max_categories}'
                                ).fetchall()
                            ]
                            categorical[cname] = vals
                    elif _is_numeric(ctype):
                        row = con.execute(
                            f'SELECT MIN("{cname}"), MAX("{cname}") FROM "{name}"'
                        ).fetchone()
                        if row and row[0] is not None and row[1] is not None:
                            numeric[cname] = {"min": row[0], "max": row[1]}
                except Exception:
                    continue
            out["tables"][name] = {"categorical": categorical, "numeric": numeric}
    finally:
        con.close()
    return out


__all__ = [
    "discover_files",
    "load_directory",
    "get_schema",
    "get_slice_options",
    "coverage_report",
    "empty_columns",
]
