#!/bin/bash
# Run all CQ evaluations and ROBOT QC checks for MCBO
#
# This script:
# 1. Runs ROBOT QC queries on the ontology
# 2. Builds and evaluates data.sample/ (demo data)
# 3. Builds and evaluates .data/ (real data, if present)

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "MCBO: Running all CQ and QC checks"
echo "=========================================="
echo ""

# Activate conda environment if available
if command -v conda &> /dev/null; then
    echo "Activating conda environment 'mcbo'..."
    eval "$(conda shell.bash hook)"
    conda activate mcbo || echo "Warning: Could not activate conda environment 'mcbo'"
    echo ""
fi

# Check for ROBOT
ROBOT_JAR="$REPO_ROOT/.robot/robot.jar"
if [ ! -f "$ROBOT_JAR" ]; then
    echo "Error: ROBOT jar not found at $ROBOT_JAR"
    exit 1
fi

# Check for Python and required scripts
if ! command -v python &> /dev/null; then
    echo "Error: python not found in PATH"
    exit 1
fi

if [ ! -f "$REPO_ROOT/run_eval.py" ]; then
    echo "Error: run_eval.py not found at $REPO_ROOT/run_eval.py"
    exit 1
fi

if [ ! -f "$REPO_ROOT/scripts/build_graph.py" ]; then
    echo "Error: build_graph.py not found at $REPO_ROOT/scripts/build_graph.py"
    exit 1
fi

# Create output directories
mkdir -p "$REPO_ROOT/reports/robot"
mkdir -p "$REPO_ROOT/eval/results"

echo "=========================================="
echo "Step 1: Running ROBOT QC queries"
echo "=========================================="
echo ""

QC_PASSED=true

# Run orphan classes check
echo "  [1/3] Checking for orphan classes..."
java -jar "$ROBOT_JAR" query \
    --input "$REPO_ROOT/ontology/mcbo.owl.ttl" \
    --query "$REPO_ROOT/sparql/orphan_classes.rq" \
    "$REPO_ROOT/reports/robot/orphan_classes.tsv" 2>&1 | grep -v "WARNING:.*Unsafe" || true

if [ -s "$REPO_ROOT/reports/robot/orphan_classes.tsv" ]; then
    ORPHAN_COUNT=$(tail -n +2 "$REPO_ROOT/reports/robot/orphan_classes.tsv" | wc -l)
    if [ "$ORPHAN_COUNT" -gt 0 ]; then
        echo "    ⚠️  WARNING: Found $ORPHAN_COUNT orphan class(es)"
        QC_PASSED=false
    else
        echo "    ✅ PASS: No orphan classes"
    fi
else
    echo "    ✅ PASS: No orphan classes"
fi

# Run duplicate labels check
echo "  [2/3] Checking for duplicate labels..."
java -jar "$ROBOT_JAR" query \
    --input "$REPO_ROOT/ontology/mcbo.owl.ttl" \
    --query "$REPO_ROOT/sparql/duplicate_labels.rq" \
    "$REPO_ROOT/reports/robot/duplicate_labels.tsv" 2>&1 | grep -v "WARNING:.*Unsafe" || true

if [ -s "$REPO_ROOT/reports/robot/duplicate_labels.tsv" ]; then
    DUP_COUNT=$(tail -n +2 "$REPO_ROOT/reports/robot/duplicate_labels.tsv" | wc -l)
    if [ "$DUP_COUNT" -gt 0 ]; then
        echo "    ⚠️  WARNING: Found $DUP_COUNT duplicate label(s)"
        QC_PASSED=false
    else
        echo "    ✅ PASS: No duplicate labels"
    fi
else
    echo "    ✅ PASS: No duplicate labels"
fi

# Run missing definitions check
echo "  [3/3] Checking for missing definitions..."
java -jar "$ROBOT_JAR" query \
    --input "$REPO_ROOT/ontology/mcbo.owl.ttl" \
    --query "$REPO_ROOT/sparql/missing_definitions.rq" \
    "$REPO_ROOT/reports/robot/missing_definitions.tsv" 2>&1 | grep -v "WARNING:.*Unsafe" || true

if [ -s "$REPO_ROOT/reports/robot/missing_definitions.tsv" ]; then
    MISSING_COUNT=$(tail -n +2 "$REPO_ROOT/reports/robot/missing_definitions.tsv" | wc -l)
    if [ "$MISSING_COUNT" -gt 0 ]; then
        echo "    ⚠️  WARNING: Found $MISSING_COUNT class(es) missing definitions"
        QC_PASSED=false
    else
        echo "    ✅ PASS: All classes have definitions"
    fi
else
    echo "    ✅ PASS: All classes have definitions"
fi

echo ""
if [ "$QC_PASSED" = true ]; then
    echo "✅ All ROBOT QC checks PASSED"
else
    echo "⚠️  Some ROBOT QC checks have warnings (see reports/robot/)"
fi
echo ""

echo "=========================================="
echo "Step 2: Building and evaluating data.sample/ (demo data)"
echo "=========================================="
echo ""

DEMO_RAN=false

# Check for demo data
if [ -d "$REPO_ROOT/data.sample" ]; then
    # Create output directories
    mkdir -p "$REPO_ROOT/data.sample/processed"
    mkdir -p "$REPO_ROOT/data.sample/results"
    
    # Determine if we have a studies/ subdirectory or direct study folders
    if [ -d "$REPO_ROOT/data.sample/studies" ]; then
        DEMO_STUDIES_DIR="$REPO_ROOT/data.sample/studies"
    else
        # Check for study_* directories directly in data.sample/
        STUDY_COUNT=$(find "$REPO_ROOT/data.sample" -maxdepth 1 -type d -name "study_*" 2>/dev/null | wc -l)
        if [ "$STUDY_COUNT" -gt 0 ]; then
            DEMO_STUDIES_DIR="$REPO_ROOT/data.sample"
        else
            DEMO_STUDIES_DIR=""
        fi
    fi
    
    if [ -n "$DEMO_STUDIES_DIR" ] && [ -d "$DEMO_STUDIES_DIR" ]; then
        echo "  Building demo graph from: $DEMO_STUDIES_DIR"
        python "$REPO_ROOT/scripts/build_graph.py" build \
            --studies-dir "$DEMO_STUDIES_DIR" \
            --ontology "$REPO_ROOT/ontology/mcbo.owl.ttl" \
            --instances "$REPO_ROOT/data.sample/processed/mcbo_instances.ttl" \
            --output "$REPO_ROOT/data.sample/graph.ttl"
        echo ""
        
        echo "  Evaluating demo graph..."
        python "$REPO_ROOT/run_eval.py" \
            --graph "$REPO_ROOT/data.sample/graph.ttl" \
            --queries "$REPO_ROOT/eval/queries" \
            --results "$REPO_ROOT/data.sample/results"
        DEMO_RAN=true
        echo ""
        echo "  Demo data results:"
        if [ -f "$REPO_ROOT/data.sample/results/SUMMARY.txt" ]; then
            cat "$REPO_ROOT/data.sample/results/SUMMARY.txt"
        fi
        echo ""
    else
        echo "  ⚠️  No study directories found in data.sample/"
    fi
else
    echo "  ⚠️  data.sample/ directory not found"
fi

echo "=========================================="
echo "Step 3: Building and evaluating .data/ (real data)"
echo "=========================================="
echo ""

REAL_RAN=false

# Check for real data
if [ -d "$REPO_ROOT/.data" ]; then
    # Create output directories
    mkdir -p "$REPO_ROOT/.data/processed"
    mkdir -p "$REPO_ROOT/.data/results"
    
    # Determine data structure
    if [ -d "$REPO_ROOT/.data/studies" ]; then
        # studies/ subdirectory exists
        REAL_STUDIES_DIR="$REPO_ROOT/.data/studies"
        STUDY_COUNT=$(find "$REAL_STUDIES_DIR" -maxdepth 1 -type d ! -name "studies" 2>/dev/null | wc -l)
        
        if [ "$STUDY_COUNT" -gt 0 ]; then
            echo "  Building real graph from: $REAL_STUDIES_DIR ($STUDY_COUNT studies)"
            python "$REPO_ROOT/scripts/build_graph.py" build \
                --studies-dir "$REAL_STUDIES_DIR" \
                --ontology "$REPO_ROOT/ontology/mcbo.owl.ttl" \
                --instances "$REPO_ROOT/.data/processed/mcbo_instances.ttl" \
                --output "$REPO_ROOT/.data/graph.ttl"
            echo ""
            
            echo "  Evaluating real graph..."
            python "$REPO_ROOT/run_eval.py" \
                --graph "$REPO_ROOT/.data/graph.ttl" \
                --queries "$REPO_ROOT/eval/queries" \
                --results "$REPO_ROOT/.data/results"
            REAL_RAN=true
            echo ""
            echo "  Real data results:"
            if [ -f "$REPO_ROOT/.data/results/SUMMARY.txt" ]; then
                cat "$REPO_ROOT/.data/results/SUMMARY.txt"
            fi
            echo ""
        else
            echo "  ⚠️  No study directories found in .data/studies/"
        fi
    elif [ -f "$REPO_ROOT/.data/sample_metadata.csv" ]; then
        # Single CSV file at root level
        echo "  Found single metadata file: .data/sample_metadata.csv"
        echo "  Converting directly with csv_to_rdf.py..."
        
        # Check for expression matrix
        EXPR_FLAG=""
        if [ -f "$REPO_ROOT/.data/expression_matrix.csv" ]; then
            EXPR_FLAG="--expression_matrix $REPO_ROOT/.data/expression_matrix.csv"
            echo "    + Expression matrix: .data/expression_matrix.csv"
        fi
        
        python "$REPO_ROOT/src/csv_to_rdf.py" \
            --csv_file "$REPO_ROOT/.data/sample_metadata.csv" \
            --output_file "$REPO_ROOT/.data/processed/mcbo_instances.ttl" \
            $EXPR_FLAG
        echo ""
        
        echo "  Merging with ontology..."
        python "$REPO_ROOT/scripts/build_graph.py" merge \
            --ontology "$REPO_ROOT/ontology/mcbo.owl.ttl" \
            --instances "$REPO_ROOT/.data/processed/mcbo_instances.ttl" \
            --output "$REPO_ROOT/.data/graph.ttl"
        echo ""
        
        echo "  Evaluating real graph..."
        python "$REPO_ROOT/run_eval.py" \
            --graph "$REPO_ROOT/.data/graph.ttl" \
            --queries "$REPO_ROOT/eval/queries" \
            --results "$REPO_ROOT/.data/results"
        REAL_RAN=true
        echo ""
        echo "  Real data results:"
        if [ -f "$REPO_ROOT/.data/results/SUMMARY.txt" ]; then
            cat "$REPO_ROOT/.data/results/SUMMARY.txt"
        fi
        echo ""
    elif [ -f "$REPO_ROOT/.data/processed/mcbo_instances.ttl" ]; then
        # Pre-existing instances file
        echo "  Found pre-existing instances: .data/processed/mcbo_instances.ttl"
        echo "  Merging with ontology..."
        python "$REPO_ROOT/scripts/build_graph.py" merge \
            --ontology "$REPO_ROOT/ontology/mcbo.owl.ttl" \
            --instances "$REPO_ROOT/.data/processed/mcbo_instances.ttl" \
            --output "$REPO_ROOT/.data/graph.ttl"
        echo ""
        
        echo "  Evaluating real graph..."
        python "$REPO_ROOT/run_eval.py" \
            --graph "$REPO_ROOT/.data/graph.ttl" \
            --queries "$REPO_ROOT/eval/queries" \
            --results "$REPO_ROOT/.data/results"
        REAL_RAN=true
        echo ""
        echo "  Real data results:"
        if [ -f "$REPO_ROOT/.data/results/SUMMARY.txt" ]; then
            cat "$REPO_ROOT/.data/results/SUMMARY.txt"
        fi
        echo ""
    else
        echo "  ⚠️  No data found in .data/"
        echo "      Expected: .data/studies/*, .data/sample_metadata.csv, or .data/processed/mcbo_instances.ttl"
    fi
else
    echo "  ℹ️  .data/ directory not found (this is normal for public clones)"
    echo "      To add real data, create .data/studies/<study_name>/sample_metadata.csv"
fi

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="

# QC Summary
if [ "$QC_PASSED" = true ]; then
    echo "✅ QC: PASSED"
else
    echo "⚠️  QC: WARNINGS (see reports/robot/)"
fi

# Demo data summary
if [ "$DEMO_RAN" = true ]; then
    echo "✅ Demo data (data.sample/): COMPLETED"
    echo "   Results: data.sample/results/"
    # Generate stats
    if [ -f "$REPO_ROOT/data.sample/graph.ttl" ]; then
        python "$REPO_ROOT/scripts/stats_eval_graph.py" --graph "$REPO_ROOT/data.sample/graph.ttl" > "$REPO_ROOT/data.sample/STATS.txt" 2>&1
        echo "   Stats: data.sample/STATS.txt"
    fi
else
    echo "⚠️  Demo data: SKIPPED"
fi

# Real data summary
if [ "$REAL_RAN" = true ]; then
    echo "✅ Real data (.data/): COMPLETED"
    echo "   Results: .data/results/"
    # Generate stats
    if [ -f "$REPO_ROOT/.data/graph.ttl" ]; then
        python "$REPO_ROOT/scripts/stats_eval_graph.py" --graph "$REPO_ROOT/.data/graph.ttl" > "$REPO_ROOT/.data/STATS.txt" 2>&1
        echo "   Stats: .data/STATS.txt"
    fi
else
    echo "ℹ️  Real data: NOT AVAILABLE"
fi

echo ""
echo "All checks complete!"
