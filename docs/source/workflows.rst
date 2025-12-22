Data Workflows
==============

This document describes the different workflows for building MCBO evaluation graphs,
from simple single-file scenarios to large-scale dataset management.

Quick Reference
---------------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Workflow
     - Command
     - Use Case
   * - Config-by-convention
     - ``make demo`` or ``make real``
     - Standard workflow
   * - Single CSV bootstrap
     - ``mcbo-build-graph bootstrap --csv FILE``
     - Hand-curated metadata
   * - Multi-study build
     - ``mcbo-build-graph build --studies-dir DIR``
     - Per-study CSVs
   * - Incremental add
     - ``mcbo-build-graph add-study --study-dir DIR``
     - Add new studies over time

Configuration by Convention
---------------------------

MCBO tools use a standardized directory layout. When you provide a ``--data-dir`` argument,
paths are automatically resolved:

.. code-block:: text

   <data-dir>/
   ├── graph.ttl               # Output: merged evaluation graph (TBox + ABox)
   ├── mcbo-instances.ttl      # Output: instance data (ABox)
   ├── sample_metadata.csv     # Input: single CSV (for bootstrap)
   ├── expression/             # Input: per-study expression matrices
   │   ├── study_001.csv
   │   └── study_002.csv
   ├── studies/                # Input: study directories (for multi-study build)
   │   ├── study_001/
   │   │   ├── sample_metadata.csv
   │   │   └── expression_matrix.csv
   │   └── study_002/
   │       └── sample_metadata.csv
   └── results/                # Output: CQ evaluation results
       ├── cq1.tsv
       └── SUMMARY.txt

The ontology (TBox) is always at ``ontology/mcbo.owl.ttl`` relative to the repository root.

Workflow 1: Demo Data (Getting Started)
---------------------------------------

.. code-block:: bash

   # Using Makefile (recommended)
   make demo
   
   # Manual steps
   mcbo-build-graph build --data-dir data.sample
   mcbo-run-eval --data-dir data.sample
   mcbo-stats --data-dir data.sample

Workflow 2: Bootstrap from Single CSV
-------------------------------------

Best for: Initial dataset creation with hand-curated metadata covering multiple studies.

.. code-block:: bash

   # Just metadata
   mcbo-build-graph bootstrap \
     --csv .data/sample_metadata.csv \
     --output .data/graph.ttl
   
   # With per-study expression matrices
   mcbo-build-graph bootstrap \
     --csv .data/sample_metadata.csv \
     --expression-dir .data/expression/ \
     --output .data/graph.ttl
   
   # With single expression matrix
   mcbo-build-graph bootstrap \
     --csv .data/sample_metadata.csv \
     --expression-matrix .data/expression_matrix.csv \
     --output .data/graph.ttl

Workflow 3: Multi-Study Build
-----------------------------

Best for: When each study has its own directory with metadata and optional expression data.

.. code-block:: bash

   # Build from study directories
   mcbo-build-graph build \
     --studies-dir .data/studies \
     --output .data/graph.ttl
   
   # Using config-by-convention
   mcbo-build-graph build --data-dir .data

Each study directory should contain:

- ``sample_metadata.csv`` (required) - sample/run metadata
- ``expression_matrix.csv`` (optional) - gene expression data

Workflow 4: Incremental Study Addition
--------------------------------------

Best for: Growing datasets where you add studies over time without rebuilding everything.

.. code-block:: bash

   # Add first study
   mcbo-build-graph add-study \
     --study-dir .data/studies/study_001 \
     --instances .data/mcbo-instances.ttl
   
   # Add subsequent studies (appends to existing instances)
   mcbo-build-graph add-study \
     --study-dir .data/studies/study_002 \
     --instances .data/mcbo-instances.ttl
   
   # When ready, merge with ontology
   mcbo-build-graph merge \
     --instances .data/mcbo-instances.ttl \
     --output .data/graph.ttl

Benefits for Large Datasets
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Incremental updates**: Add new studies without reprocessing existing data
- **Partial rebuilds**: Only regenerate graph when needed
- **Memory efficiency**: Process one study at a time
- **Git-friendly**: Instance files can be tracked separately

Workflow 5: Evaluation and Statistics
-------------------------------------

.. code-block:: bash

   # Run all competency questions
   mcbo-run-eval --data-dir .data
   
   # Verify graph parses without running queries
   mcbo-run-eval --data-dir .data --verify
   
   # Generate statistics
   mcbo-stats --data-dir .data
   
   # Fail if any CQ returns 0 results
   mcbo-run-eval --data-dir .data --fail-on-empty

Large Dataset Best Practices
----------------------------

Directory Organization
^^^^^^^^^^^^^^^^^^^^^^

Keep real data separate from demo data:

.. code-block:: text

   mcbo/
   ├── data.sample/     # Demo data (committed)
   │   └── ...
   └── .data/           # Real data (git-ignored)
       └── ...

Incremental Processing
^^^^^^^^^^^^^^^^^^^^^^

For datasets with 1000+ processes:

.. code-block:: bash

   # Process studies in batches
   for study in .data/studies/study_*; do
     mcbo-build-graph add-study \
       --study-dir "$study" \
       --instances .data/mcbo-instances.ttl
   done
   
   # Generate final graph
   mcbo-build-graph merge --data-dir .data

Memory Considerations
^^^^^^^^^^^^^^^^^^^^^

Large expression matrices can consume significant memory. Strategies:

- Split expression data into per-study files
- Use the ``--expression-dir`` approach instead of single large matrices
- Process studies incrementally with ``add-study``

Validation Checkpoints
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # After each major step, verify the graph
   mcbo-run-eval --graph .data/mcbo-instances.ttl --verify
   
   # Check for QC issues
   java -jar .robot/robot.jar query \
     --input .data/graph.ttl \
     --query sparql/orphan_classes.rq \
     reports/robot/orphan_classes.tsv

Backup Strategy
^^^^^^^^^^^^^^^

.. code-block:: bash

   # Before major changes
   cp .data/mcbo-instances.ttl .data/mcbo-instances.backup.ttl
   
   # Version with timestamp
   cp .data/graph.ttl .data/graph.$(date +%Y%m%d).ttl

File Naming Conventions
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - File
     - Description
   * - ``mcbo.owl.ttl``
     - Ontology schema (TBox)
   * - ``mcbo-instances.ttl``
     - Instance data (ABox)
   * - ``graph.ttl``
     - Merged evaluation graph (TBox + ABox)
   * - ``sample_metadata.csv``
     - Input metadata CSV
   * - ``expression_matrix.csv``
     - Input expression data CSV
   * - ``results/*.tsv``
     - CQ query results

Troubleshooting
---------------

Graph doesn't parse
^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   mcbo-run-eval --graph .data/graph.ttl --verify
   # Shows: FAIL: Graph parsing failed - <error>

Missing expression data
^^^^^^^^^^^^^^^^^^^^^^^

Check that sample IDs in expression matrix match ``SampleAccession`` in metadata CSV.

Memory errors
^^^^^^^^^^^^^

Split into smaller batches using incremental workflow.

CQ returns 0 results
^^^^^^^^^^^^^^^^^^^^

Check required columns in metadata CSV. See :doc:`cli` for column requirements.

