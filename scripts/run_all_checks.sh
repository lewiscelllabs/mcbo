#!/bin/bash
# Run all CQ evaluations and ROBOT QC checks for MCBO
#
# This script:
# 1. Verifies ontology parses correctly with rdflib
# 2. Runs ROBOT QC queries on the ontology
# 3. Builds and evaluates data.sample/ (demo data)
# 4. Builds and evaluates .data/ (real data, if present)
#    - Also runs verification and ROBOT QC on .data/graph.ttl
#
# Note: .data/ steps warn but don't fail if data is missing or has issues

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

if [ ! -f "$REPO_ROOT/python/run_eval.py" ]; then
    echo "Error: run_eval.py not found at $REPO_ROOT/python/run_eval.py"
    exit 1
fi

if [ ! -f "$REPO_ROOT/python/build_graph.py" ]; then
    echo "Error: build_graph.py not found at $REPO_ROOT/python/build_graph.py"
    exit 1
fi

# Create output directories
mkdir -p "$REPO_ROOT/reports/robot"
mkdir -p "$REPO_ROOT/eval/results"

# Helper function: Verify a TTL file parses using run_eval.py --verify
# Usage: verify_graph <file_path> <description>
# Returns: 0 if valid, 1 if invalid
verify_graph() {
    local file_path="$1"
    local description="$2"
    
    if [ ! -f "$file_path" ]; then
        echo "    ⚠️  WARNING: $description not found at $file_path"
        return 1
    fi
    
    local result
    result=$(python "$REPO_ROOT/python/run_eval.py" --graph "$file_path" --verify 2>&1)
    if [[ "$result" == PASS:* ]]; then
        echo "    ✅ $result ($description)"
        return 0
    else
        echo "    ⚠️  WARNING: $description - $result"
        return 1
    fi
}

# Helper function: Run ROBOT QC checks on a graph
# Usage: run_robot_qc <input_file> <output_dir> <description>
# Sets: LAST_QC_PASSED (true/false)
run_robot_qc() {
    local input_file="$1"
    local output_dir="$2"
    local description="$3"
    
    mkdir -p "$output_dir"
    LAST_QC_PASSED=true
    
    echo "    [1/3] Checking for orphan classes..."
    java -jar "$ROBOT_JAR" query \
        --input "$input_file" \
        --query "$REPO_ROOT/sparql/orphan_classes.rq" \
        "$output_dir/orphan_classes.tsv" 2>&1 | grep -v "WARNING:.*Unsafe" || true
    
    if [ -s "$output_dir/orphan_classes.tsv" ]; then
        local count=$(tail -n +2 "$output_dir/orphan_classes.tsv" | wc -l)
        if [ "$count" -gt 0 ]; then
            echo "      ⚠️  WARNING: Found $count orphan class(es)"
            LAST_QC_PASSED=false
        else
            echo "      ✅ PASS: No orphan classes"
        fi
    else
        echo "      ✅ PASS: No orphan classes"
    fi
    
    echo "    [2/3] Checking for duplicate labels..."
    java -jar "$ROBOT_JAR" query \
        --input "$input_file" \
        --query "$REPO_ROOT/sparql/duplicate_labels.rq" \
        "$output_dir/duplicate_labels.tsv" 2>&1 | grep -v "WARNING:.*Unsafe" || true
    
    if [ -s "$output_dir/duplicate_labels.tsv" ]; then
        local count=$(tail -n +2 "$output_dir/duplicate_labels.tsv" | wc -l)
        if [ "$count" -gt 0 ]; then
            echo "      ⚠️  WARNING: Found $count duplicate label(s)"
            LAST_QC_PASSED=false
        else
            echo "      ✅ PASS: No duplicate labels"
        fi
    else
        echo "      ✅ PASS: No duplicate labels"
    fi
    
    echo "    [3/3] Checking for missing definitions..."
    java -jar "$ROBOT_JAR" query \
        --input "$input_file" \
        --query "$REPO_ROOT/sparql/missing_definitions.rq" \
        "$output_dir/missing_definitions.tsv" 2>&1 | grep -v "WARNING:.*Unsafe" || true
    
    if [ -s "$output_dir/missing_definitions.tsv" ]; then
        local count=$(tail -n +2 "$output_dir/missing_definitions.tsv" | wc -l)
        if [ "$count" -gt 0 ]; then
            echo "      ⚠️  WARNING: Found $count class(es) missing definitions"
            LAST_QC_PASSED=false
        else
            echo "      ✅ PASS: All classes have definitions"
        fi
    else
        echo "      ✅ PASS: All classes have definitions"
    fi
    
    echo ""
    if [ "$LAST_QC_PASSED" = true ]; then
        echo "    ✅ All ROBOT QC checks PASSED ($description)"
    else
        echo "    ⚠️  Some ROBOT QC checks have warnings ($output_dir/)"
    fi
}

# Helper function: Process a dataset (build, verify, evaluate)
# Usage: process_dataset <data_dir> <name> <warn_only>
# Sets: LAST_DATASET_RAN, LAST_GRAPH_VALID, LAST_QC_PASSED
process_dataset() {
    local data_dir="$1"
    local name="$2"
    local warn_only="$3"  # "true" = warn on failure, "false" = fail on error
    
    LAST_DATASET_RAN=false
    LAST_GRAPH_VALID=false
    
    if [ ! -d "$data_dir" ]; then
        if [ "$warn_only" = "true" ]; then
            echo "  ℹ️  $data_dir/ directory not found (this is normal for public clones)"
        else
            echo "  ⚠️  $data_dir/ directory not found"
        fi
        return 1
    fi
    
    # Create output directories
    mkdir -p "$data_dir/processed"
    mkdir -p "$data_dir/results"
    
    local studies_dir=""
    local graph_file="$data_dir/graph.ttl"
    
    # Determine data structure
    if [ -d "$data_dir/studies" ]; then
        studies_dir="$data_dir/studies"
        local study_count=$(find "$studies_dir" -maxdepth 1 -type d ! -name "studies" 2>/dev/null | wc -l)
        if [ "$study_count" -eq 0 ]; then
            echo "  ⚠️  WARNING: No study directories found in $data_dir/studies/"
            return 1
        fi
        echo "  Building graph from: $studies_dir ($study_count studies)"
        
        if python "$REPO_ROOT/python/build_graph.py" build \
            --studies-dir "$studies_dir" \
            --ontology "$REPO_ROOT/ontology/mcbo.owl.ttl" \
            --instances "$data_dir/processed/mcbo_instances.ttl" \
            --output "$graph_file" 2>&1; then
            LAST_DATASET_RAN=true
        else
            echo "    ⚠️  WARNING: Failed to build graph"
            return 1
        fi
        
    elif [ -f "$data_dir/sample_metadata.csv" ]; then
        echo "  Found single metadata file: $data_dir/sample_metadata.csv"
        echo "  Converting directly with csv_to_rdf.py..."
        
        local expr_flag=""
        if [ -f "$data_dir/expression_matrix.csv" ]; then
            expr_flag="--expression_matrix $data_dir/expression_matrix.csv"
            echo "    + Expression matrix: $data_dir/expression_matrix.csv"
        fi
        
        if ! python "$REPO_ROOT/python/csv_to_rdf.py" \
            --csv_file "$data_dir/sample_metadata.csv" \
            --output_file "$data_dir/processed/mcbo_instances.ttl" \
            $expr_flag 2>&1; then
            echo "    ⚠️  WARNING: Failed to convert CSV to RDF"
            return 1
        fi
        echo ""
        
        echo "  Merging with ontology..."
        if python "$REPO_ROOT/python/build_graph.py" merge \
            --ontology "$REPO_ROOT/ontology/mcbo.owl.ttl" \
            --instances "$data_dir/processed/mcbo_instances.ttl" \
            --output "$graph_file" 2>&1; then
            LAST_DATASET_RAN=true
        else
            echo "    ⚠️  WARNING: Failed to merge graph"
            return 1
        fi
        
    elif [ -f "$data_dir/processed/mcbo_instances.ttl" ]; then
        echo "  Found pre-existing instances: $data_dir/processed/mcbo_instances.ttl"
        echo "  Merging with ontology..."
        if python "$REPO_ROOT/python/build_graph.py" merge \
            --ontology "$REPO_ROOT/ontology/mcbo.owl.ttl" \
            --instances "$data_dir/processed/mcbo_instances.ttl" \
            --output "$graph_file" 2>&1; then
            LAST_DATASET_RAN=true
        else
            echo "    ⚠️  WARNING: Failed to merge graph"
            return 1
        fi
    else
        echo "  ⚠️  WARNING: No data found in $data_dir/"
        echo "      Expected: studies/*, sample_metadata.csv, or processed/mcbo_instances.ttl"
        return 1
    fi
    
    echo ""
    
    # Verify graph
    echo "  Verifying graph..."
    if verify_graph "$graph_file" "$name graph"; then
        LAST_GRAPH_VALID=true
    fi
    echo ""
    
    # Evaluate
    echo "  Evaluating graph..."
    python "$REPO_ROOT/python/run_eval.py" \
        --graph "$graph_file" \
        --queries "$REPO_ROOT/eval/queries" \
        --results "$data_dir/results" || echo "    ⚠️  WARNING: Evaluation had issues"
    echo ""
    
    # Show results
    echo "  Results:"
    if [ -f "$data_dir/results/SUMMARY.txt" ]; then
        cat "$data_dir/results/SUMMARY.txt"
    fi
    echo ""
    
    # Generate stats
    python "$REPO_ROOT/python/stats_eval_graph.py" --graph "$graph_file" > "$data_dir/STATS.txt" 2>&1
    echo "  Stats written to: $data_dir/STATS.txt"
    
    return 0
}

echo "=========================================="
echo "Step 1: Verify ontology parses"
echo "=========================================="
echo ""

ONTOLOGY_FILE="$REPO_ROOT/ontology/mcbo.owl.ttl"
echo "  Verifying ontology parses..."
if verify_graph "$ONTOLOGY_FILE" "Ontology"; then
    ONTOLOGY_VALID=true
else
    ONTOLOGY_VALID=false
fi
echo ""

echo "=========================================="
echo "Step 2: Running ROBOT QC queries on ontology"
echo "=========================================="
echo ""

run_robot_qc "$ONTOLOGY_FILE" "$REPO_ROOT/reports/robot" "ontology"
QC_PASSED="$LAST_QC_PASSED"
echo ""

echo "=========================================="
echo "Step 3: Building and evaluating data.sample/ (demo data)"
echo "=========================================="
echo ""

if process_dataset "$REPO_ROOT/data.sample" "Demo" "false"; then
    DEMO_RAN="$LAST_DATASET_RAN"
    DEMO_GRAPH_VALID="$LAST_GRAPH_VALID"
else
    DEMO_RAN=false
    DEMO_GRAPH_VALID=false
fi

echo "=========================================="
echo "Step 4: Building and evaluating .data/ (real world data)"
echo "=========================================="
echo ""

if process_dataset "$REPO_ROOT/.data" "Real" "true"; then
    REAL_RAN="$LAST_DATASET_RAN"
    REAL_GRAPH_VALID="$LAST_GRAPH_VALID"
    
    # Run ROBOT QC on real data graph
    if [ "$REAL_RAN" = true ] && [ -f "$REPO_ROOT/.data/graph.ttl" ]; then
        echo ""
        echo "  ------------------------------------------"
        echo "  ROBOT QC for .data/graph.ttl"
        echo "  ------------------------------------------"
        echo ""
        run_robot_qc "$REPO_ROOT/.data/graph.ttl" "$REPO_ROOT/reports/robot/real_data" "real data"
        REAL_QC_PASSED="$LAST_QC_PASSED"
    fi
else
    REAL_RAN=false
    REAL_GRAPH_VALID=false
fi

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="

# Ontology Summary
if [ "$ONTOLOGY_VALID" = true ]; then
    echo "✅ Ontology: VALID"
else
    echo "❌ Ontology: INVALID"
fi

# QC Summary
if [ "$QC_PASSED" = true ]; then
    echo "✅ Ontology QC: PASSED"
else
    echo "⚠️  Ontology QC: WARNINGS (see reports/robot/)"
fi

# Demo data summary
if [ "$DEMO_RAN" = true ]; then
    echo "✅ Demo data (data.sample/): COMPLETED"
    if [ "${DEMO_GRAPH_VALID:-}" = true ]; then
        echo "   Graph: ✅ VALID"
    else
        echo "   Graph: ⚠️  WARNINGS"
    fi
else
    echo "⚠️  Demo data: SKIPPED"
fi

# Real data summary
if [ "$REAL_RAN" = true ]; then
    echo "✅ Real data (.data/): COMPLETED"
    if [ "${REAL_GRAPH_VALID:-}" = true ]; then
        echo "   Graph: ✅ VALID"
    else
        echo "   Graph: ⚠️  WARNINGS"
    fi
    if [ "${REAL_QC_PASSED:-}" = true ]; then
        echo "   QC: ✅ PASSED"
    elif [ "${REAL_QC_PASSED:-}" = false ]; then
        echo "   QC: ⚠️  WARNINGS (see reports/robot/real_data/)"
    fi
else
    echo "ℹ️  Real data: NOT AVAILABLE"
fi

echo ""
echo "All checks complete!"
