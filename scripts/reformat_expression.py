#!/usr/bin/env python3
"""
Reformat iBioHub expression data into per-study matrices for the MCBO pipeline.

Strategy:
  - For most studies: expression columns = unique samples → positional map by sorted SampleAccession
  - For study_barzadd: expression columns = runs → positional map by sorted RunAccession, average per sample
  - Mismatched studies: best-effort, map min(samples, expr_cols) positionally

Input:  .data/raw_expression/2026-04-30_ibiohub_rnaseq_tpm.tsv.gz
Output: .data/expression/<study_id>.csv  (SampleAccession + gene columns)
"""

import csv
import gzip
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / ".data"
RAW_TPM = DATA_DIR / "raw_expression" / "2026-04-30_ibiohub_rnaseq_tpm.tsv.gz"
OUT_DIR = DATA_DIR / "expression"
METADATA = DATA_DIR / "sample_metadata.csv"

# Keep only genes with mean TPM >= this threshold across all samples.
# Prevents OOM when building RDF graph (27K genes × 250 samples is too large).
# mean>=50 → ~3500 genes; mean>=10 → ~9000 genes; mean>=1 → ~12700 genes
MEAN_TPM_THRESHOLD = 50.0

# Expression column prefix → study ID (prefix must not overlap; longer prefixes listed first)
PREFIX_TO_STUDY = {
    "NovakLnc": "study_novak",
    "NovakProd": "study_novak0",
    "WgunyDE":  "study_weinguny1",
    "WgunySub": "study_weinguny2",
    "Barzadd":  "study_barzadd",
    "Chiang":   "study_chiang",
    "Dhiman":   "study_dhiman",
    "Hefzi":    "study_hefzi",
    "Kol":      "study_kol",
    "Malm":     "study_malm",
    "Ngyuen":   "study_nguyen",
    "Orel":     "study_orellana",
    "Papez":    "study_papez",
    "Rucker":   "study_ruckerbauer",
    "Stor":     None,   # not in metadata — skip
    "Syno":     None,
    "Tzani":    "study_tzani",
    "Wijk":     "study_vanwijk",
    "ZeLa":     None,
    "Masson":   None,
    "Hofer":    None,
}

# Studies where expression aligns to runs (not samples)
RUN_ALIGNED = {"study_barzadd"}


def col_sort_key(col: str) -> int:
    m = re.search(r"(\d+)$", col)
    return int(m.group(1)) if m else 0


def get_study(col: str) -> str | None:
    for prefix, study in PREFIX_TO_STUDY.items():
        if col.startswith(prefix) and (len(col) == len(prefix) or col[len(prefix)].isdigit()):
            return study
    return None


def clean_gene(name: str) -> str:
    return re.sub(r"_\d+$", "", name)


def load_metadata():
    """Return dicts: study → sorted unique SampleAccessions,
                     study → sorted unique RunAccessions,
                     run   → SampleAccession."""
    study_samples: dict[str, list[str]] = defaultdict(list)
    study_runs: dict[str, list[str]] = defaultdict(list)
    run_to_sample: dict[str, str] = {}

    seen_samples: dict[str, set] = defaultdict(set)
    seen_runs: dict[str, set] = defaultdict(set)

    with open(METADATA, newline="") as f:
        for row in csv.DictReader(f):
            sid = row["StudyID"]
            sample = row["SampleAccession"]
            run = row["RunAccession"]
            run_to_sample[run] = sample
            if sample not in seen_samples[sid]:
                seen_samples[sid].add(sample)
                study_samples[sid].append(sample)
            if run not in seen_runs[sid]:
                seen_runs[sid].add(run)
                study_runs[sid].append(run)

    # Sort both lists consistently
    for sid in study_samples:
        study_samples[sid].sort()
        study_runs[sid].sort()

    return dict(study_samples), dict(study_runs), run_to_sample


def read_expression_matrix(path: Path):
    """Two-pass read: first compute per-gene mean TPM to filter, then load kept genes.

    Returns (genes, study_data, col_names) where genes pass MEAN_TPM_THRESHOLD.
    """
    print(f"Reading {path.name} ...", flush=True)

    with gzip.open(path, "rt") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)

    sample_cols = header[1:]

    # Group columns by study, preserving numeric sort order
    study_col_indices: dict[str, list[tuple[int, str]]] = defaultdict(list)
    skipped = set()
    for idx, col in enumerate(sample_cols, start=1):
        study = get_study(col)
        if study is None:
            skipped.add(re.sub(r"\d+$", "", col))
            continue
        study_col_indices[study].append((idx, col))

    for study in study_col_indices:
        study_col_indices[study].sort(key=lambda t: col_sort_key(t[1]))

    if skipped:
        print(f"  Skipping prefixes not in metadata: {sorted(skipped)}")

    n_cols = len(sample_cols)

    # Pass 1: compute per-gene mean TPM across ALL samples; collect kept genes
    print(f"  Pass 1: filtering genes (mean TPM >= {MEAN_TPM_THRESHOLD}) ...", flush=True)
    kept_genes: set[str] = set()
    seen_raw: set[str] = set()
    raw_to_clean: dict[str, str] = {}
    with gzip.open(path, "rt") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for row in reader:
            raw = row[0]
            gene = clean_gene(raw)
            if gene in seen_raw:
                continue
            seen_raw.add(gene)
            raw_to_clean[raw] = gene
            try:
                vals = [float(v) for v in row[1:] if v]
                if vals and (sum(vals) / len(vals)) >= MEAN_TPM_THRESHOLD:
                    kept_genes.add(gene)
            except Exception:
                pass

    print(f"  {len(kept_genes)} / {len(seen_raw)} genes pass threshold")

    # Pass 2: load only kept genes
    print(f"  Pass 2: loading kept genes ...", flush=True)
    genes: list[str] = []
    seen_genes: set[str] = set()
    study_data: dict[str, dict[str, list[float]]] = {
        sid: {col: [] for _, col in cols}
        for sid, cols in study_col_indices.items()
    }
    col_names: dict[str, list[str]] = {
        sid: [col for _, col in cols]
        for sid, cols in study_col_indices.items()
    }

    with gzip.open(path, "rt") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for row in reader:
            gene = clean_gene(row[0])
            if gene in seen_genes or gene not in kept_genes:
                continue
            seen_genes.add(gene)
            genes.append(gene)
            for study, col_idx_list in study_col_indices.items():
                for idx, col in col_idx_list:
                    try:
                        val = float(row[idx])
                    except (ValueError, IndexError):
                        val = 0.0
                    study_data[study][col].append(val)

    print(f"  {len(genes)} genes loaded after filtering")
    return genes, study_data, col_names


def write_study(study_id: str, genes: list[str],
                study_data: dict[str, list[float]],
                expr_col_names: list[str],
                sorted_samples: list[str],
                sorted_runs: list[str],
                run_to_sample: dict[str, str],
                out_dir: Path):
    """Write one per-study expression CSV to out_dir/<study_id>.csv."""

    n_expr = len(expr_col_names)
    n_samples = len(sorted_samples)
    n_runs = len(sorted_runs)

    if study_id in RUN_ALIGNED:
        # Map expr columns → runs positionally, then average per sample
        n_map = min(n_expr, n_runs)
        if n_expr != n_runs:
            print(f"  WARNING [{study_id}]: {n_expr} expr cols vs {n_runs} runs; mapping first {n_map}")
        run_to_col = {sorted_runs[i]: expr_col_names[i] for i in range(n_map)}

        # Accumulate values per sample
        sample_gene_vals: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for run, col in run_to_col.items():
            sample = run_to_sample.get(run)
            if sample is None:
                continue
            col_vals = study_data[col]
            for g, v in zip(genes, col_vals):
                sample_gene_vals[sample][g].append(v)

        rows: list[dict] = []
        for sample in sorted_samples:
            if sample not in sample_gene_vals:
                continue
            row = {"SampleAccession": sample}
            for g in genes:
                vals = sample_gene_vals[sample].get(g, [0.0])
                row[g] = sum(vals) / len(vals)
            rows.append(row)

    else:
        # Map expr columns → samples positionally (sorted SampleAccession order)
        n_map = min(n_expr, n_samples)
        if n_expr != n_samples:
            print(f"  WARNING [{study_id}]: {n_expr} expr cols vs {n_samples} samples; mapping first {n_map}")
        col_to_sample = {expr_col_names[i]: sorted_samples[i] for i in range(n_map)}

        rows: list[dict] = []
        for col in expr_col_names[:n_map]:
            sample = col_to_sample[col]
            col_vals = study_data[col]
            row = {"SampleAccession": sample}
            for g, v in zip(genes, col_vals):
                row[g] = v
            rows.append(row)

    if not rows:
        print(f"  SKIP [{study_id}]: no rows to write")
        return

    out_path = out_dir / f"{study_id}.csv"
    fieldnames = ["SampleAccession"] + genes
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Wrote {len(rows)} samples × {len(genes)} genes → {out_path.name}")


def main():
    if not RAW_TPM.exists():
        print(f"ERROR: {RAW_TPM} not found", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    study_samples, study_runs, run_to_sample = load_metadata()
    genes, study_data, col_names = read_expression_matrix(RAW_TPM)

    studies_in_expr = set(study_data.keys())
    print(f"\nStudies found in expression matrix: {sorted(studies_in_expr)}")

    for study_id in sorted(studies_in_expr):
        sorted_samples = study_samples.get(study_id, [])
        sorted_runs = study_runs.get(study_id, [])
        if not sorted_samples:
            print(f"  SKIP [{study_id}]: no metadata samples found")
            continue
        print(f"\n[{study_id}]  {len(col_names[study_id])} expr cols, "
              f"{len(sorted_samples)} samples, {len(sorted_runs)} runs")
        write_study(
            study_id, genes,
            study_data[study_id], col_names[study_id],
            sorted_samples, sorted_runs, run_to_sample,
            OUT_DIR,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
