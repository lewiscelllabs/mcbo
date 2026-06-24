"""Alchemist chat engine.

A bounded OpenAI tool-calling loop over a local DuckDB database with two
tools: ``query_data`` (read-only SQL) and ``generate_plot``
(matplotlib/seaborn in a sandboxed namespace).

Public API:
    ask(db_path, question, *, history=None, slice_context="") -> dict
    invalidate_schema_cache(db_path=None)
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any

import duckdb

try:  # pragma: no cover - import-time
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Schema introspection (60s cache)
# ---------------------------------------------------------------------------

_SCHEMA_CACHE: dict[str, tuple[float, str]] = {}
_SCHEMA_LOCK = Lock()
_SCHEMA_TTL = 60.0


def _build_schema_text(db_path: str) -> str:
    p = Path(db_path)
    if not p.exists():
        db_section = "(no database found at " + db_path + ")"
    else:
        con = duckdb.connect(db_path, read_only=True)
        try:
            names = [r[0] for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='main' ORDER BY table_name"
            ).fetchall()]
            if not names:
                db_section = "(database has no tables; drop files into the data dir and reload)"
            else:
                lines: list[str] = []
                for t in names:
                    try:
                        nrows = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                    except Exception:
                        nrows = "?"
                    cols = con.execute(
                        "SELECT column_name, data_type FROM information_schema.columns "
                        "WHERE table_schema='main' AND table_name=? "
                        "ORDER BY ordinal_position",
                        [t],
                    ).fetchall()
                    col_str = ", ".join(f"{c} {ty}" for c, ty in cols[:25])
                    if len(cols) > 25:
                        col_str += f" ... (+{len(cols) - 25} more cols)"
                    lines.append(f'- "{t}" ({nrows} rows): {col_str}')
                    try:
                        sample = con.execute(f'SELECT * FROM "{t}" LIMIT 2').fetchall()
                        if sample:
                            sample_str = "; ".join(str(r) for r in sample)
                            if len(sample_str) > 240:
                                sample_str = sample_str[:240] + "..."
                            lines.append(f"    sample: {sample_str}")
                    except Exception:
                        pass
                db_section = "\n".join(lines)
        finally:
            con.close()

    raw_section = _build_raw_files_text()
    if raw_section:
        return db_section + "\n\n" + raw_section
    return db_section


def _build_raw_files_text(max_files: int = 40) -> str:
    """Inventory of raw files in ALCHEMIST_DATA_DIR for the model's context.

    Includes BOTH tabular files (which the model can also reach via
    query_data, and should prefer for) and non-tabular files (which are
    only reachable via the list_files / read_file tools).
    """
    base = _data_dir()
    if not base.exists():
        return ""
    entries: list[tuple[str, int, str]] = []
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        rel = p.relative_to(base).as_posix()
        ext = p.suffix.lower()
        if ext in _XLSX_EXTS:
            kind = "xlsx (use read_file; pass sheet=<name> to drill in)"
        elif ext in _TABULAR_EXTS:
            kind = "tabular (use query_data)"
        elif ext in _PDF_EXTS:
            kind = "pdf (use read_file; text is extracted)"
        else:
            kind = "raw text (use read_file)"
        entries.append((rel, size, kind))
        if len(entries) >= max_files + 1:
            break
    if not entries:
        return ""
    lines = [f"RAW FILES under {base} (use list_files / read_file):"]
    for rel, size, kind in entries[:max_files]:
        lines.append(f"  - {rel}  [{kind}, {size} bytes]")
    if len(entries) > max_files:
        lines.append(f"  ... (+{len(entries) - max_files} more; call list_files to enumerate)")
    return "\n".join(lines)


def get_schema_text(db_path: str) -> str:
    with _SCHEMA_LOCK:
        cached = _SCHEMA_CACHE.get(db_path)
        if cached and (time.time() - cached[0]) < _SCHEMA_TTL:
            return cached[1]
        text = _build_schema_text(db_path)
        _SCHEMA_CACHE[db_path] = (time.time(), text)
        return text


def invalidate_schema_cache(db_path: str | None = None) -> None:
    with _SCHEMA_LOCK:
        if db_path is None:
            _SCHEMA_CACHE.clear()
        else:
            _SCHEMA_CACHE.pop(db_path, None)


# ---------------------------------------------------------------------------
# SQL safety: only SELECT / WITH, no DDL or mutations.
# ---------------------------------------------------------------------------

_FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "ATTACH", "DETACH", "COPY", "EXPORT", "IMPORT", "PRAGMA", "VACUUM",
    "REPLACE", "GRANT", "REVOKE", "CALL",
}
_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def _strip_strings_and_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"'(?:''|[^'])*'", "''", sql)
    sql = re.sub(r'"(?:[^"])*"', '""', sql)
    return sql


def is_safe_select(sql: str) -> tuple[bool, str]:
    cleaned = _strip_strings_and_comments(sql)
    tokens = {t.upper() for t in _IDENT_RE.findall(cleaned)}
    forbidden = tokens & _FORBIDDEN_KEYWORDS
    if forbidden:
        return False, f"Forbidden SQL keyword(s): {', '.join(sorted(forbidden))}"
    head = cleaned.lstrip().upper()
    if not (head.startswith("SELECT") or head.startswith("WITH")):
        return False, "Only SELECT or WITH ... SELECT queries are allowed."
    if ";" in cleaned.rstrip().rstrip(";"):
        return False, "Multiple statements are not allowed."
    return True, ""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

_MAX_ROWS = 100

# Raw file access (list_files / read_file). DATA_DIR is resolved lazily from
# ALCHEMIST_DATA_DIR so the engine doesn't need it as a constructor arg.
_RAW_FILE_MAX_BYTES = 256 * 1024  # 256 KB per read; OpenAI tool-result cap is ~8KB anyway
_RAW_FILE_LIST_LIMIT = 200
# Files with these extensions are auto-imported into DuckDB by data_loader,
# so the model should prefer query_data for them.
_TABULAR_EXTS = {".csv", ".tsv", ".parquet", ".json", ".ndjson"}

# Extensions handled by content-aware paths inside _tool_read_file (binary
# files that get extracted to a structured/text representation in-memory,
# without touching DuckDB).
_PDF_EXTS = {".pdf"}
_XLSX_EXTS = {".xlsx", ".xls"}

# Default and maximum row counts for the xlsx preview branch of read_file.
# Multi-sheet summary mode uses _XLSX_DEFAULT_PREVIEW per sheet; single-sheet
# mode (when `sheet` arg is passed) defaults to _XLSX_SHEET_DEFAULT_ROWS.
# The hard cap protects the 8KB tool-result truncation in ask().
_XLSX_DEFAULT_PREVIEW = 5
_XLSX_SHEET_DEFAULT_ROWS = 50
_XLSX_MAX_ROWS = 200


def _data_dir() -> Path:
    """Resolve the raw-file directory (must match app.DATA_DIR's default)."""
    default = Path(__file__).resolve().parent / "data"
    return Path(os.getenv("ALCHEMIST_DATA_DIR", str(default))).resolve()


def _resolve_under_data_dir(rel_path: str) -> tuple[Path | None, str]:
    """Resolve ``rel_path`` against DATA_DIR; refuse absolute paths and `..` escapes."""
    base = _data_dir()
    s = (rel_path or "").strip()
    if not s or s in ("/", "."):
        return None, "path must be a non-empty file path relative to the data directory"
    candidate = (base / s).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None, f"path escapes the data directory ({base})"
    return candidate, ""


def _tool_query_data(db_path: str, args: dict) -> dict:
    sql = (args.get("sql") or "").strip().rstrip(";")
    if not sql:
        return {"error": "Missing required argument: sql"}
    ok, why = is_safe_select(sql)
    if not ok:
        return {"error": why}
    if not Path(db_path).exists():
        return {"error": (
            f"DuckDB file not found at {db_path}. "
            "Either drop data files into ALCHEMIST_DATA_DIR and POST /api/data/reload, "
            "or set ALCHEMIST_DB_PATH to an existing DuckDB file."
        )}
    try:
        con = duckdb.connect(db_path, read_only=True)
    except Exception as e:
        return {"error": f"Could not open DuckDB at {db_path}: {e}"}
    try:
        df = con.execute(sql).fetchdf()
    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()
    n_all = int(len(df))
    df = df.head(_MAX_ROWS)

    def _cell(v):
        if v is None:
            return None
        try:
            import math
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        # numpy scalars expose .item(); pandas Timestamp / Decimal / datetime fall back to str
        if hasattr(v, "item"):
            try:
                return v.item()
            except Exception:
                pass
        if isinstance(v, (str, int, float, bool)):
            return v
        return str(v)

    safe = df.astype(object).where(df.notna(), None)
    rows = [[_cell(v) for v in row] for row in safe.values.tolist()]
    return {
        "columns": [str(c) for c in df.columns],
        "rows": rows,
        "n_rows": n_all,
        "truncated": n_all > _MAX_ROWS,
    }


def _tool_generate_plot(db_path: str, args: dict) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np
    import pandas as pd
    import sklearn  # noqa: F401  (exposed to user code)

    code = args.get("code") or ""
    title = args.get("title") or ""
    if not code.strip():
        return {"error": "Missing required argument: code"}

    plt.close("all")
    con = duckdb.connect(db_path, read_only=True)

    def run_sql(sql: str):
        ok, why = is_safe_select(sql)
        if not ok:
            raise ValueError(why)
        return con.execute(sql).fetchdf()

    buf = io.BytesIO()
    ns: dict[str, Any] = {
        "run_sql": run_sql,
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "sklearn": sklearn,
        "buf": buf,
        "title": title,
        "__builtins__": __builtins__,
    }
    try:
        plt.figure(figsize=(7, 6))
        exec(code, ns)  # noqa: S102 - sandboxed namespace; SQL helper is restricted
        if buf.tell() == 0:
            # Fallback: user forgot to savefig; save the current figure.
            plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        plt.close("all")
        con.close()

    data = buf.getvalue()
    if not data:
        return {"error": "Plot code did not produce a PNG image."}
    return {
        "image_base64": base64.b64encode(data).decode("ascii"),
        "title": title,
    }


def _tool_list_files(_db_path: str, args: dict) -> dict:
    """Enumerate files under DATA_DIR. Optional subpath + glob pattern."""
    subpath = (args.get("subpath") or "").strip().lstrip("/")
    pattern = (args.get("pattern") or "*").strip() or "*"
    try:
        max_results = int(args.get("max_results") or _RAW_FILE_LIST_LIMIT)
    except (TypeError, ValueError):
        max_results = _RAW_FILE_LIST_LIMIT
    max_results = max(1, min(max_results, _RAW_FILE_LIST_LIMIT))

    base = _data_dir()
    if not base.exists():
        return {
            "data_dir": str(base),
            "files": [],
            "note": f"data directory does not exist yet: {base}",
        }

    if subpath:
        root, err = _resolve_under_data_dir(subpath)
        if err:
            return {"error": err}
        if root is None or not root.exists() or not root.is_dir():
            return {"error": f"not a directory: {subpath}"}
    else:
        root = base

    files: list[dict] = []
    for p in sorted(root.rglob(pattern)):
        if not p.is_file():
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        rel = p.relative_to(base).as_posix()
        ext = p.suffix.lower()
        if ext in (".xlsx", ".xls"):
            kind = "xlsx"
        elif ext in _TABULAR_EXTS:
            kind = "tabular"
        elif ext in _PDF_EXTS:
            kind = "pdf"
        else:
            kind = "raw"
        files.append({
            "path": rel,
            "size_bytes": int(st.st_size),
            "ext": ext,
            "kind": kind,
        })
        if len(files) >= max_results:
            break
    return {
        "data_dir": str(base),
        "subpath": subpath or ".",
        "pattern": pattern,
        "files": files,
        "truncated": len(files) >= max_results,
    }


def _json_safe_cell(v: Any) -> Any:
    """Coerce a pandas/numpy cell into a JSON-serializable scalar."""
    if v is None:
        return None
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:  # pragma: no cover
        pass
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    if isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def _df_preview_rows(df) -> list[list[Any]]:
    """Convert the head of a DataFrame to JSON-safe row lists."""
    safe = df.astype(object).where(df.notna(), None)
    return [[_json_safe_cell(v) for v in row] for row in safe.values.tolist()]


def _read_xlsx(path: Path, sheet: str | None, max_rows: int | None) -> dict:
    """Open an xlsx/xls workbook and return sheet metadata + a row preview.

    Two modes:
      - sheet=None (summary): every sheet, with columns + ``_XLSX_DEFAULT_PREVIEW``
        preview rows each. Use to discover the workbook layout.
      - sheet=<name>: that one sheet only, with up to ``max_rows`` preview rows
        (default ``_XLSX_SHEET_DEFAULT_ROWS``, hard-capped at ``_XLSX_MAX_ROWS``).
    """
    try:
        import pandas as pd  # local import keeps engine import fast when unused
    except ImportError as e:
        raise RuntimeError(
            "xlsx support requires pandas + openpyxl. "
            "Install with: pip install pandas openpyxl"
        ) from e
    engine = "openpyxl" if path.suffix.lower() == ".xlsx" else None  # xlrd for .xls

    if sheet is not None:
        cap = max(1, min(max_rows or _XLSX_SHEET_DEFAULT_ROWS, _XLSX_MAX_ROWS))
        try:
            df = pd.read_excel(path, sheet_name=sheet, engine=engine)
        except ValueError:
            # Surface available sheet names so the model can retry.
            try:
                all_sheets = pd.read_excel(path, sheet_name=None, engine=engine)
                names = list(all_sheets.keys())
            except Exception:
                names = []
            return {
                "error": f"sheet '{sheet}' not found in {path.name}",
                "available_sheets": names,
            }
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        total = int(len(df))
        preview = df.head(cap)
        return {
            "sheet": sheet,
            "columns": [str(c) for c in df.columns],
            "total_rows": total,
            "preview_rows": _df_preview_rows(preview),
            "truncated": total > cap,
        }

    cap = max(1, min(max_rows or _XLSX_DEFAULT_PREVIEW, _XLSX_MAX_ROWS))
    all_sheets = pd.read_excel(path, sheet_name=None, engine=engine)
    sheets_out: list[dict] = []
    for name, df in all_sheets.items():
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        total = int(len(df))
        sheets_out.append({
            "name": str(name),
            "columns": [str(c) for c in df.columns],
            "total_rows": total,
            "preview_rows": _df_preview_rows(df.head(cap)),
            "truncated": total > cap,
        })
    return {
        "sheet_count": len(sheets_out),
        "sheets": sheets_out,
        "hint": (
            "Call read_file again with sheet=<name> and max_rows to fetch "
            "more rows from a specific sheet."
        ),
    }


def _read_pdf_text(path: Path, max_chars: int) -> tuple[str, int, bool]:
    """Extract text from a PDF; return (text, page_count, truncated)."""
    try:
        from pypdf import PdfReader  # local import: optional dep
    except ImportError as e:
        raise RuntimeError(
            "PDF support requires the 'pypdf' package. "
            "Install with: pip install pypdf"
        ) from e
    reader = PdfReader(str(path))
    pages = len(reader.pages)
    chunks: list[str] = []
    total = 0
    truncated = False
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception as e:  # pragma: no cover - malformed PDFs
            t = f"[page {i+1}: extraction failed: {e}]"
        header = f"\n--- page {i+1}/{pages} ---\n"
        if total + len(header) + len(t) > max_chars:
            remaining = max_chars - total - len(header)
            if remaining > 0:
                chunks.append(header)
                chunks.append(t[:remaining])
            truncated = True
            break
        chunks.append(header)
        chunks.append(t)
        total += len(header) + len(t)
    return ("".join(chunks).strip(), pages, truncated)


def _tool_read_file(_db_path: str, args: dict) -> dict:
    """Read a file under DATA_DIR. Type-aware:
      - .pdf  -> text extracted via pypdf (page-delimited).
      - .xlsx / .xls -> sheets + columns + a row preview via pandas/openpyxl.
        Optional args ``sheet`` and ``max_rows`` let the model drill into
        a single sheet for more rows.
      - everything else -> raw bytes decoded as utf-8 / latin-1; binaries refused.
    """
    rel = (args.get("path") or "").strip()
    if not rel:
        return {"error": "Missing required argument: path"}
    try:
        max_bytes = int(args.get("max_bytes") or _RAW_FILE_MAX_BYTES)
    except (TypeError, ValueError):
        max_bytes = _RAW_FILE_MAX_BYTES
    max_bytes = max(1, min(max_bytes, _RAW_FILE_MAX_BYTES))

    target, err = _resolve_under_data_dir(rel)
    if err:
        return {"error": err}
    if target is None or not target.exists():
        return {"error": f"file not found: {rel}"}
    if not target.is_file():
        return {"error": f"not a regular file: {rel}"}

    ext = target.suffix.lower()

    # xlsx/xls: open the workbook in-memory (no DuckDB load), surface sheet
    # names + columns + a row preview the model can quote / aggregate over.
    if ext in _XLSX_EXTS:
        sheet = args.get("sheet")
        if isinstance(sheet, str):
            sheet = sheet.strip() or None
        else:
            sheet = None
        max_rows_arg = args.get("max_rows")
        try:
            max_rows = int(max_rows_arg) if max_rows_arg is not None else None
        except (TypeError, ValueError):
            max_rows = None
        try:
            result = _read_xlsx(target, sheet, max_rows)
        except RuntimeError as e:
            return {"error": str(e), "path": rel}
        except Exception as e:
            return {"error": f"xlsx read failed: {type(e).__name__}: {e}",
                    "path": rel}
        result["path"] = rel
        result["size_bytes"] = int(target.stat().st_size)
        result["encoding"] = "xlsx-extracted"
        return result

    # PDFs: extract text via pypdf; budget chars at max_bytes (1 char ~ 1 byte).
    if ext in _PDF_EXTS:
        try:
            text, pages, truncated = _read_pdf_text(target, max_bytes)
        except RuntimeError as e:
            return {"error": str(e), "path": rel}
        except Exception as e:
            return {"error": f"PDF extraction failed: {type(e).__name__}: {e}",
                    "path": rel}
        return {
            "path": rel,
            "size_bytes": int(target.stat().st_size),
            "bytes_read": len(text),
            "truncated": truncated,
            "encoding": "pdf-extracted",
            "pages": pages,
            "content": text,
        }

    try:
        size = int(target.stat().st_size)
        with target.open("rb") as fh:
            raw = fh.read(max_bytes)
    except OSError as e:
        return {"error": f"read failed: {e}"}

    # Reject obvious binaries (NUL byte heuristic) before paying the decode cost.
    if b"\x00" in raw[:4096]:
        return {
            "error": (
                f"file appears to be binary ({size} bytes); read_file "
                "only supports text files, pdf (extracted), and xlsx/xls "
                "(extracted)"
            ),
            "path": rel,
            "size_bytes": size,
        }

    encoding = "utf-8"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
            encoding = "latin-1"
        except Exception:
            return {
                "error": f"file is not decodable as utf-8 or latin-1 ({size} bytes)",
                "path": rel,
                "size_bytes": size,
            }

    return {
        "path": rel,
        "size_bytes": size,
        "bytes_read": len(raw),
        "truncated": size > len(raw),
        "encoding": encoding,
        "content": text,
    }


TOOLS_SPEC: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": (
                "Execute a read-only SQL query against the local DuckDB database "
                "and return up to 100 rows. Only SELECT and WITH ... SELECT are "
                "allowed; INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE are "
                "blocked. Use this for any question that needs to look at data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A single SELECT or WITH statement.",
                    },
                    "explanation": {
                        "type": "string",
                        "description": "One-sentence rationale for the query.",
                    },
                },
                "required": ["sql", "explanation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_plot",
            "description": (
                "Run matplotlib/seaborn Python code in a sandbox to produce a "
                "single PNG plot. The code has access to: run_sql(sql)->DataFrame, "
                "pd, np, plt, sns, sklearn, and a pre-injected BytesIO named "
                "'buf'. The code MUST end with "
                "plt.savefig(buf, format='png', dpi=100, bbox_inches='tight'). "
                "Maximum figure size 7x6 inches. Use only when the user asks for "
                "a visualization."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code that draws and saves the plot.",
                    },
                    "title": {"type": "string"},
                },
                "required": ["code", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files in the Alchemist data directory (sandboxed; "
                "cannot escape it). Use to discover raw files the user has "
                "dropped in, then call read_file on the interesting ones. "
                "Tabular files (.csv/.tsv/.parquet/.json/.ndjson) are also "
                "auto-imported as DuckDB tables — prefer query_data for those."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subpath": {
                        "type": "string",
                        "description": "Optional subdirectory under the data dir. Empty = whole data dir.",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional glob pattern (default '*'). E.g. '*.md', '**/*.txt'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": f"Cap on files returned (default and max {_RAW_FILE_LIST_LIMIT}).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the Alchemist data directory. The path "
                "must be relative to that directory (no '..' escapes, no "
                "absolute paths). Behavior by type:\n"
                "  - Text files (.md/.txt/.log/source/etc.) are returned "
                f"verbatim (up to {_RAW_FILE_MAX_BYTES} bytes).\n"
                "  - PDFs are text-extracted via pypdf; response includes "
                "a 'pages' field and content is delimited by "
                "'--- page N/M ---' markers.\n"
                "  - xlsx/xls workbooks are opened with pandas/openpyxl "
                "and returned as structured sheet metadata (no DuckDB "
                "import). With no 'sheet' arg you get every sheet's "
                "columns + a small preview; pass sheet=<name> (and "
                f"optionally max_rows up to {_XLSX_MAX_ROWS}) to drill "
                "into one sheet for more rows.\n"
                "  - Other binary files are refused."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to ALCHEMIST_DATA_DIR.",
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": (
                            f"Text/PDF only: byte (or char) cap "
                            f"(default and max {_RAW_FILE_MAX_BYTES})."
                        ),
                    },
                    "sheet": {
                        "type": "string",
                        "description": (
                            "xlsx only: name of a specific sheet to read. "
                            "Omit to get a summary of every sheet."
                        ),
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": (
                            "xlsx only: row preview cap "
                            f"(default {_XLSX_DEFAULT_PREVIEW} per sheet in summary mode, "
                            f"{_XLSX_SHEET_DEFAULT_ROWS} when 'sheet' is set; "
                            f"hard max {_XLSX_MAX_ROWS})."
                        ),
                    },
                },
                "required": ["path"],
            },
        },
    },
]


# Fallback prompt template, used when message_catalogs/en/alchemist_system_prompt.md
# is missing. Keep in sync with the catalog file.
_FALLBACK_SYSTEM_PROMPT = """You are Alchemist (Generative AI Assistant), a knowledgeable data analyst.
You have access to a local DuckDB database AND the raw files the user dropped
into the data directory. Use the tools to answer questions with real data.

Tools:
- query_data: SELECT against tabular data (CSV/TSV/Parquet/JSON imported as
  DuckDB tables). Prefer this for any structured-data question.
- generate_plot: only when the user explicitly asks for a chart/plot.
- list_files: enumerate raw files under the data directory (with optional
  subpath / glob). Use this to see what files exist.
- read_file: read a single file by path relative to the data directory.
  Text returned verbatim. PDFs are text-extracted via pypdf. xlsx/xls
  workbooks are opened with pandas/openpyxl: with no 'sheet' arg you get
  every sheet's columns + a row preview; pass sheet=<name> (and optional
  max_rows up to 200) to drill into one sheet.

Rules:
- NEVER claim data is absent without checking first (query_data + list_files).
- Prefer concise answers that cite actual numbers / quoted snippets.
- Never fabricate tables, columns, or file contents; only use what the tools return.
- Maximum plot size is 7x6 inches; always close figures when done.
- If the user supplies an active data slice, treat it as a default WHERE filter.

DATABASE SCHEMA AND RAW FILES:
{schema}
"""


def _load_system_prompt_template() -> str:
    """Load the system prompt template from the message catalog.

    Lookup order (first hit wins):
      1. $ALCHEMIST_SYSTEM_PROMPT_FILE
      2. <module dir>/message_catalogs/<lang>/alchemist_system_prompt.md
      3. _FALLBACK_SYSTEM_PROMPT (baked-in)
    """
    override = os.getenv("ALCHEMIST_SYSTEM_PROMPT_FILE")
    if override:
        p = Path(override)
        if p.exists():
            return p.read_text(encoding="utf-8")
    lang = os.getenv("ALCHEMIST_LANG", "en")
    candidate = Path(__file__).resolve().parent / "message_catalogs" / lang / "alchemist_system_prompt.md"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return _FALLBACK_SYSTEM_PROMPT


# Kept as a module-level constant for backward compatibility with anything
# that imported SYSTEM_PROMPT_BASE directly.
SYSTEM_PROMPT_BASE = _load_system_prompt_template()


def _model() -> str:
    return os.getenv("ALCHEMIST_MODEL", "gpt-4o")


# Models in the GPT-5 and o-series (reasoning) families only accept the
# default temperature (1.0). Sending temperature=0.1 yields a 400.
_FIXED_TEMP_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _supports_temperature(model: str) -> bool:
    m = (model or "").lower()
    return not any(m.startswith(p) for p in _FIXED_TEMP_PREFIXES)


def _is_reasoning_model(model: str) -> bool:
    """gpt-5 and o-series models accept a `reasoning_effort` parameter."""
    return not _supports_temperature(model)


def ask(
    db_path: str,
    question: str,
    *,
    history: list[dict] | None = None,
    slice_context: str = "",
) -> dict:
    """Single chat turn. Returns ``{answer, images, model, tokens_used}``.

    ``history`` is a list of ``{role, content}`` dicts (user/assistant only;
    tool messages are not echoed back). ``slice_context`` is a short natural
    language description of the active data slice; when non-empty it is
    appended to the user's question as a bracketed instruction.
    """
    model = _model()
    if OpenAI is None:
        return {
            "answer": "The `openai` package is not installed. "
                      "Run: pip install -r requirements.txt",
            "images": [], "model": model, "tokens_used": 0,
        }
    if not os.getenv("OPENAI_API_KEY"):
        return {
            "answer": "OPENAI_API_KEY is not set. Export it and reload.",
            "images": [], "model": model, "tokens_used": 0,
        }

    client = OpenAI()
    schema_text = get_schema_text(db_path)
    system = _load_system_prompt_template().format(schema=schema_text)

    user_msg = question
    if slice_context.strip():
        user_msg = (
            f"{question}\n\n[Active data slice: {slice_context.strip()}. "
            f"Apply these filters unless I say otherwise.]"
        )

    messages: list[dict] = [{"role": "system", "content": system}]
    for m in history or []:
        role = m.get("role")
        if role in ("user", "assistant") and m.get("content"):
            messages.append({"role": role, "content": m["content"]})
    messages.append({"role": "user", "content": user_msg})

    images: list[str] = []
    tokens_used = 0
    deadline = time.time() + 55.0
    max_iters = 3
    final_text = ""
    tools_called: list[str] = []
    iterations_used = 0

    for i in range(max_iters):
        iterations_used = i + 1
        time_left = deadline - time.time()
        # Out of budget or last iteration -> force a textual answer
        force_no_tools = (time_left < 5.0) or (i == max_iters - 1)
        tool_choice = "none" if force_no_tools else "auto"

        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "tools": TOOLS_SPEC,
                "tool_choice": tool_choice,
            }
            if _supports_temperature(model):
                kwargs["temperature"] = float(os.getenv("ALCHEMIST_TEMPERATURE", "0.1"))
            elif _is_reasoning_model(model):
                # Default to 'minimal' so simple queries return quickly; override
                # via ALCHEMIST_REASONING_EFFORT={minimal|low|medium|high}.
                effort = os.getenv("ALCHEMIST_REASONING_EFFORT", "minimal").strip().lower()
                if effort in ("minimal", "low", "medium", "high"):
                    kwargs["reasoning_effort"] = effort
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            return {
                "answer": f"Model call failed: {e}",
                "images": images, "model": model, "tokens_used": tokens_used,
            }

        if resp.usage:
            tokens_used += int(resp.usage.total_tokens or 0)

        msg = resp.choices[0].message
        if msg.content:
            final_text = msg.content

        tool_calls = msg.tool_calls or []
        if not tool_calls:
            break

        assistant_turn: dict = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        }
        # OpenAI accepts content=null with tool_calls; never send empty string.
        if msg.content:
            assistant_turn["content"] = msg.content
        messages.append(assistant_turn)

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            # Tool dispatch must never raise out of ask(); always return a tool message.
            tools_called.append(name)
            try:
                if name == "query_data":
                    result = _tool_query_data(db_path, args)
                elif name == "generate_plot":
                    raw = _tool_generate_plot(db_path, args)
                    if "image_base64" in raw:
                        images.append(raw["image_base64"])
                        # Don't echo the base64 payload back into the chat context.
                        result = {
                            "ok": True,
                            "title": raw.get("title", ""),
                            "note": "image was returned to the user",
                        }
                    else:
                        result = raw
                elif name == "list_files":
                    result = _tool_list_files(db_path, args)
                elif name == "read_file":
                    result = _tool_read_file(db_path, args)
                else:
                    result = {"error": f"Unknown tool: {name}"}
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}"}

            try:
                content = json.dumps(result, default=str)[:8000]
            except Exception as e:
                content = json.dumps({"error": f"unserializable tool result: {e}"})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": content,
            })

        if time.time() >= deadline:
            break

    if not final_text:
        # Diagnostic fallback so the user knows WHY no answer landed.
        called = ", ".join(tools_called) if tools_called else "(none)"
        ran_out = (time.time() - (deadline - 55.0)) >= 54.5
        why = []
        if iterations_used >= max_iters:
            why.append(f"hit max iterations ({max_iters})")
        if ran_out:
            why.append("hit 55s wall-clock budget")
        if _is_reasoning_model(model):
            why.append(f"model={model} (reasoning model; try ALCHEMIST_REASONING_EFFORT=minimal or switch to gpt-4.1)")
        reason = "; ".join(why) or "model returned an empty assistant message"
        final_text = (
            f"_(no answer produced — {reason}. Tools called: {called}. "
            f"Tokens used: {tokens_used}.)_"
        )

    return {
        "answer": final_text,
        "images": images,
        "model": model,
        "tokens_used": tokens_used,
    }


__all__ = [
    "ask",
    "invalidate_schema_cache",
    "get_schema_text",
    "is_safe_select",
    "TOOLS_SPEC",
]
