"""Shared file-reading tools (list_files / read_file).

Extracted from ``alchemist_engine`` so the same implementation can be
reused by other orchestrators (notably ``mcbo_engine`` -> the MCBO
``AgentOrchestrator``) without code duplication.

The "data directory" is the same one Alchemist uses for DuckDB
ingestion, resolved from ``ALCHEMIST_DATA_DIR`` (default:
``<this dir>/data``). All path resolution is sandboxed: absolute paths
and ``..`` escapes are rejected.

Public API (engine-agnostic; tools take a ``dict`` of arguments and
return a JSON-serializable ``dict`` result):

    data_dir() -> Path
    resolve_under_data_dir(rel_path) -> (Path | None, str)
    list_files(args) -> dict
    read_file(args) -> dict
    iter_inventory(max_files) -> list[tuple[str, int, str]]

Constants (used by tool-schema descriptions):

    MAX_BYTES, LIST_LIMIT, TABULAR_EXTS, PDF_EXTS, XLSX_EXTS,
    XLSX_DEFAULT_PREVIEW, XLSX_SHEET_DEFAULT_ROWS, XLSX_MAX_ROWS
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Per-read byte cap for read_file. OpenAI tool-result truncation is ~8KB,
# but a higher per-read ceiling lets the engine surface a useful "truncated"
# flag instead of silently chopping content at the tool boundary.
MAX_BYTES = 256 * 1024

LIST_LIMIT = 200

# Tabular files are auto-imported into DuckDB by alchemist's data_loader,
# so the model should prefer query_data / execute_sql over read_file for them.
TABULAR_EXTS = {".csv", ".tsv", ".parquet", ".json", ".ndjson"}

# Extensions handled by content-aware branches inside read_file (binary
# files that get extracted to a structured/text representation in-memory).
PDF_EXTS = {".pdf"}
XLSX_EXTS = {".xlsx", ".xls"}

# Default and maximum row counts for the xlsx preview branch of read_file.
# Multi-sheet summary mode uses XLSX_DEFAULT_PREVIEW per sheet; single-sheet
# mode (when `sheet` arg is passed) defaults to XLSX_SHEET_DEFAULT_ROWS.
# The hard cap protects the 8KB tool-result truncation in the engine loop.
XLSX_DEFAULT_PREVIEW = 5
XLSX_SHEET_DEFAULT_ROWS = 50
XLSX_MAX_ROWS = 200


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def data_dir() -> Path:
    """Resolve the raw-file directory.

    Reads ``ALCHEMIST_DATA_DIR`` from the environment; defaults to
    ``<alchemist module dir>/data``. The default keeps standalone
    ``python app.py`` working out of the box.
    """
    default = Path(__file__).resolve().parent / "data"
    return Path(os.getenv("ALCHEMIST_DATA_DIR", str(default))).resolve()


def resolve_under_data_dir(rel_path: str) -> tuple[Path | None, str]:
    """Resolve ``rel_path`` against ``data_dir()``.

    Rejects empty input, absolute paths, and ``..`` escapes. Returns
    ``(resolved_path, "")`` on success or ``(None, error_message)``.
    """
    base = data_dir()
    s = (rel_path or "").strip()
    if not s or s in ("/", "."):
        return None, "path must be a non-empty file path relative to the data directory"
    candidate = (base / s).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return None, f"path escapes the data directory ({base})"
    return candidate, ""


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def json_safe_cell(v: Any) -> Any:
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


def df_preview_rows(df) -> list[list[Any]]:
    """Convert the head of a DataFrame to JSON-safe row lists."""
    safe = df.astype(object).where(df.notna(), None)
    return [[json_safe_cell(v) for v in row] for row in safe.values.tolist()]


# ---------------------------------------------------------------------------
# Type-aware readers
# ---------------------------------------------------------------------------

def read_xlsx(path: Path, sheet: str | None, max_rows: int | None) -> dict:
    """Open an xlsx/xls workbook and return sheet metadata + a row preview.

    Two modes:
      - ``sheet=None`` (summary): every sheet, with columns + ``XLSX_DEFAULT_PREVIEW``
        preview rows each. Use to discover the workbook layout.
      - ``sheet=<name>``: that one sheet only, with up to ``max_rows`` preview rows
        (default ``XLSX_SHEET_DEFAULT_ROWS``, hard-capped at ``XLSX_MAX_ROWS``).
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
        cap = max(1, min(max_rows or XLSX_SHEET_DEFAULT_ROWS, XLSX_MAX_ROWS))
        try:
            df = pd.read_excel(path, sheet_name=sheet, engine=engine)
        except ValueError:
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
            "preview_rows": df_preview_rows(preview),
            "truncated": total > cap,
        }

    cap = max(1, min(max_rows or XLSX_DEFAULT_PREVIEW, XLSX_MAX_ROWS))
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
            "preview_rows": df_preview_rows(df.head(cap)),
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


def read_pdf_text(path: Path, max_chars: int) -> tuple[str, int, bool]:
    """Extract text from a PDF; return ``(text, page_count, truncated)``."""
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


# ---------------------------------------------------------------------------
# Tool entry points (engine-agnostic)
# ---------------------------------------------------------------------------

def list_files(args: dict) -> dict:
    """Enumerate files under ``data_dir()``.

    Optional args:
      - ``subpath``: directory under the data dir to start in (default: root).
      - ``pattern``: glob pattern (default: ``"*"``).
      - ``max_results``: cap on returned files (default and hard max: ``LIST_LIMIT``).
    """
    subpath = (args.get("subpath") or "").strip().lstrip("/")
    pattern = (args.get("pattern") or "*").strip() or "*"
    try:
        max_results = int(args.get("max_results") or LIST_LIMIT)
    except (TypeError, ValueError):
        max_results = LIST_LIMIT
    max_results = max(1, min(max_results, LIST_LIMIT))

    base = data_dir()
    if not base.exists():
        return {
            "data_dir": str(base),
            "files": [],
            "note": f"data directory does not exist yet: {base}",
        }

    if subpath:
        root, err = resolve_under_data_dir(subpath)
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
        if ext in XLSX_EXTS:
            kind = "xlsx"
        elif ext in TABULAR_EXTS:
            kind = "tabular"
        elif ext in PDF_EXTS:
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


def read_file(args: dict) -> dict:
    """Read a file under ``data_dir()``. Type-aware:

      - ``.pdf``  -> text extracted via pypdf (page-delimited).
      - ``.xlsx`` / ``.xls`` -> sheets + columns + a row preview via
        pandas/openpyxl. Optional args ``sheet`` and ``max_rows`` let the
        model drill into a single sheet for more rows.
      - everything else -> raw bytes decoded as utf-8 / latin-1; binaries
        refused (NUL-byte heuristic).
    """
    rel = (args.get("path") or "").strip()
    if not rel:
        return {"error": "Missing required argument: path"}
    try:
        max_bytes = int(args.get("max_bytes") or MAX_BYTES)
    except (TypeError, ValueError):
        max_bytes = MAX_BYTES
    max_bytes = max(1, min(max_bytes, MAX_BYTES))

    target, err = resolve_under_data_dir(rel)
    if err:
        return {"error": err}
    if target is None or not target.exists():
        return {"error": f"file not found: {rel}"}
    if not target.is_file():
        return {"error": f"not a regular file: {rel}"}

    ext = target.suffix.lower()

    if ext in XLSX_EXTS:
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
            result = read_xlsx(target, sheet, max_rows)
        except RuntimeError as e:
            return {"error": str(e), "path": rel}
        except Exception as e:
            return {"error": f"xlsx read failed: {type(e).__name__}: {e}",
                    "path": rel}
        result["path"] = rel
        result["size_bytes"] = int(target.stat().st_size)
        result["encoding"] = "xlsx-extracted"
        return result

    if ext in PDF_EXTS:
        try:
            text, pages, truncated = read_pdf_text(target, max_bytes)
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


# ---------------------------------------------------------------------------
# Inventory helper (used by Alchemist's system-prompt schema text)
# ---------------------------------------------------------------------------

def iter_inventory(max_files: int = 40) -> list[tuple[str, int, str]]:
    """Return ``[(rel_path, size_bytes, kind_hint), ...]`` for the data dir.

    ``kind_hint`` is a short human-readable label suggesting the right
    tool to use (so the model can pick query_data vs read_file).
    Returns at most ``max_files + 1`` entries; callers should cap to
    ``max_files`` for display and mention the overflow if present.
    """
    base = data_dir()
    if not base.exists():
        return []
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
        if ext in XLSX_EXTS:
            kind = "xlsx (use read_file; pass sheet=<name> to drill in)"
        elif ext in TABULAR_EXTS:
            kind = "tabular (use query_data)"
        elif ext in PDF_EXTS:
            kind = "pdf (use read_file; text is extracted)"
        else:
            kind = "raw text (use read_file)"
        entries.append((rel, size, kind))
        if len(entries) >= max_files + 1:
            break
    return entries


__all__ = [
    "MAX_BYTES",
    "LIST_LIMIT",
    "TABULAR_EXTS",
    "PDF_EXTS",
    "XLSX_EXTS",
    "XLSX_DEFAULT_PREVIEW",
    "XLSX_SHEET_DEFAULT_ROWS",
    "XLSX_MAX_ROWS",
    "data_dir",
    "resolve_under_data_dir",
    "json_safe_cell",
    "df_preview_rows",
    "read_xlsx",
    "read_pdf_text",
    "list_files",
    "read_file",
    "iter_inventory",
]
