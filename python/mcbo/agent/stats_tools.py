"""
Statistical analysis tools for MCBO agent.

These functions perform statistical analyses on DataFrames returned by
SPARQL queries, enabling the agent to compute correlations, fold changes,
and identify optimal conditions.
"""

from typing import Literal, Optional, Union
import pandas as pd
import numpy as np

# Try to import scipy for statistical tests, fall back to basic stats if not available
try:
    from scipy import stats as scipy_stats
    from scipy.stats import pearsonr, spearmanr, ttest_ind, mannwhitneyu
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def compute_correlation(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    method: Literal["pearson", "spearman"] = "pearson",
    min_samples: int = 3,
) -> dict:
    """Compute correlation between two columns.
    
    Args:
        df: DataFrame with the data
        x_col: Name of the first column
        y_col: Name of the second column  
        method: Correlation method ('pearson' or 'spearman')
        min_samples: Minimum number of samples required
        
    Returns:
        dict with keys:
            - correlation: float, the correlation coefficient
            - p_value: float, significance p-value
            - n_samples: int, number of valid data points
            - method: str, the method used
            - significant: bool, whether p < 0.05
    """
    # Drop rows with missing values in either column
    valid_df = df[[x_col, y_col]].dropna()
    n = len(valid_df)
    
    if n < min_samples:
        return {
            "correlation": None,
            "p_value": None,
            "n_samples": n,
            "method": method,
            "significant": False,
            "error": f"Insufficient samples: {n} < {min_samples}",
        }
    
    x = valid_df[x_col].astype(float)
    y = valid_df[y_col].astype(float)
    
    if SCIPY_AVAILABLE:
        if method == "pearson":
            corr, p_val = pearsonr(x, y)
        else:
            corr, p_val = spearmanr(x, y)
    else:
        # Fallback to pandas correlation (no p-value)
        corr = x.corr(y, method=method)
        p_val = None
    
    return {
        "correlation": float(corr) if not np.isnan(corr) else None,
        "p_value": float(p_val) if p_val is not None and not np.isnan(p_val) else None,
        "n_samples": n,
        "method": method,
        "significant": p_val is not None and p_val < 0.05,
    }


def compute_fold_change(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    group1: str,
    group2: str,
    log2: bool = True,
    add_pseudocount: float = 1.0,
) -> dict:
    """Compute fold change between two groups.
    
    Args:
        df: DataFrame with the data
        group_col: Column containing group labels
        value_col: Column containing values to compare
        group1: Label for the first group (numerator) - partial match OK
        group2: Label for the second group (denominator) - partial match OK
        log2: If True, return log2 fold change
        add_pseudocount: Pseudocount to add before log (avoids log(0))
        
    Returns:
        dict with keys:
            - fold_change: float, the fold change (or log2 FC if log2=True)
            - mean_group1: float, mean of group 1
            - mean_group2: float, mean of group 2
            - n_group1: int, samples in group 1
            - n_group2: int, samples in group 2
            - p_value: float, t-test p-value (if scipy available)
            - significant: bool, whether p < 0.05
    """
    # Filter to each group - support partial matching for URIs
    g1_mask = df[group_col].astype(str).str.contains(group1, case=False, na=False)
    g2_mask = df[group_col].astype(str).str.contains(group2, case=False, na=False)
    g1_vals = df[g1_mask][value_col].dropna().astype(float)
    g2_vals = df[g2_mask][value_col].dropna().astype(float)
    
    n1, n2 = len(g1_vals), len(g2_vals)
    
    if n1 == 0 or n2 == 0:
        return {
            "fold_change": None,
            "mean_group1": g1_vals.mean() if n1 > 0 else None,
            "mean_group2": g2_vals.mean() if n2 > 0 else None,
            "n_group1": n1,
            "n_group2": n2,
            "p_value": None,
            "significant": False,
            "error": f"Empty group(s): group1={n1}, group2={n2}",
        }
    
    mean1 = g1_vals.mean()
    mean2 = g2_vals.mean()
    
    # Compute fold change
    if log2:
        fc = np.log2((mean1 + add_pseudocount) / (mean2 + add_pseudocount))
    else:
        fc = mean1 / mean2 if mean2 != 0 else float('inf')
    
    # Statistical test
    p_val = None
    if SCIPY_AVAILABLE and n1 >= 2 and n2 >= 2:
        try:
            _, p_val = ttest_ind(g1_vals, g2_vals, equal_var=False)
        except Exception:
            pass
    
    return {
        "fold_change": float(fc) if not np.isnan(fc) and not np.isinf(fc) else None,
        "log2": log2,
        "mean_group1": float(mean1),
        "mean_group2": float(mean2),
        "n_group1": n1,
        "n_group2": n2,
        "p_value": float(p_val) if p_val is not None and not np.isnan(p_val) else None,
        "significant": p_val is not None and p_val < 0.05,
    }


def find_peak_conditions(
    df: pd.DataFrame,
    condition_cols: list[str],
    metric_col: str,
    method: Literal["max", "mean", "median"] = "mean",
    top_n: int = 5,
) -> dict:
    """Find conditions associated with peak values of a metric.
    
    Args:
        df: DataFrame with condition and metric data
        condition_cols: List of columns representing conditions
        metric_col: Column containing the metric to optimize
        method: How to aggregate within condition groups
        top_n: Number of top condition combinations to return
        
    Returns:
        dict with keys:
            - top_conditions: list of dicts, each with condition values and metric
            - overall_best: dict with the single best condition combination
            - metric_stats: dict with overall metric statistics
    """
    # Drop rows with missing metric values
    valid_df = df.dropna(subset=[metric_col]).copy()
    valid_df[metric_col] = valid_df[metric_col].astype(float)
    
    if len(valid_df) == 0:
        return {
            "top_conditions": [],
            "overall_best": None,
            "metric_stats": None,
            "error": "No valid data",
        }
    
    # Identify which condition columns actually have data
    valid_condition_cols = [c for c in condition_cols if c in valid_df.columns and valid_df[c].notna().any()]
    
    if not valid_condition_cols:
        # No condition columns available, just return overall stats
        return {
            "top_conditions": [],
            "overall_best": None,
            "metric_stats": {
                "mean": float(valid_df[metric_col].mean()),
                "max": float(valid_df[metric_col].max()),
                "min": float(valid_df[metric_col].min()),
                "std": float(valid_df[metric_col].std()),
                "count": len(valid_df),
            },
            "note": "No condition columns with data",
        }
    
    # Group by conditions and aggregate
    agg_func = {"mean": "mean", "max": "max", "median": "median"}[method]
    grouped = valid_df.groupby(valid_condition_cols, dropna=False)[metric_col].agg([agg_func, "count"])
    grouped = grouped.reset_index()
    grouped = grouped.sort_values(agg_func, ascending=False)
    
    # Build top conditions list
    top_conditions = []
    for _, row in grouped.head(top_n).iterrows():
        condition = {col: row[col] for col in valid_condition_cols}
        condition[f"{metric_col}_{method}"] = float(row[agg_func])
        condition["sample_count"] = int(row["count"])
        top_conditions.append(condition)
    
    overall_best = top_conditions[0] if top_conditions else None
    
    return {
        "top_conditions": top_conditions,
        "overall_best": overall_best,
        "metric_stats": {
            "mean": float(valid_df[metric_col].mean()),
            "max": float(valid_df[metric_col].max()),
            "min": float(valid_df[metric_col].min()),
            "std": float(valid_df[metric_col].std()) if len(valid_df) > 1 else 0.0,
            "count": len(valid_df),
        },
        "method": method,
        "condition_columns": valid_condition_cols,
    }


def filter_by_threshold(
    df: pd.DataFrame,
    col: str,
    op: Literal[">", ">=", "<", "<=", "==", "!="],
    value: Union[float, int, str],
) -> pd.DataFrame:
    """Filter a DataFrame by a threshold condition.
    
    Args:
        df: DataFrame to filter
        col: Column to apply the condition to
        op: Comparison operator
        value: Threshold value
        
    Returns:
        Filtered DataFrame
    """
    if col not in df.columns:
        raise ValueError(f"Column '{col}' not found in DataFrame")
    
    # Try to convert to numeric if possible
    try:
        series = pd.to_numeric(df[col], errors='coerce')
        value = float(value)
    except (ValueError, TypeError):
        series = df[col]
    
    if op == ">":
        mask = series > value
    elif op == ">=":
        mask = series >= value
    elif op == "<":
        mask = series < value
    elif op == "<=":
        mask = series <= value
    elif op == "==":
        mask = series == value
    elif op == "!=":
        mask = series != value
    else:
        raise ValueError(f"Unknown operator: {op}")
    
    return df[mask].copy()


def differential_expression(
    df: pd.DataFrame,
    group_col: str,
    group1: str,
    group2: str,
    gene_col: str = "gene",
    value_col: str = "expressionValue",
    log2fc_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
    cell_line: str = None,
    cell_line_col: str = "cellLineLabel",
) -> pd.DataFrame:
    """Perform differential expression analysis between two groups.
    
    This is a simplified DESeq2-style analysis that computes log2 fold change
    and p-values for each gene.
    
    Args:
        df: DataFrame with gene expression data
        group_col: Column containing group labels
        group1: Label for condition/treatment group
        group2: Label for control/reference group
        gene_col: Column containing gene identifiers
        value_col: Column containing expression values
        log2fc_threshold: Minimum absolute log2 fold change for significance
        pvalue_threshold: Maximum p-value for significance
        cell_line: Optional cell line to filter by (partial match)
        cell_line_col: Column containing cell line labels
        
    Returns:
        DataFrame with columns:
            - gene: gene identifier
            - log2FoldChange: log2 fold change (group1 / group2)
            - pvalue: t-test p-value
            - significant: bool, meets both thresholds
            - direction: 'up' or 'down' if significant
    """
    # Filter by cell line if specified
    if cell_line and cell_line_col in df.columns:
        df = df[df[cell_line_col].str.contains(cell_line, case=False, na=False)]
    
    results = []
    
    # Get unique genes
    genes = df[gene_col].dropna().unique()
    
    for gene in genes:
        gene_data = df[df[gene_col] == gene]
        fc_result = compute_fold_change(
            gene_data, 
            group_col, 
            value_col, 
            group1, 
            group2,
            log2=True,
        )
        
        log2fc = fc_result.get("fold_change")
        pval = fc_result.get("p_value")
        
        # Check significance: require log2fc threshold
        # If p-value is available, also require it to be below threshold
        # If p-value is not available (small sample size), mark as "potential" based on fold change alone
        passes_fc = log2fc is not None and abs(log2fc) >= log2fc_threshold
        passes_pval = pval is not None and pval < pvalue_threshold
        no_pval_available = pval is None
        
        is_sig = passes_fc and (passes_pval or no_pval_available)
        
        direction = None
        if passes_fc:
            direction = "up" if log2fc > 0 else "down"
        
        results.append({
            "gene": gene,
            "log2FoldChange": log2fc,
            "mean_group1": fc_result.get("mean_group1"),
            "mean_group2": fc_result.get("mean_group2"),
            "n_group1": fc_result.get("n_group1"),
            "n_group2": fc_result.get("n_group2"),
            "pvalue": pval,
            "significant": is_sig,
            "direction": direction,
        })
    
    result_df = pd.DataFrame(results)
    
    # Sort by significance then by absolute fold change
    if not result_df.empty and "log2FoldChange" in result_df.columns:
        # Handle None values when computing abs
        result_df["abs_log2fc"] = result_df["log2FoldChange"].apply(
            lambda x: abs(x) if x is not None else 0
        )
        result_df = result_df.sort_values(
            ["significant", "abs_log2fc"], 
            ascending=[False, False]
        ).drop(columns=["abs_log2fc"])
    
    return result_df


def compute_correlation_matrix(
    df: pd.DataFrame,
    cols: list[str],
    method: Literal["pearson", "spearman"] = "pearson",
) -> pd.DataFrame:
    """Compute pairwise correlation matrix for multiple columns.
    
    Args:
        df: DataFrame with the data
        cols: List of column names to include
        method: Correlation method
        
    Returns:
        Correlation matrix as DataFrame
    """
    valid_cols = [c for c in cols if c in df.columns]
    if len(valid_cols) < 2:
        raise ValueError("Need at least 2 valid columns for correlation matrix")
    
    numeric_df = df[valid_cols].apply(pd.to_numeric, errors='coerce')
    return numeric_df.corr(method=method)


def summarize_by_group(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    agg_funcs: list[str] = None,
) -> pd.DataFrame:
    """Summarize a value column by group.
    
    Args:
        df: DataFrame with the data
        group_col: Column to group by
        value_col: Column to summarize
        agg_funcs: List of aggregation functions (default: mean, std, count, min, max)
        
    Returns:
        Summary DataFrame with group statistics
    """
    if agg_funcs is None:
        agg_funcs = ["mean", "std", "count", "min", "max"]
    
    valid_df = df[[group_col, value_col]].dropna()
    valid_df[value_col] = pd.to_numeric(valid_df[value_col], errors='coerce')
    
    return valid_df.groupby(group_col)[value_col].agg(agg_funcs).reset_index()


__all__ = [
    "compute_correlation",
    "compute_fold_change",
    "find_peak_conditions",
    "filter_by_threshold",
    "differential_expression",
    "compute_correlation_matrix",
    "summarize_by_group",
    "SCIPY_AVAILABLE",
]

