"""
plot_cq6.py — Gene-productivity correlation plots for CHO RNA-seq data.

Plots produced:
  1. Volcano: x=mean TPM (log10), y=Pearson r, highlights |r|>0.7
  2. Bar chart: top 20 positively and negatively correlated genes
  3. Scatter: Glul TPM vs Productivity, coloured by CellLine

Productivity (categorical: Low/LowMedium/Medium/High/VeryHigh) is encoded
ordinally (1-5) before computing Pearson r.
"""

import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from matplotlib.lines import Line2D

# ── paths ────────────────────────────────────────────────────────────────────
BASE = "/mnt/c/Users/kroba/Documents/dropZone/uga/uga-repos/mcbo"
EXPR_GLOB = os.path.join(BASE, ".data/expression/study_*.csv")
META_CSV  = os.path.join(BASE, ".data/sample_metadata.csv")
FIG_DIR   = os.path.join(BASE, ".data/figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── ordinal encoding for Productivity ────────────────────────────────────────
PROD_ORDER = {"Low": 1, "LowMedium": 2, "Medium": 3, "High": 4, "VeryHigh": 5}

# ── 1. load & merge ──────────────────────────────────────────────────────────
print("Loading expression matrices …")
expr_parts = []
for f in sorted(glob.glob(EXPR_GLOB)):
    expr_parts.append(pd.read_csv(f, index_col=0))
expr_all = pd.concat(expr_parts, axis=0)
print(f"  Combined expression: {expr_all.shape[0]} samples × {expr_all.shape[1]} genes")

print("Loading metadata …")
meta = pd.read_csv(META_CSV)
meta_sub = meta[["SampleAccession", "Productivity", "ProcessType",
                  "CulturePhase", "CellLine", "StudyID"]].copy()
meta_sub = meta_sub.set_index("SampleAccession")

print("Merging …")
merged = expr_all.join(meta_sub, how="inner")
print(f"  After inner join: {len(merged)} samples")

# ── 2. filter to samples with numeric Productivity ───────────────────────────
merged["Prod_num"] = merged["Productivity"].map(PROD_ORDER)
merged = merged.dropna(subset=["Prod_num"])
print(f"  After Productivity filter: {len(merged)} samples")
print(f"  Productivity distribution:\n{merged['Productivity'].value_counts().to_string()}")

# separate gene columns from metadata columns
meta_cols = {"Productivity", "ProcessType", "CulturePhase",
             "CellLine", "StudyID", "Prod_num"}
gene_cols = [c for c in merged.columns if c not in meta_cols]

expr_mat   = merged[gene_cols].astype(float)
prod_vec   = merged["Prod_num"].astype(float)

# ── 3. compute per-gene Pearson r & mean TPM ─────────────────────────────────
print("Computing correlations …")
n_genes = len(gene_cols)
r_vals   = np.empty(n_genes)
p_vals   = np.empty(n_genes)
mean_tpm = expr_mat.mean(axis=0).values

for i, gene in enumerate(gene_cols):
    tpm = expr_mat[gene].values
    if np.std(tpm) == 0:
        r_vals[i] = np.nan
        p_vals[i] = np.nan
    else:
        r, p = stats.pearsonr(tpm, prod_vec)
        r_vals[i] = r
        p_vals[i] = p

corr_df = pd.DataFrame({
    "gene":     gene_cols,
    "r":        r_vals,
    "p":        p_vals,
    "mean_tpm": mean_tpm,
}).dropna(subset=["r"])

print(f"  Valid correlations: {len(corr_df)}")
print(f"  |r|>0.7 count: {(corr_df['r'].abs() > 0.7).sum()}")

# ── PLOT 1 : Volcano ──────────────────────────────────────────────────────────
print("Plotting volcano …")

R_THRESH = 0.5
HIGH_R = corr_df["r"].abs() > R_THRESH
log10_mean = np.log10(corr_df["mean_tpm"].clip(lower=1e-3))

fig, ax = plt.subplots(figsize=(10, 7))

# background (|r| ≤ threshold)
ax.scatter(
    log10_mean[~HIGH_R], corr_df.loc[~HIGH_R, "r"],
    s=15, alpha=0.35, color="steelblue", linewidths=0, label=f"|r| ≤ {R_THRESH}"
)
# highlighted (|r| > threshold)
ax.scatter(
    log10_mean[HIGH_R], corr_df.loc[HIGH_R, "r"],
    s=30, alpha=0.8, color="crimson", linewidths=0, label=f"|r| > {R_THRESH}"
)

# label top 15 by |r|
top15 = corr_df.reindex(corr_df["r"].abs().nlargest(15).index)
for _, row in top15.iterrows():
    ax.annotate(
        row["gene"],
        xy=(np.log10(max(row["mean_tpm"], 1e-3)), row["r"]),
        xytext=(4, 2), textcoords="offset points",
        fontsize=7, color="black",
        arrowprops=dict(arrowstyle="-", color="grey", lw=0.5),
    )

ax.axhline(0, color="black", lw=0.8, ls="--")
ax.axhline( R_THRESH, color="crimson", lw=0.7, ls=":", alpha=0.6)
ax.axhline(-R_THRESH, color="crimson", lw=0.7, ls=":", alpha=0.6)
ax.set_xlabel("Mean TPM (log₁₀)", fontsize=12)
ax.set_ylabel("Pearson r (gene TPM vs Productivity)", fontsize=12)
ax.set_title("Gene–Productivity Correlation Volcano\n(CHO RNA-seq, ordinal Productivity)", fontsize=13)
ax.legend(fontsize=10, framealpha=0.8)
sns.despine(ax=ax)

out1 = os.path.join(FIG_DIR, "cq6_volcano.png")
fig.tight_layout()
fig.savefig(out1, dpi=300)
plt.close(fig)
print(f"  Saved: {out1}")

# ── PLOT 2 : Horizontal bar — top 20 positive + top 20 negative ──────────────
print("Plotting top-genes bar chart …")

top_pos = corr_df.nlargest(20, "r")[["gene", "r"]].copy()
top_neg = corr_df.nsmallest(20, "r")[["gene", "r"]].copy()
bar_df  = pd.concat([top_pos, top_neg]).sort_values("r")

colors = ["#d73027" if r < 0 else "#1a9850" for r in bar_df["r"]]

fig, ax = plt.subplots(figsize=(9, 12))
bars = ax.barh(bar_df["gene"], bar_df["r"], color=colors, edgecolor="none")
ax.axvline(0, color="black", lw=0.8)
ax.set_xlabel("Pearson r", fontsize=12)
ax.set_title("Top 20 Positively & Negatively Correlated Genes\n(gene TPM vs ordinal Productivity)", fontsize=13)

legend_elements = [
    Line2D([0], [0], marker="s", color="w", markerfacecolor="#1a9850",
           markersize=10, label="Positive (r > 0)"),
    Line2D([0], [0], marker="s", color="w", markerfacecolor="#d73027",
           markersize=10, label="Negative (r < 0)"),
]
ax.legend(handles=legend_elements, fontsize=10, loc="lower right")
sns.despine(ax=ax)

out2 = os.path.join(FIG_DIR, "cq6_top_genes.png")
fig.tight_layout()
fig.savefig(out2, dpi=300)
plt.close(fig)
print(f"  Saved: {out2}")

# ── PLOT 3 : Glul scatter ─────────────────────────────────────────────────────
print("Plotting Glul scatter …")

GENE = "Glul"
if GENE not in expr_mat.columns:
    print(f"  WARNING: {GENE} not found in expression matrix. Skipping plot 3.")
else:
    glul_df = pd.DataFrame({
        "Productivity_num": prod_vec,
        "Productivity":     merged["Productivity"],
        "TPM":              expr_mat[GENE],
        "CellLine":         merged["CellLine"],
    })

    cell_lines = sorted(glul_df["CellLine"].dropna().unique())
    palette = sns.color_palette("tab10", n_colors=len(cell_lines))
    cl_color = dict(zip(cell_lines, palette))

    fig, ax = plt.subplots(figsize=(8, 6))

    for cl, grp in glul_df.groupby("CellLine"):
        ax.scatter(
            grp["Productivity_num"], grp["TPM"],
            s=45, alpha=0.7, color=cl_color[cl], label=cl, linewidths=0
        )

    # regression line across all points
    x_all = glul_df["Productivity_num"].values
    y_all = glul_df["TPM"].values
    slope, intercept, r_reg, p_reg, _ = stats.linregress(x_all, y_all)
    x_line = np.linspace(x_all.min(), x_all.max(), 200)
    ax.plot(x_line, slope * x_line + intercept, color="black", lw=1.5,
            ls="--", label=f"Regression (r={r_reg:.3f})")

    # annotate r
    ax.text(0.97, 0.04,
            f"r = {r_reg:.3f}  (p = {p_reg:.2e})",
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=11, bbox=dict(boxstyle="round,pad=0.3",
                                   facecolor="white", alpha=0.8))

    # x-axis ticks → ordinal labels
    tick_map = {v: k for k, v in PROD_ORDER.items()}
    ax.set_xticks(sorted(tick_map))
    ax.set_xticklabels([tick_map[t] for t in sorted(tick_map)], rotation=20)

    ax.set_xlabel("Productivity (ordinal)", fontsize=12)
    ax.set_ylabel("Glul TPM", fontsize=12)
    ax.set_title("Glul Expression vs Productivity\n(coloured by CellLine)", fontsize=13)
    ax.legend(title="CellLine", fontsize=9, title_fontsize=10, framealpha=0.8)
    sns.despine(ax=ax)

    out3 = os.path.join(FIG_DIR, "cq6_glul.png")
    fig.tight_layout()
    fig.savefig(out3, dpi=300)
    plt.close(fig)
    print(f"  Saved: {out3}")

print("\nDone.")
