# Alchemist Desktop

A locally-runnable, single-page AI chat assistant that can query, visualize,
and explore tabular data sitting in a local DuckDB database. No cloud, no
Docker, no S3.

## Quick start

```bash
cd alchemist
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...
# Drop CSV / Parquet / JSON files into ./data/
python app.py
```

Open <http://localhost:8000>.

## Pointing at an existing DuckDB (e.g. the mcbo ingest)

Alchemist also happily uses a DuckDB file you built elsewhere. The mcbo
repo's `mcbo-build-duckdb` produces exactly that:

```bash
# from the repo root
mcbo-build-duckdb --data-dir data.sample

cd alchemist
ALCHEMIST_DB_PATH=../data.sample/mcbo.duckdb \
ALCHEMIST_DATA_DIR=/tmp/empty \
OPENAI_API_KEY=sk-... \
python app.py
```

With `ALCHEMIST_DATA_DIR` pointing at an empty directory, the loader will
not overwrite the existing tables in `mcbo.duckdb`; Alchemist will read the
schema (samples, expression_long, ...) and chat against it.

## Configuration

| Variable             | Default              | Purpose                              |
|----------------------|----------------------|--------------------------------------|
| `OPENAI_API_KEY`     | (required)           | OpenAI API key                       |
| `ALCHEMIST_MODEL`    | `gpt-4o`             | OpenAI model to use                  |
| `ALCHEMIST_DATA_DIR` | `./data`             | Directory scanned for data files     |
| `ALCHEMIST_DB_PATH`  | `./alchemist.duckdb` | DuckDB file (persists across runs)   |
| `ALCHEMIST_CONV_DIR` | `./conversations`    | Conversation + plot storage          |
| `ALCHEMIST_PORT`     | `8000`               | HTTP port                            |

## Layout

```
alchemist/
  app.py                # FastAPI app, routes, lifespan
  alchemist_engine.py   # OpenAI tool-calling loop (query_data, generate_plot)
  data_loader.py        # CSV / Parquet / JSON -> DuckDB importer + schema
  conversations.py      # JSON-file conversation store + plot persistence
  templates/index.html  # Single-page UI (CSS + JS inline, no npm)
  data/                 # Drop CSV / Parquet / JSON files here
  conversations/        # Auto-created: conversation JSON + plot PNGs
  requirements.txt
```

## What the assistant can do

- Answer questions about your tables (it sees the schema automatically).
- Run read-only SQL (SELECT / WITH only; INSERT/UPDATE/DELETE/DROP blocked).
- Generate matplotlib / seaborn plots in a sandbox with access to
  `run_sql(sql) -> DataFrame`, `pd`, `np`, `plt`, `sns`, `sklearn`.
- Honor an "active data slice" - filters you pick in the Slice panel are
  appended to every question as a bracketed instruction.

## API

| Method | Path                                          | Purpose                            |
|--------|-----------------------------------------------|------------------------------------|
| GET    | `/`                                           | Single-page UI                     |
| POST   | `/api/chat`                                   | `{question, history, slice_context}` -> `{answer, images, model, tokens_used}` |
| GET    | `/api/data/schema`                            | Current DuckDB schema              |
| POST   | `/api/data/reload`                            | Re-scan `ALCHEMIST_DATA_DIR`       |
| GET    | `/api/conversations`                          | List conversations                 |
| GET    | `/api/conversations/{id}`                     | Get conversation                   |
| PUT    | `/api/conversations/{id}`                     | Save conversation                  |
| DELETE | `/api/conversations/{id}`                     | Delete conversation                |
| GET    | `/api/conversations/{id}/plots/{msg_idx}`     | Get persisted plot PNG             |
