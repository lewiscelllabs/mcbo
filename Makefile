# MCBO Makefile
# Build graphs, run evaluations, and quality control checks
#
# Usage:
#   make demo         # Build and evaluate demo data (data.sample/)
#   make real         # Build and evaluate real data (.data/)
#   make qc           # Run ROBOT QC checks on ontology
#   make all          # Run demo + qc (default)
#   make clean        # Remove generated files
#   make help         # Show this help
#
# Prerequisites:
#   - Conda environment: make conda-env && conda activate mcbo
#   - Python package installed: make install
#   - ROBOT jar at .robot/robot.jar (for QC checks)

.PHONY: all demo real qc clean help install robot verify-demo verify-real stats-demo stats-real conda-env check-env docs docs-clean

# Configuration
PYTHON := python
ROBOT_JAR := .robot/robot.jar
ONTOLOGY := ontology/mcbo.owl.ttl
SPARQL_DIR := sparql
REPORTS_DIR := reports/robot

# Conda detection
CONDA := $(shell command -v conda 2>/dev/null)
MCBO_ENV_ACTIVE := $(shell [ "$$CONDA_DEFAULT_ENV" = "mcbo" ] && echo 1 || echo 0)

# Demo data paths
DEMO_DIR := data.sample
DEMO_GRAPH := $(DEMO_DIR)/graph.ttl
DEMO_INSTANCES := $(DEMO_DIR)/mcbo-instances.ttl
DEMO_RESULTS := $(DEMO_DIR)/results

# Real data paths
REAL_DIR := .data
REAL_GRAPH := $(REAL_DIR)/graph.ttl
REAL_INSTANCES := $(REAL_DIR)/mcbo-instances.ttl
REAL_RESULTS := $(REAL_DIR)/results

# Default target
all: demo qc

help:
	@echo "MCBO Build System"
	@echo ""
	@echo "First-time setup:"
	@echo "  make conda-env    Create mcbo conda environment"
	@echo "  conda activate mcbo"
	@echo "  make install      Install dependencies and mcbo package"
	@echo ""
	@echo "Usage:"
	@echo "  make demo         Build and evaluate demo data (data.sample/)"
	@echo "  make real         Build and evaluate real data (.data/)"
	@echo "  make qc           Run ROBOT QC checks on ontology"
	@echo "  make all          Run demo + qc (default)"
	@echo "  make clean        Remove generated files"
	@echo "  make robot        Download ROBOT jar"
	@echo ""
	@echo "Individual targets:"
	@echo "  make demo-build   Build demo graph only"
	@echo "  make demo-eval    Run CQ evaluation on demo data"
	@echo "  make demo-stats   Show demo data statistics"
	@echo "  make verify-demo  Verify demo graph parses"
	@echo "  make docs         Build Sphinx documentation"
	@echo "  make docs-clean   Clean documentation build"
	@echo ""
	@echo "Configuration by convention:"
	@echo "  Graph files:     <data-dir>/graph.ttl"
	@echo "  Instances:       <data-dir>/mcbo-instances.ttl"
	@echo "  Results:         <data-dir>/results/"
	@echo "  Ontology:        ontology/mcbo.owl.ttl"

# =============================================================================
# Environment Setup
# =============================================================================

conda-env:
ifndef CONDA
	@echo "❌ Conda not found"
	@echo ""
	@echo "Please install Conda (Miniconda recommended):"
	@echo "  https://docs.conda.io/en/latest/miniconda.html"
	@echo ""
	@echo "Quick install (Linux):"
	@echo "  wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
	@echo "  bash Miniconda3-latest-Linux-x86_64.sh"
	@echo ""
	@echo "Quick install (macOS):"
	@echo "  brew install miniconda"
	@echo ""
	@exit 1
else
	@if conda env list | grep -q "^mcbo "; then \
		echo "ℹ️  Conda environment 'mcbo' already exists"; \
		echo "   To recreate: conda env remove -n mcbo && make conda-env"; \
	else \
		echo "Creating mcbo conda environment..."; \
		conda create -n mcbo python=3.10 -y; \
		echo ""; \
		echo "✅ Environment created!"; \
	fi
	@# Add CONDA_DEFAULT_ENV to .env if not present (for IDE integration)
	@if [ -f .env ]; then \
		grep -q "^CONDA_DEFAULT_ENV=mcbo$$" .env || echo "CONDA_DEFAULT_ENV=mcbo" >> .env; \
	else \
		echo "CONDA_DEFAULT_ENV=mcbo" > .env; \
	fi
	@echo ""
	@echo "Next steps:"
	@echo "  conda activate mcbo"
	@echo "  make install"
endif

check-env:
	@if [ "$(MCBO_ENV_ACTIVE)" != "1" ]; then \
		echo "⚠️  Warning: mcbo conda environment is not active"; \
		echo "   Run: conda activate mcbo"; \
		echo ""; \
	fi

# Installation (requires active conda environment)
install: check-env
	pip install -r requirements.txt
	pip install -e python/
	@echo ""
	@echo "✅ mcbo package installed"

robot: $(ROBOT_JAR)

$(ROBOT_JAR):
	@echo "Downloading ROBOT..."
	@mkdir -p .robot
	curl -L -o $(ROBOT_JAR) "https://github.com/ontodev/robot/releases/download/v1.9.6/robot.jar"

# =============================================================================
# Demo Data Targets
# =============================================================================

demo: check-env demo-build demo-eval demo-stats
	@echo ""
	@echo "✅ Demo data processing complete"
	@echo "   Graph: $(DEMO_GRAPH)"
	@echo "   Results: $(DEMO_RESULTS)/"

demo-build: $(DEMO_GRAPH)

$(DEMO_GRAPH): $(ONTOLOGY) $(wildcard $(DEMO_DIR)/studies/*/sample_metadata.csv) $(wildcard $(DEMO_DIR)/sample_metadata.csv)
	@echo "Building demo graph..."
	@if [ -d "$(DEMO_DIR)/studies" ] && [ -n "$$(ls -A $(DEMO_DIR)/studies 2>/dev/null)" ]; then \
		mcbo-build-graph build --data-dir $(DEMO_DIR); \
	elif [ -f "$(DEMO_DIR)/sample_metadata.csv" ]; then \
		mcbo-build-graph bootstrap --data-dir $(DEMO_DIR); \
	else \
		echo "Error: No data found in $(DEMO_DIR)"; exit 1; \
	fi

demo-eval: $(DEMO_GRAPH)
	@echo "Running CQ evaluation on demo data..."
	@mkdir -p $(DEMO_RESULTS)
	mcbo-run-eval --data-dir $(DEMO_DIR)
	@echo ""
	@cat $(DEMO_RESULTS)/SUMMARY.txt

demo-stats: $(DEMO_GRAPH)
	@echo "Demo data statistics:"
	mcbo-stats --data-dir $(DEMO_DIR)

verify-demo: $(DEMO_GRAPH)
	mcbo-run-eval --data-dir $(DEMO_DIR) --verify

# =============================================================================
# Real Data Targets
# =============================================================================

real: check-env real-build real-eval real-stats real-qc
	@echo ""
	@echo "✅ Real data processing complete"
	@echo "   Graph: $(REAL_GRAPH)"
	@echo "   Results: $(REAL_RESULTS)/"

real-build: $(REAL_GRAPH)

$(REAL_GRAPH): $(ONTOLOGY) $(wildcard $(REAL_DIR)/studies/*/sample_metadata.csv) $(wildcard $(REAL_DIR)/sample_metadata.csv)
	@if [ ! -d "$(REAL_DIR)" ]; then \
		echo "ℹ️  Real data directory ($(REAL_DIR)) not found"; \
		echo "   This is normal for public clones without private data."; \
		exit 0; \
	fi
	@echo "Building real data graph..."
	@if [ -d "$(REAL_DIR)/studies" ] && [ -n "$$(ls -A $(REAL_DIR)/studies 2>/dev/null)" ]; then \
		mcbo-build-graph build --data-dir $(REAL_DIR); \
	elif [ -f "$(REAL_DIR)/sample_metadata.csv" ]; then \
		mcbo-build-graph bootstrap --data-dir $(REAL_DIR); \
	else \
		echo "Warning: No data found in $(REAL_DIR)"; \
	fi

real-eval: $(REAL_GRAPH)
	@if [ -f "$(REAL_GRAPH)" ]; then \
		echo "Running CQ evaluation on real data..."; \
		mkdir -p $(REAL_RESULTS); \
		mcbo-run-eval --data-dir $(REAL_DIR); \
		echo ""; \
		cat $(REAL_RESULTS)/SUMMARY.txt; \
	fi

real-stats: $(REAL_GRAPH)
	@if [ -f "$(REAL_GRAPH)" ]; then \
		echo "Real data statistics:"; \
		mcbo-stats --data-dir $(REAL_DIR); \
	fi

verify-real:
	@if [ -f "$(REAL_GRAPH)" ]; then \
		mcbo-run-eval --data-dir $(REAL_DIR) --verify; \
	else \
		echo "ℹ️  Real data graph not found ($(REAL_GRAPH))"; \
	fi

real-qc: $(REAL_GRAPH)
	@if [ -f "$(REAL_GRAPH)" ]; then \
		echo "Running QC on real data graph..."; \
		mkdir -p $(REPORTS_DIR)/real_data; \
		java -jar $(ROBOT_JAR) query \
			--input $(REAL_GRAPH) \
			--query $(SPARQL_DIR)/orphan_classes.rq \
			$(REPORTS_DIR)/real_data/orphan_classes.tsv 2>&1 | grep -v "WARNING:.*Unsafe" || true; \
		java -jar $(ROBOT_JAR) query \
			--input $(REAL_GRAPH) \
			--query $(SPARQL_DIR)/duplicate_labels.rq \
			$(REPORTS_DIR)/real_data/duplicate_labels.tsv 2>&1 | grep -v "WARNING:.*Unsafe" || true; \
	fi

# =============================================================================
# QC Targets
# =============================================================================

qc: $(ROBOT_JAR) qc-ontology
	@echo ""
	@echo "✅ QC checks complete"
	@echo "   Reports: $(REPORTS_DIR)/"

qc-ontology: $(ROBOT_JAR)
	@echo "Running ROBOT QC on ontology..."
	@mkdir -p $(REPORTS_DIR)
	@echo "  Checking for orphan classes..."
	@java -jar $(ROBOT_JAR) query \
		--input $(ONTOLOGY) \
		--query $(SPARQL_DIR)/orphan_classes.rq \
		$(REPORTS_DIR)/orphan_classes.tsv 2>&1 | grep -v "WARNING:.*Unsafe" || true
	@echo "  Checking for duplicate labels..."
	@java -jar $(ROBOT_JAR) query \
		--input $(ONTOLOGY) \
		--query $(SPARQL_DIR)/duplicate_labels.rq \
		$(REPORTS_DIR)/duplicate_labels.tsv 2>&1 | grep -v "WARNING:.*Unsafe" || true
	@echo "  Checking for missing definitions..."
	@java -jar $(ROBOT_JAR) query \
		--input $(ONTOLOGY) \
		--query $(SPARQL_DIR)/missing_definitions.rq \
		$(REPORTS_DIR)/missing_definitions.tsv 2>&1 | grep -v "WARNING:.*Unsafe" || true

# =============================================================================
# Clean Targets
# =============================================================================

clean: clean-demo clean-real clean-reports
	@echo "✅ Clean complete"

clean-demo:
	@echo "Cleaning demo artifacts..."
	rm -f $(DEMO_GRAPH)
	rm -f $(DEMO_INSTANCES)
	rm -rf $(DEMO_RESULTS)
	rm -f $(DEMO_DIR)/STATS.txt

clean-real:
	@echo "Cleaning real data artifacts..."
	rm -f $(REAL_GRAPH)
	rm -f $(REAL_INSTANCES)
	rm -rf $(REAL_RESULTS)
	rm -f $(REAL_DIR)/STATS.txt

clean-reports:
	@echo "Cleaning reports..."
	rm -rf $(REPORTS_DIR)

# =============================================================================
# CI/CD Target
# =============================================================================

ci: install qc demo verify-demo
	@echo ""
	@echo "✅ CI checks passed"

# =============================================================================
# Documentation Targets
# =============================================================================

docs:
	@echo "Building Sphinx documentation..."
	@cd docs && $(MAKE) html
	@echo ""
	@echo "✅ Documentation built successfully"
	@echo "   Open docs/_build/html/index.html in your browser"

docs-clean:
	@echo "Cleaning documentation build..."
	@cd docs && $(MAKE) clean

