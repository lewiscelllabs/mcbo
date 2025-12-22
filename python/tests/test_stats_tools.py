"""
Unit tests for MCBO agent statistical tools.
"""

import pytest
import pandas as pd
import numpy as np

from mcbo.agent.stats_tools import (
    compute_correlation,
    compute_fold_change,
    find_peak_conditions,
    filter_by_threshold,
    differential_expression,
    summarize_by_group,
    SCIPY_AVAILABLE,
)


class TestComputeCorrelation:
    """Tests for compute_correlation function."""
    
    def test_perfect_positive_correlation(self):
        """Test correlation of perfectly correlated data."""
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "y": [2, 4, 6, 8, 10],
        })
        result = compute_correlation(df, "x", "y")
        
        assert result["correlation"] is not None
        assert abs(result["correlation"] - 1.0) < 0.001
        assert result["n_samples"] == 5
        assert result["method"] == "pearson"
    
    def test_perfect_negative_correlation(self):
        """Test correlation of negatively correlated data."""
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "y": [10, 8, 6, 4, 2],
        })
        result = compute_correlation(df, "x", "y")
        
        assert result["correlation"] is not None
        assert abs(result["correlation"] - (-1.0)) < 0.001
    
    def test_no_correlation(self):
        """Test correlation of uncorrelated data."""
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "y": [5, 1, 4, 2, 3],  # Random-ish order
        })
        result = compute_correlation(df, "x", "y")
        
        assert result["correlation"] is not None
        # Should be close to 0 (but not exactly)
        assert abs(result["correlation"]) < 0.5
    
    def test_spearman_correlation(self):
        """Test Spearman correlation method."""
        df = pd.DataFrame({
            "x": [1, 2, 3, 4, 5],
            "y": [1, 4, 9, 16, 25],  # Non-linear but monotonic
        })
        result = compute_correlation(df, "x", "y", method="spearman")
        
        assert result["method"] == "spearman"
        assert result["correlation"] is not None
        # Spearman should show perfect rank correlation
        assert abs(result["correlation"] - 1.0) < 0.001
    
    def test_insufficient_samples(self):
        """Test handling of insufficient samples."""
        df = pd.DataFrame({
            "x": [1, 2],
            "y": [3, 4],
        })
        result = compute_correlation(df, "x", "y", min_samples=3)
        
        assert result["correlation"] is None
        assert "error" in result
        assert "Insufficient samples" in result["error"]
    
    def test_missing_values(self):
        """Test handling of missing values."""
        df = pd.DataFrame({
            "x": [1, 2, None, 4, 5],
            "y": [2, 4, 6, None, 10],
        })
        result = compute_correlation(df, "x", "y")
        
        # Should only use 3 complete rows
        assert result["n_samples"] == 3


class TestComputeFoldChange:
    """Tests for compute_fold_change function."""
    
    def test_basic_fold_change(self):
        """Test basic fold change calculation."""
        df = pd.DataFrame({
            "group": ["A", "A", "A", "B", "B", "B"],
            "value": [10, 12, 11, 5, 6, 4],
        })
        result = compute_fold_change(df, "group", "value", "A", "B")
        
        assert result["mean_group1"] is not None
        assert result["mean_group2"] is not None
        assert result["fold_change"] is not None
        assert result["n_group1"] == 3
        assert result["n_group2"] == 3
        # A mean ~11, B mean ~5, log2(11/5) ≈ 1.14
        assert result["log2"] == True
        assert result["fold_change"] > 0  # A > B
    
    def test_downregulated(self):
        """Test fold change for downregulation."""
        df = pd.DataFrame({
            "group": ["A", "A", "B", "B"],
            "value": [5, 5, 20, 20],
        })
        result = compute_fold_change(df, "group", "value", "A", "B")
        
        # A mean = 5, B mean = 20, log2(5/20) < 0
        assert result["fold_change"] < 0
    
    def test_empty_group(self):
        """Test handling of empty group."""
        df = pd.DataFrame({
            "group": ["A", "A"],
            "value": [10, 12],
        })
        result = compute_fold_change(df, "group", "value", "A", "B")
        
        assert result["fold_change"] is None
        assert "error" in result
    
    @pytest.mark.skipif(not SCIPY_AVAILABLE, reason="scipy not available")
    def test_pvalue_calculation(self):
        """Test p-value calculation with t-test."""
        df = pd.DataFrame({
            "group": ["A"] * 10 + ["B"] * 10,
            "value": [100 + np.random.randn() for _ in range(10)] + 
                     [50 + np.random.randn() for _ in range(10)],
        })
        result = compute_fold_change(df, "group", "value", "A", "B")
        
        assert result["p_value"] is not None
        # Should be highly significant
        assert result["p_value"] < 0.05
        assert result["significant"] == True


class TestFindPeakConditions:
    """Tests for find_peak_conditions function."""
    
    def test_single_condition(self):
        """Test finding peak with single condition column."""
        df = pd.DataFrame({
            "temperature": [37, 37, 37, 33, 33, 33],
            "productivity": [100, 110, 105, 60, 65, 55],
        })
        result = find_peak_conditions(df, ["temperature"], "productivity")
        
        assert result["overall_best"] is not None
        assert result["overall_best"]["temperature"] == 37
        assert len(result["top_conditions"]) <= 5
    
    def test_multiple_conditions(self):
        """Test finding peak with multiple condition columns."""
        df = pd.DataFrame({
            "temperature": [37, 37, 33, 33],
            "pH": [7.0, 7.2, 7.0, 7.2],
            "productivity": [100, 120, 60, 70],
        })
        result = find_peak_conditions(df, ["temperature", "pH"], "productivity")
        
        assert result["overall_best"] is not None
        # Best should be T=37, pH=7.2 with productivity 120
        assert result["overall_best"]["temperature"] == 37
        assert result["overall_best"]["pH"] == 7.2
    
    def test_aggregation_methods(self):
        """Test different aggregation methods."""
        df = pd.DataFrame({
            "condition": ["A", "A", "A", "B", "B"],
            "value": [10, 20, 15, 5, 100],  # B has one outlier
        })
        
        mean_result = find_peak_conditions(df, ["condition"], "value", method="mean")
        max_result = find_peak_conditions(df, ["condition"], "value", method="max")
        
        # Mean: A=15, B=52.5 -> B wins
        # Max: A=20, B=100 -> B wins
        assert mean_result["overall_best"]["condition"] == "B"
        assert max_result["overall_best"]["condition"] == "B"
    
    def test_empty_data(self):
        """Test handling of empty data."""
        df = pd.DataFrame({"condition": [], "value": []})
        result = find_peak_conditions(df, ["condition"], "value")
        
        assert result["top_conditions"] == []
        assert "error" in result


class TestFilterByThreshold:
    """Tests for filter_by_threshold function."""
    
    def test_greater_than(self):
        """Test > operator."""
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        result = filter_by_threshold(df, "x", ">", 3)
        assert len(result) == 2
        assert list(result["x"]) == [4, 5]
    
    def test_greater_equal(self):
        """Test >= operator."""
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        result = filter_by_threshold(df, "x", ">=", 3)
        assert len(result) == 3
    
    def test_less_than(self):
        """Test < operator."""
        df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        result = filter_by_threshold(df, "x", "<", 3)
        assert len(result) == 2
    
    def test_equals(self):
        """Test == operator."""
        df = pd.DataFrame({"x": [1, 2, 3, 3, 5]})
        result = filter_by_threshold(df, "x", "==", 3)
        assert len(result) == 2
    
    def test_invalid_column(self):
        """Test handling of invalid column."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        with pytest.raises(ValueError):
            filter_by_threshold(df, "y", ">", 1)


class TestDifferentialExpression:
    """Tests for differential_expression function."""
    
    def test_basic_de(self):
        """Test basic differential expression analysis."""
        df = pd.DataFrame({
            "gene": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "group": ["ctrl", "ctrl", "treat", "treat", "ctrl", "ctrl", "treat", "treat"],
            "expressionValue": [10, 12, 50, 55, 100, 110, 105, 95],
        })
        result = differential_expression(df, "group", "treat", "ctrl")
        
        assert len(result) == 2  # Two genes
        assert "gene" in result.columns
        assert "log2FoldChange" in result.columns
        assert "significant" in result.columns
    
    def test_upregulated_detection(self):
        """Test detection of upregulated genes."""
        df = pd.DataFrame({
            "gene": ["UP"] * 4,
            "group": ["ctrl", "ctrl", "treat", "treat"],
            "expressionValue": [10, 10, 40, 40],  # 4x increase
        })
        result = differential_expression(df, "group", "treat", "ctrl")
        
        # Should detect as upregulated
        up_gene = result[result["gene"] == "UP"].iloc[0]
        assert up_gene["log2FoldChange"] > 1.0  # log2(4) = 2
        if SCIPY_AVAILABLE:
            assert up_gene["direction"] == "up" or up_gene["significant"] == False
    
    def test_no_expression_data(self):
        """Test handling of no expression data."""
        df = pd.DataFrame({
            "gene": [],
            "group": [],
            "expressionValue": [],
        })
        result = differential_expression(df, "group", "treat", "ctrl")
        
        assert len(result) == 0


class TestSummarizeByGroup:
    """Tests for summarize_by_group function."""
    
    def test_basic_summary(self):
        """Test basic group summary."""
        df = pd.DataFrame({
            "group": ["A", "A", "A", "B", "B"],
            "value": [10, 20, 30, 5, 15],
        })
        result = summarize_by_group(df, "group", "value")
        
        assert len(result) == 2  # Two groups
        assert "mean" in result.columns
        assert "count" in result.columns
        
        a_row = result[result["group"] == "A"].iloc[0]
        assert a_row["mean"] == 20.0
        assert a_row["count"] == 3

