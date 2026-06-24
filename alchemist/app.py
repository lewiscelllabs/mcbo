"""Alchemist Desktop - FastAPI application.

Run with:
    python app.py
or
    uvicorn app:app --reload
"""

from __future__ import annotations

import base64
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import file_tools  # local module; shared with mcbo_engine via lazy load.


HERE = Path(__file__).resolve().parent

# Load .env early so OPENAI_API_KEY etc. are available everywhere below.
def _load_dotenv() -> None:
    candidates = [HERE / ".env", Path.cwd() / ".env"]
    try:
        from dotenv import load_dotenv  # type: ignore
        for p in candidates:
            if p.exists():
                load_dotenv(p, override=False)
        return
    except ImportError:
        pass
    # Tiny fallback parser (KEY=VALUE, comments + blank lines ignored)
    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)

_load_dotenv()

from alchemist_engine import ask, invalidate_schema_cache  # noqa: E402
from conversations import ConversationStore, new_id  # noqa: E402
from data_loader import (  # noqa: E402
    coverage_report,
    empty_columns,
    get_schema,
    get_slice_options,
    load_directory,
)


DATA_DIR = Path(os.getenv("ALCHEMIST_DATA_DIR", HERE / "data"))
DB_PATH = Path(os.getenv("ALCHEMIST_DB_PATH", HERE / "alchemist.duckdb"))
CONV_DIR = Path(os.getenv("ALCHEMIST_CONV_DIR", HERE / "conversations"))
PORT = int(os.getenv("ALCHEMIST_PORT", "8000"))
USE_MCBO = os.getenv("ALCHEMIST_USE_MCBO", "").strip().lower() in ("1", "true", "yes", "on")
# Per-file upload size cap. Browsers/proxies often refuse much larger uploads
# anyway; the default keeps a stray multi-GB drop from filling the disk.
MAX_UPLOAD_BYTES = int(os.getenv("ALCHEMIST_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))

templates = Jinja2Templates(directory=str(HERE / "templates"))
store = ConversationStore(CONV_DIR)


def _reload_everything() -> dict:
    """Re-scan the data directory and refresh the schema cache."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    load_result = load_directory(DB_PATH, DATA_DIR)
    invalidate_schema_cache(str(DB_PATH))
    return {
        "import_results": load_result.get("files", []),
        "normalizations": load_result.get("normalizations", []),
        "schema": get_schema(DB_PATH),
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    info = _reload_everything()
    print(f"Alchemist Desktop running at http://localhost:{PORT}")
    tables = info["schema"].get("tables", [])
    if tables:
        print("Loaded tables:")
        for t in tables:
            print(f"  - {t['name']} ({t['rows']} rows, {len(t['columns'])} cols)")
    else:
        print(
            f"(no tables loaded; drop CSV/Parquet/JSON files into {DATA_DIR} "
            "and POST /api/data/reload)"
        )

    # Surface any post-import data-curation fixes (e.g., the 'Pefusion' typo).
    for note in info.get("normalizations", []):
        print(f"  [normalized] {note}")

    # Warn about silently-empty columns so demo'ers don't ask the agent a
    # question that will inevitably come back as "data not available".
    try:
        empties = empty_columns(DB_PATH, min_table_rows=10)
        if empties:
            by_table: dict[str, list[str]] = {}
            for tbl, col in empties:
                by_table.setdefault(tbl, []).append(col)
            print("Heads up: these columns exist but are 100% NULL (no data):")
            for tbl, cols in by_table.items():
                preview = ", ".join(cols[:8])
                more = f" (+{len(cols)-8} more)" if len(cols) > 8 else ""
                print(f"  - {tbl}: {preview}{more}")
            print("  -> avoid asking the agent about these columns; it will (correctly) say there's no data.")
    except Exception as e:
        print(f"  (coverage check skipped: {e})")
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY is not set; chat will return an error.")
    if USE_MCBO:
        print("Chat backend: mcbo dual-tool agent (SPARQL + DuckDB SQL + stats)")
        # Eagerly parse the (large) Turtle graph at server boot via the
        # pyoxigraph fast path. This shifts the one-time load cost (~13s on
        # a 4.5M-triple graph) out of the first chat request, so demo
        # interactions stay snappy.
        print("Pre-warming mcbo agent (parsing graph)...", flush=True)
        from mcbo_engine import prewarm  # lazy import
        status = prewarm(str(DB_PATH))
        if status.get("ok"):
            print(f"mcbo agent ready (graph loaded in {status['elapsed_s']}s).")
        else:
            print(f"WARNING: mcbo prewarm failed: {status.get('error')}")
            print("  -> first chat request will surface this error too.")
    yield


app = FastAPI(title="Alchemist Desktop", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/img/{filename}")
async def serve_img(filename: str):
    path = HERE / "img" / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Not found")
    suffix = path.suffix.lower()
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                   ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp"}
    return FileResponse(str(path), media_type=media_types.get(suffix, "application/octet-stream"))


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str
    history: list[dict] = Field(default_factory=list)
    conversation_id: str | None = None
    slice_context: str = ""


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(400, "question is required")
    try:
        if USE_MCBO:
            from mcbo_engine import ask as mcbo_ask  # lazy import: only when enabled
            return mcbo_ask(
                str(DB_PATH),
                req.question,
                history=req.history,
                slice_context=req.slice_context,
            )
        return ask(
            str(DB_PATH),
            req.question,
            history=req.history,
            slice_context=req.slice_context,
        )
    except Exception as e:
        # Surface the real error to the UI instead of letting it become a generic 500.
        tb = traceback.format_exc()
        print("\n[/api/chat] ERROR:\n" + tb, flush=True)
        return JSONResponse(
            status_code=200,
            content={
                "answer": f"**Server error**: `{type(e).__name__}: {e}`\n\n"
                          "Check the terminal where you started `python app.py` for the full traceback.",
                "images": [],
                "model": os.getenv("ALCHEMIST_MODEL", "gpt-4o"),
                "tokens_used": 0,
                "error": str(e),
            },
        )


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"\n[{request.url.path}] UNHANDLED:\n{tb}", flush=True)
    return JSONResponse(
        status_code=500,
        content={"error": f"{type(exc).__name__}: {exc}", "path": request.url.path},
    )


# ---------------------------------------------------------------------------
# Data / schema
# ---------------------------------------------------------------------------

@app.get("/api/data/schema")
async def schema():
    return get_schema(DB_PATH)


@app.get("/api/data/slice_options")
async def slice_options():
    return get_slice_options(DB_PATH)


@app.post("/api/data/reload")
async def reload_data():
    return _reload_everything()


def _sanitize_upload_filename(raw: str) -> tuple[str | None, str]:
    """Normalize a client-supplied filename into a relative path under DATA_DIR.

    Returns ``(safe_relative_path, "")`` on success or ``(None, error)`` on
    rejection. Accepts forward-slash subpaths (so ``raw/foo.xlsx`` lands in
    ``DATA_DIR/raw/foo.xlsx``) so directory uploads via
    ``<input webkitdirectory>`` work. Rejects absolute paths, Windows
    drive-letter paths, ``..`` escapes, and NUL bytes.
    """
    if not raw or not raw.strip():
        return None, "missing filename"
    name = raw.strip().replace("\\", "/")
    if "\x00" in name:
        return None, f"filename contains NUL byte: {raw!r}"
    if name.startswith("/"):
        return None, f"absolute paths are not allowed: {raw!r}"
    if len(name) >= 2 and name[1] == ":":  # e.g. "C:..."
        return None, f"absolute (drive-letter) paths are not allowed: {raw!r}"
    if name in (".", ".."):
        return None, "filename resolves to data directory itself"
    # file_tools.resolve_under_data_dir handles the .. / sandbox guard.
    target, err = file_tools.resolve_under_data_dir(name)
    if err or target is None:
        return None, err or "could not resolve target path"
    return name, ""


@app.post("/api/data/upload")
async def upload_data(files: list[UploadFile] = File(...)):
    """Upload one or more files into the Alchemist data directory.

    Each file is written under ``ALCHEMIST_DATA_DIR``. Filenames may
    contain forward-slash subpaths (``raw/foo.xlsx``) and will create
    intermediate directories as needed; absolute paths and ``..``
    escapes are rejected. After all writes, the data loader is
    triggered so any tabular files become DuckDB tables immediately.

    Returns ``{uploaded: [...], rejected: [...], reload, data_dir}``.
    Always returns 200 -- per-file errors are surfaced in ``rejected``
    so the UI can show a partial-success toast.
    """
    if not files:
        raise HTTPException(400, "no files in upload")

    base = file_tools.data_dir()
    base.mkdir(parents=True, exist_ok=True)

    uploaded: list[dict] = []
    rejected: list[dict] = []

    for f in files:
        client_name = f.filename or ""
        safe_name, err = _sanitize_upload_filename(client_name)
        if err or safe_name is None:
            rejected.append({"filename": client_name, "error": err})
            continue
        target = (base / safe_name).resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            rejected.append({"filename": client_name, "error": f"mkdir failed: {e}"})
            continue

        overwritten = target.exists()
        bytes_written = 0
        try:
            # Stream in chunks so a single huge upload can't blow the
            # event loop's memory; cap at MAX_UPLOAD_BYTES.
            with target.open("wb") as out:
                while True:
                    chunk = await f.read(1024 * 1024)  # 1 MB
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > MAX_UPLOAD_BYTES:
                        out.close()
                        target.unlink(missing_ok=True)
                        raise ValueError(
                            f"file exceeds upload cap of "
                            f"{MAX_UPLOAD_BYTES} bytes"
                        )
                    out.write(chunk)
        except Exception as e:
            rejected.append({"filename": client_name, "error": str(e)})
            continue
        finally:
            try:
                await f.close()
            except Exception:
                pass

        uploaded.append({
            "filename": client_name,
            "saved_as": safe_name,
            "size_bytes": bytes_written,
            "overwritten": overwritten,
        })

    # Re-scan + re-import so any tabular files become DuckDB tables and
    # the schema/slice options refresh on the next UI poll.
    reload_info: dict | None = None
    if uploaded:
        try:
            reload_info = _reload_everything()
        except Exception as e:
            reload_info = {"error": f"reload failed: {type(e).__name__}: {e}"}

    return {
        "data_dir": str(base),
        "uploaded": uploaded,
        "rejected": rejected,
        "reload": reload_info,
    }


@app.get("/api/data/coverage")
async def data_coverage():
    """Per-column non-null coverage for every table.

    Returns ``{tables: {tname: {total_rows, columns: {cname: {non_null, pct}}}},
    summary: {total_tables, total_columns, empty_columns: [[tbl, col], ...]}}``.

    Used by the sidebar "Data health" panel to surface columns that are 100%
    NULL (a common cause of "data not available" answers from the agent).
    """
    report = coverage_report(DB_PATH)
    tables_out: dict[str, dict] = {}
    total_columns = 0
    for tbl, cols in report.items():
        total = next(iter(cols.values()))["total"] if cols else 0
        tables_out[tbl] = {
            "total_rows": total,
            "columns": {
                cname: {"non_null": info["non_null"], "pct": info["pct"]}
                for cname, info in cols.items()
            },
        }
        total_columns += len(cols)
    return {
        "tables": tables_out,
        "summary": {
            "total_tables": len(tables_out),
            "total_columns": total_columns,
            "empty_columns": [list(t) for t in empty_columns(DB_PATH, min_table_rows=10)],
        },
    }


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class SaveConvRequest(BaseModel):
    messages: list[dict]


@app.get("/api/conversations")
async def list_conversations():
    return store.list()


@app.post("/api/conversations/new")
async def create_conversation():
    return {"id": new_id()}


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    data = store.get(conv_id)
    if data is None:
        raise HTTPException(404, "Conversation not found")
    return data


@app.put("/api/conversations/{conv_id}")
async def save_conversation(conv_id: str, req: SaveConvRequest):
    # Persist any base64 plot images to disk so they survive reloads.
    sanitized_messages: list[dict] = []
    for idx, m in enumerate(req.messages):
        sanitized = {k: v for k, v in m.items() if k != "images"}
        images = m.get("images") or []
        if images:
            saved_indices: list[int] = []
            for j, b64 in enumerate(images):
                msg_idx = idx if j == 0 else (idx * 1000 + j)
                try:
                    png = base64.b64decode(b64)
                    store.save_plot(conv_id, msg_idx, png)
                    saved_indices.append(msg_idx)
                except Exception:
                    continue
            if saved_indices:
                sanitized["plot_indices"] = saved_indices
        sanitized_messages.append(sanitized)
    return store.save(conv_id, sanitized_messages)


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if not store.delete(conv_id):
        raise HTTPException(404, "Conversation not found")
    return {"deleted": conv_id}


@app.get("/api/conversations/{conv_id}/plots/{msg_idx}")
async def get_plot(conv_id: str, msg_idx: int):
    p = store.plot_path(conv_id, msg_idx)
    if p is None:
        raise HTTPException(404, "Plot not found")
    return FileResponse(p, media_type="image/png")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        # Force exit within 2s on Ctrl-C, even if a long LLM call is in flight.
        timeout_graceful_shutdown=2,
    )
