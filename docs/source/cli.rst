CLI Reference
=============

MCBO provides four command-line tools for working with bioprocessing data and the ontology.

Available Commands
------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Command
     - Description
   * - ``mcbo-csv-to-rdf``
     - Convert CSV metadata to RDF instances (with optional expression data)
   * - ``mcbo-build-graph``
     - Build graphs from studies or single CSV (bootstrap, build, merge, add-study)
   * - ``mcbo-run-eval``
     - Run SPARQL competency queries
   * - ``mcbo-stats``
     - Generate graph statistics

mcbo-build-graph
----------------

Build and manage evaluation graphs.

Subcommands
^^^^^^^^^^^

**bootstrap** - Create graph from single CSV

.. code-block:: bash

   mcbo-build-graph bootstrap \
     --csv .data/sample_metadata.csv \
     --output .data/graph.ttl

**build** - Build from study directories

.. code-block:: bash

   mcbo-build-graph build \
     --studies-dir .data/studies \
     --output .data/graph.ttl
   
   # Or with config-by-convention
   mcbo-build-graph build --data-dir .data

**add-study** - Add a study incrementally

.. code-block:: bash

   mcbo-build-graph add-study \
     --study-dir .data/studies/my_new_study \
     --instances .data/mcbo-instances.ttl

**merge** - Merge instances with ontology

.. code-block:: bash

   mcbo-build-graph merge \
     --ontology ontology/mcbo.owl.ttl \
     --instances .data/mcbo-instances.ttl \
     --output .data/graph.ttl

Options
^^^^^^^

.. code-block:: text

   --data-dir DIR       Use config-by-convention (auto-resolves paths)
   --csv FILE           Input CSV file (for bootstrap)
   --studies-dir DIR    Directory containing study subdirectories
   --study-dir DIR      Single study directory to add
   --instances FILE     Path to instances TTL file
   --output FILE        Output graph file
   --ontology FILE      Ontology TTL file (default: ontology/mcbo.owl.ttl)
   --expression-dir DIR Directory with per-study expression matrices
   --expression-matrix FILE  Single expression matrix file

mcbo-csv-to-rdf
---------------

Low-level CSV to RDF conversion.

.. code-block:: bash

   mcbo-csv-to-rdf \
     --csv_file .data/sample_metadata.csv \
     --output_file .data/mcbo-instances.ttl

With expression data:

.. code-block:: bash

   mcbo-csv-to-rdf \
     --csv_file .data/sample_metadata.csv \
     --output_file .data/mcbo-instances.ttl \
     --expression_dir .data/expression/

Options
^^^^^^^

.. code-block:: text

   --csv_file FILE          Input CSV metadata file (required)
   --output_file FILE       Output TTL file (required)
   --expression_matrix FILE Single expression matrix CSV
   --expression_dir DIR     Directory with per-study expression CSVs

mcbo-run-eval
-------------

Run SPARQL competency question queries.

.. code-block:: bash

   # Using config-by-convention
   mcbo-run-eval --data-dir data.sample
   
   # Using explicit paths
   mcbo-run-eval \
     --graph data.sample/graph.ttl \
     --queries eval/queries \
     --results data.sample/results

Options
^^^^^^^

.. code-block:: text

   --data-dir DIR      Use config-by-convention
   --graph FILE        Input graph TTL file
   --queries DIR       Directory with .rq query files (default: eval/queries)
   --results DIR       Output directory for TSV results
   --verify            Only verify graph parses, don't run queries
   --fail-on-empty     Exit with error if any CQ returns 0 results

mcbo-stats
----------

Generate statistics about a graph.

.. code-block:: bash

   mcbo-stats --data-dir data.sample
   
   # Or with explicit path
   mcbo-stats --graph .data/graph.ttl

Output includes:

- Total cell culture process instances (by type: Batch, Fed-batch, Perfusion, Unknown)
- Total bioprocess sample instances

Config-by-Convention
--------------------

All CLI tools support ``--data-dir`` for automatic path resolution:

.. code-block:: bash

   # These are equivalent:
   mcbo-run-eval --data-dir data.sample
   mcbo-run-eval --graph data.sample/graph.ttl --results data.sample/results
   
   # Convention: <data-dir>/ contains:
   #   graph.ttl           - merged evaluation graph
   #   mcbo-instances.ttl  - instance data (ABox)
   #   results/            - CQ query results

CSV Column Reference
--------------------

Required Columns
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Column
     - CQs
     - Description
   * - ``RunAccession``
     - all
     - Unique run ID
   * - ``SampleAccession``
     - all
     - Unique sample ID
   * - ``CellLine``
     - CQ1-8
     - Cell line name (CHO-K1, HEK293)
   * - ``ProcessType``
     - CQ5
     - Batch, FedBatch, Perfusion

Optional Columns
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 10 60

   * - Column
     - CQs
     - Description
   * - ``Temperature``
     - CQ1
     - Culture temperature (°C)
   * - ``pH``
     - CQ1
     - Culture medium pH
   * - ``DissolvedOxygen``
     - CQ1
     - Dissolved oxygen (% saturation)
   * - ``Productivity``
     - CQ1, CQ6
     - High/Medium/Low or numeric
   * - ``CollectionDay``
     - CQ3
     - Day of sample collection
   * - ``ViableCellDensity``
     - CQ3
     - Viable cells/mL
   * - ``ViabilityPercentage``
     - CQ7
     - Cell viability %
   * - ``CloneID``
     - CQ4, CQ8
     - Clone identifier
   * - ``GlutamineConcentration``
     - CQ3
     - mM glutamine
   * - ``TiterValue``
     - CQ8
     - Product titer (mg/L)
   * - ``QualityType``
     - CQ8
     - Quality attribute type
   * - ``Producer``
     - CQ2
     - Boolean: TRUE if producer line
   * - ``ProductType``
     - CQ2
     - Product name (mAb, BsAb, gene symbol)

Expression Matrix Format
^^^^^^^^^^^^^^^^^^^^^^^^

For gene expression data (CQ4, CQ6, CQ7), use a separate CSV file:

.. code-block:: text

   SampleAccession,GeneX,GeneY,GeneZ,ACTB,GAPDH
   ERS4805133,150,200,50,1000,800
   ERS4805134,180,220,45,950,850

- First column must be ``SampleAccession`` (matching metadata CSV)
- Remaining columns are gene symbols
- Values are expression levels (TPM, FPKM, etc.)

Running as Python Modules
-------------------------

Commands can also be run as Python modules:

.. code-block:: bash

   python -m mcbo.csv_to_rdf --help
   python -m mcbo.build_graph --help
   python -m mcbo.run_eval --help
   python -m mcbo.stats_eval_graph --help

