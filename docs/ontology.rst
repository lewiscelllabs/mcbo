Ontology Design
===============

MCBO (Mammalian Cell Bioprocessing Ontology) uses a hub-and-spoke architecture with the 
Industrial Ontology Foundry (IOF) Core as the central hub, building on BFO foundations with 
domain-specific extensions.

Hub-and-Spoke Architecture
--------------------------

MCBO reuses terms from multiple OBO Foundry ontologies:

.. list-table::
   :header-rows: 1
   :widths: 15 30 30 25

   * - Ontology
     - Scope / Coverage
     - Example Terms Used
     - Role in MCBO
   * - IOF Core
     - Industrial processes
     - ProductProductionProcess, hasOutput
     - Hub anchor for all processes/outputs
   * - CLO
     - Cell lines
     - CHO-K1
     - Standardized cell line IDs
   * - CL
     - Cell types
     - Chinese hamster ovary cell
     - Biological cell type grounding
   * - OBI
     - Assays
     - RNA-seq assay, has specified input/output
     - Experimental processes
   * - EFO/ENVO
     - Conditions, environments
     - Hypoxia, culture pH
     - Capture experimental context
   * - ChEBI
     - Chemicals
     - Glucose, L-glutamine
     - Media components
   * - UO
     - Units
     - gram per liter
     - Normalize quantitative values
   * - PATO
     - Phenotypes
     - Cell viability
     - Describe traits
   * - SO/GO/PRO
     - Molecular entities
     - Transcript, gene ontology term, IgG protein
     - Link outputs to biology

Core Modeling Patterns
----------------------

MCBO follows BFO-compliant semantic patterns to ensure interoperability with OBO Foundry ontologies.

Process–Participant–Quality Chain
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The core pattern for culture conditions:

.. code-block:: text

   Process (BFO:process)
     └─ RO:0000057 (has participant) → CellCultureSystem (BFO:material entity)
         └─ RO:0000086 (has quality) → CultureConditionQuality (BFO:quality)
             ├─ hasTemperature (xsd:decimal)
             ├─ hasPH (xsd:decimal)
             └─ hasDissolvedOxygen (xsd:decimal)

**How it works:**

1. A bioprocess (e.g., ``BatchCultureProcess``, ``FedBatchCultureProcess``) is a ``BFO:process`` instance
2. The process ``RO:0000057`` (has participant) a ``CellCultureSystem`` (a ``BFO:material entity``)
3. The ``CellCultureSystem`` ``RO:0000086`` (has quality) a ``CultureConditionQuality`` instance (a ``BFO:quality``)
4. Temperature, pH, and dissolved oxygen values are attached as datatype properties to the ``CultureConditionQuality`` instance

This pattern preserves BFO semantics: processes have material entity participants, which bear qualities.
It avoids direct process-to-quality links that would conflict with BFO's occurrent–continuant distinction.

Cell Line Engineering
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   CellLine (material entity)
     └─ mcbo:overexpressesGene → Gene (information entity)

- Cell lines can ``mcbo:overexpressesGene`` gene individuals
- Inferred from Producer (boolean) + ProductType fields when explicit gene columns not present
- Antibody products (mAb/BsAb) use shared placeholder gene ``mcbo:AntibodyProductGene``

Sample Outputs
^^^^^^^^^^^^^^

.. code-block:: text

   CellCultureProcess (process)
     └─ mcbo:hasProcessOutput → BioprocessSample (material entity)
         └─ mcbo:inCulturePhase → CulturePhase (StationaryPhase, ExponentialPhase)

- Runs produce samples via ``mcbo:hasProcessOutput``
- Samples can be in specific culture phases
- Productivity measurements are attached to runs

Key Data Structures
-------------------

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Structure
     - Location
     - Description
   * - TBox (Ontology)
     - ``ontology/mcbo.owl.ttl``
     - Ontology schema - class definitions, properties
   * - ABox (Instances)
     - ``<data-dir>/mcbo-instances.ttl``
     - Instance data generated from CSV
   * - Evaluation Graphs
     - ``<data-dir>/graph.ttl``
     - Union of TBox + ABox for SPARQL queries

Scope and Boundaries
--------------------

In Scope
^^^^^^^^

- Mammalian cell bioprocessing (CHO, HEK293)
- Culture process types: Batch, Fed-batch, Perfusion, Continuous
- RNA-seq data integration
- Culture conditions (temperature, pH, dissolved oxygen)
- Productivity measurements
- Cell line engineering (gene overexpression)

Out of Scope
^^^^^^^^^^^^

- Non-mammalian cell culture (yeast, bacterial)
- Downstream purification processes (future work)
- Proteomics data (future work)

Dataset Classification
----------------------

All dataset classes are subclasses of ``IAO:dataset`` (IAO_0000100), which is an information 
content entity (ICE) in the BFO/IAO hierarchy:

- ``RNASeqDataset``
- ``RawReadsDataset``
- ``AlignedReadsDataset``

This ensures proper classification: datasets are ICEs, not material entities or processes.

CSV to RDF Conversion
---------------------

The ``mcbo.csv_to_rdf`` module transforms tabular metadata into RDF:

- Maps process types (Batch, FedBatch, Perfusion, etc.) to ontology classes
- Creates material entities (CellCultureSystem, cell lines, culture media)
- Attaches culture conditions (temperature, pH, dissolved oxygen) as qualities
- Handles productivity categorization (VeryHigh, High, Medium, LowMedium, Low)
- Infers gene overexpression from Producer + ProductType columns
- Generates IRI-safe identifiers from run/sample accessions

SPARQL Query Architecture
-------------------------

Competency questions in ``eval/queries/*.rq`` leverage:

- ``rdfs:subClassOf*`` property paths for class hierarchies
- OBO relation IRIs (RO_0000057, RO_0000086) for standard relationships
- Filters on productivity types for optimization queries
- Cross-table relationship traversals via the RDF graph structure

IOF Alignment
-------------

MCBO process classes (e.g., ``CellCultureProcess``, ``MammalianCellBioprocess``) are direct 
subclasses of ``BFO:process`` to maintain strict BFO alignment and interoperability with 
OBO Foundry ontologies.

We use ``rdfs:seeAlso`` annotations to ``iof:ManufacturingProcess`` and 
``iof:ProductProductionProcess`` to indicate conceptual alignment with IOF manufacturing 
concepts, while preserving direct BFO classification.

This approach ensures compatibility with both BFO-based biomedical ontologies and IOF-based 
industrial ontologies.

