"""Adapter that lets Alchemist's /api/chat route into the mcbo dual-tool agent.

Wraps ``mcbo.agent.orchestrator.AgentOrchestrator`` (SPARQL + DuckDB SQL +
stats + pathway tools) behind the same ``ask()`` signature exposed by
``alchemist_engine.ask``. This module is imported only when
``ALCHEMIST_USE_MCBO`` is truthy, so the default Alchemist runtime is
unaffected.

Required environment / paths when enabled:
    ALCHEMIST_USE_MCBO=1                # opt-in flag (read in app.py)
    ALCHEMIST_DB_PATH=<.../mcbo.duckdb> # already used by Alchemist
    ALCHEMIST_GRAPH_PATH=<.../graph.ttl># optional; defaults to <db parent>/graph.ttl
    OPENAI_API_KEY=...                  # mcbo OpenAIProvider uses this

Notes / caveats (intentional, to keep the change minimal):
- ``history`` (user/assistant turns only) is forwarded to the orchestrator.
- ``images`` are captured from the shared executor's ``self.images`` list,
  which the new ``generate_plot`` tool appends to.
- Per-request transient executor state (current_df, de_results, images) is
  reset at the start of each call to avoid bleed across conversation turns.
- The graph (often 100K+ triples) is loaded lazily on first request and
  cached; rebuild happens only if ``db_path`` changes.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path
from threading import Lock
from typing import Any


_LOCK = Lock()
_STATE: dict[str, Any] = {"orchestrator": None, "db_path": None}


def _ensure_mcbo_on_path() -> None:
    """Make ``python/mcbo`` importable when alchemist runs as a sibling project."""
    here = Path(__file__).resolve().parent
    repo_python = here.parent / "python"
    if repo_python.exists() and str(repo_python) not in sys.path:
        sys.path.insert(0, str(repo_python))


def _resolve_graph_path(db_path: str) -> Path:
    env = os.getenv("ALCHEMIST_GRAPH_PATH")
    if env:
        return Path(env)
    return Path(db_path).parent / "graph.ttl"


def _fast_load_graph(graph_path: Path):
    """Parse Turtle via ``pyoxigraph.Store.bulk_load`` (10-20x faster than
    rdflib's pure-Python parser on multi-million-triple graphs), then wrap
    the resulting store in ``rdflib.Graph(store=OxigraphStore(...))`` so the
    mcbo SPARQL tool can keep using the standard rdflib ``.query()`` API.

    Falls back to ``mcbo.graph_utils.load_graphs`` if the fast stack isn't
    installed.
    """
    try:
        import pyoxigraph
        from oxrdflib import OxigraphStore
        import rdflib
    except ImportError as e:
        print(
            f"[mcbo_engine] fast loader unavailable ({e}); "
            "falling back to rdflib Turtle parser (slow).",
            flush=True,
        )
        from mcbo.graph_utils import load_graphs
        return load_graphs([graph_path])

    t0 = time.time()
    store = pyoxigraph.Store()
    store.bulk_load(path=str(graph_path), format=pyoxigraph.RdfFormat.TURTLE)
    n = len(store)
    # NOTE: ``bulk_load`` puts triples in the dataset's default graph; we
    # must use rdflib's default-graph identifier so ``Graph.query()`` (which
    # is scoped to one named graph) actually sees them.
    g = rdflib.Graph(
        store=OxigraphStore(store=store),
        identifier=rdflib.URIRef("urn:x-rdflib:default"),
    )
    print(
        f"[mcbo_engine] fast-loaded {n:,} triples in {time.time() - t0:.1f}s "
        f"(via pyoxigraph.bulk_load + oxrdflib)",
        flush=True,
    )
    return g


def _build_orchestrator(db_path: str):
    _ensure_mcbo_on_path()
    from mcbo.agent.orchestrator import AgentOrchestrator, OpenAIProvider

    graph_path = _resolve_graph_path(db_path)
    if not graph_path.exists():
        raise FileNotFoundError(
            f"mcbo graph not found at {graph_path}. "
            "Build it with: mcbo-build-graph build --data-dir <dir>"
        )
    print(f"[mcbo_engine] loading graph from {graph_path} ...", flush=True)
    graph = _fast_load_graph(graph_path)

    provider = OpenAIProvider(model=os.getenv("ALCHEMIST_MODEL", "gpt-4o"))
    # Complex PCA / multi-step plot workflows easily eat 6-10 tool-call
    # iterations (top-genes query, fetch, plot, retry-on-error, ...). The
    # mcbo default of 10 is too tight for the Alchemist demo, so bump it.
    # Configurable via MCBO_MAX_ITERATIONS env var.
    max_iter = int(os.getenv("MCBO_MAX_ITERATIONS", "20"))
    return AgentOrchestrator(
        graph=graph,
        provider=provider,
        duckdb_path=Path(db_path),
        max_iterations=max_iter,
        verbose=False,
    )


def _get_orchestrator(db_path: str):
    with _LOCK:
        if _STATE["orchestrator"] is None or _STATE["db_path"] != db_path:
            _STATE["orchestrator"] = _build_orchestrator(db_path)
            _STATE["db_path"] = db_path
        return _STATE["orchestrator"]


def prewarm(db_path: str) -> dict:
    """Eagerly load the graph + build the orchestrator at server boot, so the
    first chat request doesn't pay the ~13s parse cost.

    Returns a small status dict for the lifespan log; never raises (errors
    are swallowed and reported so the server still comes up and the first
    chat call can surface a clean error message).
    """
    try:
        t0 = time.time()
        _get_orchestrator(db_path)
        return {"ok": True, "elapsed_s": round(time.time() - t0, 1)}
    except Exception as e:
        print(f"[mcbo_engine] prewarm failed: {type(e).__name__}: {e}", flush=True)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def ask(
    db_path: str,
    question: str,
    *,
    history: list[dict] | None = None,
    slice_context: str = "",
) -> dict:
    """Drop-in replacement for ``alchemist_engine.ask``."""
    model = os.getenv("ALCHEMIST_MODEL", "gpt-4o")
    if not os.getenv("OPENAI_API_KEY"):
        return {
            "answer": "OPENAI_API_KEY is not set.",
            "images": [], "model": model, "tokens_used": 0,
        }

    try:
        orch = _get_orchestrator(db_path)
    except Exception as e:
        return {
            "answer": f"mcbo mode failed to initialize: `{type(e).__name__}: {e}`",
            "images": [], "model": model, "tokens_used": 0,
        }

    q = question
    if slice_context.strip():
        q = (
            f"{question}\n\n[Active data slice: {slice_context.strip()}. "
            "Apply these filters unless I say otherwise.]"
        )

    # Reset transient per-turn state so prior queries / plots don't bleed in.
    try:
        orch.executor.reset_state()
    except AttributeError:
        # Older mcbo installs without reset_state(); fall back manually.
        orch.executor.current_df = None
        orch.executor.de_results = None
        orch.executor.images = []

    # Reset per-turn token counters on the provider so we can report just
    # *this* turn's usage (and the UI can sum them up).
    for attr in ("last_input_tokens", "last_output_tokens", "last_total_tokens",
                 "peak_prompt_tokens"):
        try:
            setattr(orch.provider, attr, 0)
        except Exception:
            pass

    try:
        result = orch.answer_question(q, history=history or [])
    except Exception as e:
        print("\n[mcbo_engine] ERROR:\n" + traceback.format_exc(), flush=True)
        return {
            "answer": f"**Server error (mcbo mode)**: `{type(e).__name__}: {e}`",
            "images": [], "model": model, "tokens_used": 0,
        }

    images = list(getattr(orch.executor, "images", []) or [])
    # The UI's "context %" wants the *largest* prompt sent to the model this
    # turn (because tool-using multi-iter turns inflate the cumulative count
    # without ever exceeding the model's context window). Fall back to the
    # last call's total_tokens, then 0.
    tokens_used = (
        int(getattr(orch.provider, "peak_prompt_tokens", 0) or 0)
        or int(getattr(orch.provider, "last_total_tokens", 0) or 0)
    )
    return {
        "answer": result.get("answer", "(no answer)"),
        "images": images,
        "model": model,
        "tokens_used": tokens_used,
    }


__all__ = ["ask", "prewarm"]
