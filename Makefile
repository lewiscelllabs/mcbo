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
#   - Python package + ROBOT installed: make install

.PHONY: all demo real qc clean help install robot verify-demo verify-real conda-env check-env docs docs-clean clean-demo clean-real clean-reports clean-install ci demo-build demo-eval demo-stats real-build real-eval real-stats real-qc qc-ontology install-agent install-ollama clean-agent

# Configuration
PYTHON := python
ROBOT_JAR := .robot/robot.jar
ONTOLOGY := ontology/mcbo.owl.ttl
SPARQL_DIR := sparql
REPORTS_DIR := reports/robot

# Conda/Mamba detection (prefer mamba for faster dependency resolution)
CONDA := $(shell command -v conda 2>/dev/null)
MAMBA := $(shell command -v mamba 2>/dev/null)
CONDA_OR_MAMBA := $(if $(MAMBA),mamba,conda)
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
REAL_CSV := $(REAL_DIR)/sample_metadata.csv
REAL_RESULTS := $(REAL_DIR)/results

# Output files (for proper dependency tracking)
DEMO_SUMMARY := $(DEMO_RESULTS)/SUMMARY.txt
DEMO_STATS := $(DEMO_DIR)/STATS.txt
REAL_SUMMARY := $(REAL_RESULTS)/SUMMARY.txt
REAL_STATS := $(REAL_DIR)/STATS.txt
INSTALL_STAMP := .install.stamp

# QC report files
QC_ORPHAN := $(REPORTS_DIR)/orphan_classes.tsv
QC_DUPLABELS := $(REPORTS_DIR)/duplicate_labels.tsv
QC_MISSINGDEFS := $(REPORTS_DIR)/missing_definitions.tsv
# Real data QC reports go under the data directory (not checked in)
REAL_REPORTS_DIR := $(REAL_DIR)/reports
REAL_QC_ORPHAN := $(REAL_REPORTS_DIR)/orphan_classes.tsv
REAL_QC_DUPLABELS := $(REAL_REPORTS_DIR)/duplicate_labels.tsv
REAL_QC_MISSINGDEFS := $(REAL_REPORTS_DIR)/missing_definitions.tsv

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
	@echo "Agent (LLM-powered queries):"
	@echo "  make install-agent   Install agent deps (ollama, anthropic, openai)"
	@echo "  make install-ollama  Install Ollama for local LLM inference"
	@echo ""
	@echo "  After install, set API key:"
	@echo "    export OPENAI_API_KEY=sk-...    # For OpenAI"
	@echo "    export ANTHROPIC_API_KEY=...   # For Anthropic"
	@echo ""
	@echo "  Test agent:"
	@echo "    mcbo-agent-eval --data-dir data.sample --cq CQ1"
	@echo "    mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider ollama"
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
	@echo "Please install Miniforge (recommended) or Miniconda:"
	@echo "  https://github.com/conda-forge/miniforge#miniforge3"
	@echo "  https://docs.conda.io/en/latest/miniconda.html"
	@echo ""
	@echo "Quick install (Linux):"
	@echo "  wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
	@echo "  bash Miniforge3-Linux-x86_64.sh"
	@echo ""
	@echo "Quick install (macOS):"
	@echo "  brew install miniforge"
	@echo ""
	@exit 1
else
	@if conda env list | grep -q "^mcbo "; then \
		echo "ℹ️  Conda environment 'mcbo' already exists"; \
		echo "   To recreate: conda env remove -n mcbo && make conda-env"; \
	else \
		echo "Creating mcbo conda environment from environment.yml..."; \
		if command -v mamba >/dev/null 2>&1; then \
			echo "  (using mamba for faster dependency resolution)"; \
			mamba env create -f environment.yml; \
		else \
			echo "  (tip: install mamba for faster installs: conda install -n base mamba)"; \
			conda env create -f environment.yml; \
		fi; \
		echo ""; \
		echo "✅ Environment created (includes Python 3.10 + OpenJDK)!"; \
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
		echo "   Or to create: make conda-env (requires conda/mamba)"; \
		echo ""; \
	fi

# Installation (requires active conda environment)
install: check-env $(INSTALL_STAMP) $(ROBOT_JAR)

$(INSTALL_STAMP): requirements.txt python/pyproject.toml
	pip install -r requirements.txt
	pip install -e python/
	@touch $(INSTALL_STAMP)
	@echo ""
	@echo "✅ mcbo package installed"
	@echo "   (ROBOT will be downloaded next if needed)"

# Agent installation with LLM provider dependencies
AGENT_STAMP := .agent-install.stamp

install-agent: check-env $(AGENT_STAMP)

$(AGENT_STAMP): $(INSTALL_STAMP) python/pyproject.toml
	@echo "Installing agent dependencies (scipy, anthropic, openai, requests)..."
	pip install -e python/[agent]
	@touch $(AGENT_STAMP)
	@echo ""
	@echo "✅ Agent dependencies installed"
	@echo ""
	@echo "Configure your LLM provider:"
	@echo "  OpenAI:    export OPENAI_API_KEY=sk-..."
	@echo "  Anthropic: export ANTHROPIC_API_KEY=sk-ant-..."
	@echo "  Ollama:    No key needed (install: https://ollama.ai)"
	@echo ""
	@echo "Test with: mcbo-agent-eval --data-dir data.sample --cq CQ1"

install-ollama: check-env $(AGENT_STAMP)
	@echo "Installing Ollama and pulling models..."
	@if command -v ollama >/dev/null 2>&1; then \
		echo "✅ Ollama already installed"; \
	else \
		echo "❌ Ollama not found. Install from: https://ollama.ai"; \
		echo ""; \
		echo "Quick install (Linux):"; \
		echo "  curl -fsSL https://ollama.ai/install.sh | sh"; \
		echo ""; \
		echo "Quick install (macOS):"; \
		echo "  brew install ollama"; \
		exit 1; \
	fi
	@echo ""
	@echo "Pulling recommended model (qwen2.5:3b - fast, good for tool calling)..."
	ollama pull qwen2.5:3b
	@echo ""
	@echo "✅ Ollama setup complete"
	@echo ""
	@echo "Start Ollama server (if not running): ollama serve"
	@echo "Test: mcbo-agent-eval --data-dir data.sample --cq CQ1 --provider ollama --model qwen2.5:3b"

robot: $(ROBOT_JAR)

$(ROBOT_JAR):
	@echo "Downloading ROBOT..."
	@mkdir -p .robot
	@curl -L -o $(ROBOT_JAR) "https://github.com/ontodev/robot/releases/download/v1.9.6/robot.jar"
	@echo "✅ ROBOT downloaded to $(ROBOT_JAR)"

# =============================================================================
# Demo Data Targets
# =============================================================================

demo: check-env $(DEMO_GRAPH) $(DEMO_SUMMARY) $(DEMO_STATS)
	@echo ""
	@echo "✅ Demo data processing complete"
	@echo "   Graph: $(DEMO_GRAPH)"
	@echo "   Results: $(DEMO_RESULTS)/"

demo-build: $(DEMO_GRAPH)

$(DEMO_GRAPH): $(ONTOLOGY) $(wildcard $(DEMO_DIR)/studies/*/sample_metadata.csv) $(wildcard $(DEMO_DIR)/sample_metadata.csv) $(wildcard $(DEMO_DIR)/expression/*.csv)
	@echo "Building demo graph..."
	@# Unified build: root CSV (foundation) + studies (supplements)
	mcbo-build-graph build --data-dir $(DEMO_DIR)

demo-eval: $(DEMO_SUMMARY)

$(DEMO_SUMMARY): $(DEMO_GRAPH) $(wildcard eval/queries/*.rq)
	@echo "Running CQ evaluation on demo data..."
	@mkdir -p $(DEMO_RESULTS)
	mcbo-run-eval --data-dir $(DEMO_DIR)
	@echo ""
	@cat $(DEMO_SUMMARY)

demo-stats: $(DEMO_STATS)
	@cat $(DEMO_STATS)

$(DEMO_STATS): $(DEMO_GRAPH)
	@echo "Generating demo data statistics..."
	@mcbo-stats --data-dir $(DEMO_DIR) > $(DEMO_STATS)
	@echo "  -> $(DEMO_STATS)"

verify-demo: $(DEMO_GRAPH)
	mcbo-run-eval --data-dir $(DEMO_DIR) --verify

# =============================================================================
# Real Data Targets
# =============================================================================

real: check-env $(REAL_GRAPH) $(REAL_SUMMARY) $(REAL_STATS)
	@echo ""
	@echo "✅ Real data processing complete"
	@echo "   Graph: $(REAL_GRAPH)"
	@echo "   Results: $(REAL_RESULTS)/"

real-build: $(REAL_GRAPH)

# Build real data graph using mcbo-build-graph (handles root CSV + studies + expression)
$(REAL_GRAPH): $(ONTOLOGY) $(wildcard $(REAL_DIR)/studies/*/sample_metadata.csv) $(wildcard $(REAL_CSV)) $(wildcard $(REAL_DIR)/expression/*.csv)
	@if [ ! -d "$(REAL_DIR)" ]; then \
		echo "ℹ️  Real data directory ($(REAL_DIR)) not found"; \
		echo "   This is normal for public clones without private data."; \
		exit 0; \
	fi
	@echo "Building real data graph..."
	@# Unified build: root CSV (foundation) + studies (supplements)
	mcbo-build-graph build --data-dir $(REAL_DIR)

real-eval: $(REAL_SUMMARY)

$(REAL_SUMMARY): $(REAL_GRAPH) $(wildcard eval/queries/*.rq)
	@if [ -f "$(REAL_GRAPH)" ]; then \
		echo "Running CQ evaluation on real data..."; \
		mkdir -p $(REAL_RESULTS); \
		mcbo-run-eval --data-dir $(REAL_DIR); \
		echo ""; \
		cat $(REAL_SUMMARY); \
	fi

real-stats: $(REAL_STATS)
	@if [ -f "$(REAL_STATS)" ]; then cat $(REAL_STATS); fi

$(REAL_STATS): $(REAL_GRAPH)
	@if [ -f "$(REAL_GRAPH)" ]; then \
		echo "Generating real data statistics..."; \
		mcbo-stats --data-dir $(REAL_DIR) > $(REAL_STATS); \
		echo "  -> $(REAL_STATS)"; \
	fi

verify-real:
	@if [ -f "$(REAL_GRAPH)" ]; then \
		mcbo-run-eval --data-dir $(REAL_DIR) --verify; \
	else \
		echo "ℹ️  Real data graph not found ($(REAL_GRAPH))"; \
	fi

# Note: real-qc is NOT included in 'make real' by default.
# The QC queries (orphan_classes, duplicate_labels, missing_definitions) are designed
# for ontology classes (TBox), not instance data (ABox). Use 'make qc' for ontology QC.
# This target is kept for manual use if needed.
real-qc: $(REAL_GRAPH) $(ROBOT_JAR)
	@echo "⚠️  Note: QC queries are designed for ontology, not instance data"
	@if [ -f "$(REAL_GRAPH)" ]; then \
		mkdir -p $(REAL_REPORTS_DIR); \
		java -jar $(ROBOT_JAR) query \
			--input $(REAL_GRAPH) \
			--query $(SPARQL_DIR)/orphan_classes.rq \
			$(REAL_QC_ORPHAN) 2>&1 | grep -v "WARNING:.*Unsafe" || true; \
		java -jar $(ROBOT_JAR) query \
			--input $(REAL_GRAPH) \
			--query $(SPARQL_DIR)/duplicate_labels.rq \
			$(REAL_QC_DUPLABELS) 2>&1 | grep -v "WARNING:.*Unsafe" || true; \
		java -jar $(ROBOT_JAR) query \
			--input $(REAL_GRAPH) \
			--query $(SPARQL_DIR)/missing_definitions.rq \
			$(REAL_QC_MISSINGDEFS) 2>&1 | grep -v "WARNING:.*Unsafe" || true; \
		echo "  Reports: $(REAL_REPORTS_DIR)/"; \
	fi

# =============================================================================
# QC Targets
# =============================================================================

qc: $(QC_ORPHAN) $(QC_DUPLABELS) $(QC_MISSINGDEFS)
	@echo ""
	@echo "✅ QC checks complete"
	@echo "   Reports: $(REPORTS_DIR)/"

qc-ontology: $(QC_ORPHAN) $(QC_DUPLABELS) $(QC_MISSINGDEFS)

$(QC_ORPHAN): $(ONTOLOGY) $(ROBOT_JAR) $(SPARQL_DIR)/orphan_classes.rq
	@echo "Running ROBOT QC on ontology..."
	@mkdir -p $(REPORTS_DIR)
	@echo "  Checking for orphan classes..."
	@java -jar $(ROBOT_JAR) query \
		--input $(ONTOLOGY) \
		--query $(SPARQL_DIR)/orphan_classes.rq \
		$(QC_ORPHAN) 2>&1 | grep -v "WARNING:.*Unsafe" || true

$(QC_DUPLABELS): $(ONTOLOGY) $(ROBOT_JAR) $(SPARQL_DIR)/duplicate_labels.rq
	@mkdir -p $(REPORTS_DIR)
	@echo "  Checking for duplicate labels..."
	@java -jar $(ROBOT_JAR) query \
		--input $(ONTOLOGY) \
		--query $(SPARQL_DIR)/duplicate_labels.rq \
		$(QC_DUPLABELS) 2>&1 | grep -v "WARNING:.*Unsafe" || true

$(QC_MISSINGDEFS): $(ONTOLOGY) $(ROBOT_JAR) $(SPARQL_DIR)/missing_definitions.rq
	@mkdir -p $(REPORTS_DIR)
	@echo "  Checking for missing definitions..."
	@java -jar $(ROBOT_JAR) query \
		--input $(ONTOLOGY) \
		--query $(SPARQL_DIR)/missing_definitions.rq \
		$(QC_MISSINGDEFS) 2>&1 | grep -v "WARNING:.*Unsafe" || true

# =============================================================================
# Clean Targets
# =============================================================================

clean: clean-demo clean-real clean-reports clean-install
	@echo "✅ Clean complete"

clean-demo:
	@echo "Cleaning demo artifacts..."
	rm -f $(DEMO_GRAPH)
	rm -f $(DEMO_INSTANCES)
	@# Safety: only rm -rf if variable is non-empty and not root
	@if [ -n "$(DEMO_RESULTS)" ] && [ "$(DEMO_RESULTS)" != "/" ]; then rm -rf $(DEMO_RESULTS); fi
	rm -f $(DEMO_STATS)

clean-real:
	@echo "Cleaning real data artifacts..."
	rm -f $(REAL_GRAPH)
	rm -f $(REAL_INSTANCES)
	@# Safety: only rm -rf if variable is non-empty and not root
	@if [ -n "$(REAL_RESULTS)" ] && [ "$(REAL_RESULTS)" != "/" ]; then rm -rf $(REAL_RESULTS); fi
	@if [ -n "$(REAL_REPORTS_DIR)" ] && [ "$(REAL_REPORTS_DIR)" != "/" ]; then rm -rf $(REAL_REPORTS_DIR); fi
	rm -f $(REAL_STATS)

clean-reports:
	@echo "Cleaning reports..."
	@if [ -n "$(REPORTS_DIR)" ] && [ "$(REPORTS_DIR)" != "/" ]; then rm -rf $(REPORTS_DIR); fi

clean-install:
	@rm -f $(INSTALL_STAMP) $(DOCS_STAMP) $(AGENT_STAMP)

clean-agent:
	@echo "Cleaning agent artifacts..."
	@rm -f $(AGENT_STAMP)
	@rm -rf data.sample/agent_results
	@rm -rf .data/agent_results

# =============================================================================
# CI/CD Target
# =============================================================================

ci: install qc demo verify-demo
	@echo ""
	@echo "✅ CI checks passed"

# =============================================================================
# Documentation Targets
# =============================================================================

DOCS_STAMP := .docs-install.stamp

docs: check-env $(DOCS_STAMP)
	@echo "Building Sphinx documentation..."
	@cd docs && $(MAKE) html
	@echo ""
	@echo "✅ Documentation built successfully"
	@echo "   Open docs/_build/html/index.html in your browser"

$(DOCS_STAMP): docs/requirements.txt $(INSTALL_STAMP)
	pip install -r docs/requirements.txt
	@touch $(DOCS_STAMP)

docs-clean:
	@echo "Cleaning documentation build..."
	@cd docs && $(MAKE) clean
	@rm -f $(DOCS_STAMP)

