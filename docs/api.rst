API Reference
=============

This section documents the MCBO Python package API.

Installation
------------

.. code-block:: bash

   pip install -e python/

After installation, import the package:

.. code-block:: python

   from mcbo import (
       # Namespaces
       MCBO, OBO, RDF, RDFS, XSD,
       RO_HAS_PARTICIPANT, RO_HAS_QUALITY, BFO_HAS_PART,
       
       # Graph utilities
       create_graph, load_graph, load_graphs,
       iri_safe, safe_numeric,
       ensure_dir, ensure_parent_dir,
       
       # CSV conversion
       convert_csv_to_rdf,
       load_expression_matrix,
       add_expression_data,
   )

mcbo.namespaces
---------------

RDF namespace definitions used throughout MCBO.

.. py:data:: MCBO
   :type: rdflib.Namespace

   The MCBO ontology namespace: ``http://purl.obolibrary.org/obo/MCBO_``

.. py:data:: OBO
   :type: rdflib.Namespace

   The OBO Foundry namespace: ``http://purl.obolibrary.org/obo/``

.. py:data:: RO_HAS_PARTICIPANT
   :type: rdflib.URIRef

   Relation Ontology "has participant" (RO_0000057)

.. py:data:: RO_HAS_QUALITY
   :type: rdflib.URIRef

   Relation Ontology "has quality" (RO_0000086)

.. py:data:: BFO_HAS_PART
   :type: rdflib.URIRef

   BFO "has part" relation (BFO_0000051)

mcbo.graph_utils
----------------

Utilities for creating and loading RDF graphs.

.. py:function:: create_graph() -> rdflib.Graph

   Create a new RDF graph with MCBO namespaces pre-bound.
   
   :returns: An empty rdflib Graph with standard namespace bindings

.. py:function:: load_graph(path: Path) -> rdflib.Graph

   Load an RDF graph from a Turtle file.
   
   :param path: Path to the TTL file
   :returns: The loaded rdflib Graph

.. py:function:: load_graphs(*paths: Path) -> rdflib.Graph

   Load and merge multiple RDF graphs.
   
   :param paths: Paths to TTL files to merge
   :returns: A single merged rdflib Graph

.. py:function:: iri_safe(text: str) -> str

   Convert text to an IRI-safe identifier.
   
   Replaces spaces and special characters with underscores.
   
   :param text: Input text
   :returns: IRI-safe string

.. py:function:: safe_numeric(value, default=None)

   Safely convert a value to a number.
   
   :param value: Value to convert (string, int, float, or None)
   :param default: Default value if conversion fails
   :returns: Converted number or default

.. py:function:: ensure_dir(path: Path) -> Path

   Ensure a directory exists, creating it if necessary.
   
   :param path: Directory path
   :returns: The path (for chaining)

.. py:function:: ensure_parent_dir(path: Path) -> Path

   Ensure the parent directory of a file path exists.
   
   :param path: File path
   :returns: The path (for chaining)

mcbo.csv_to_rdf
---------------

CSV to RDF conversion for bioprocessing metadata.

.. py:function:: convert_csv_to_rdf(csv_file: str, output_file: str, expression_matrix: str = None, expression_dir: str = None) -> rdflib.Graph

   Convert a CSV metadata file to RDF instances.
   
   :param csv_file: Path to input CSV file
   :param output_file: Path for output TTL file
   :param expression_matrix: Optional path to expression matrix CSV
   :param expression_dir: Optional directory with per-study expression CSVs
   :returns: The generated rdflib Graph

.. py:function:: load_expression_matrix(path: Path) -> pandas.DataFrame

   Load a gene expression matrix from CSV.
   
   The CSV should have SampleAccession as the first column and gene symbols
   as remaining columns.
   
   :param path: Path to expression matrix CSV
   :returns: DataFrame with expression data

.. py:function:: add_expression_data(graph: rdflib.Graph, sample_uri: rdflib.URIRef, expression_df: pandas.DataFrame, sample_accession: str)

   Add gene expression measurements to a sample in the graph.
   
   Creates GeneExpressionMeasurement instances for each gene-sample pair.
   
   :param graph: The RDF graph to add to
   :param sample_uri: URI of the sample
   :param expression_df: DataFrame with expression data
   :param sample_accession: Sample accession ID to look up in the DataFrame

Usage Examples
--------------

Creating a Graph from Scratch
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from mcbo import create_graph, MCBO, RDF, RDFS
   
   # Create a new graph with MCBO namespaces
   g = create_graph()
   
   # Add a cell line instance
   cell_line = MCBO["CHO-K1"]
   g.add((cell_line, RDF.type, MCBO.CellLine))
   g.add((cell_line, RDFS.label, Literal("CHO-K1")))
   
   # Serialize to file
   g.serialize("my_instances.ttl", format="turtle")

Loading and Querying Graphs
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from mcbo import load_graph
   from pathlib import Path
   
   # Load evaluation graph
   g = load_graph(Path("data.sample/graph.ttl"))
   
   # Run a SPARQL query
   query = """
       PREFIX mcbo: <http://purl.obolibrary.org/obo/MCBO_>
       SELECT ?process ?type WHERE {
           ?process a ?type .
           ?type rdfs:subClassOf* mcbo:CellCultureProcess .
       }
   """
   results = g.query(query)
   for row in results:
       print(f"{row.process} is a {row.type}")

Converting CSV to RDF
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   from mcbo import convert_csv_to_rdf
   
   # Convert metadata with expression data
   g = convert_csv_to_rdf(
       csv_file=".data/sample_metadata.csv",
       output_file=".data/mcbo-instances.ttl",
       expression_dir=".data/expression/"
   )
   
   print(f"Generated {len(g)} triples")

Module Reference
----------------

For complete API documentation, see the source code in ``python/mcbo/``:

- ``namespaces.py`` - RDF namespace definitions
- ``graph_utils.py`` - Graph loading/creation utilities
- ``csv_to_rdf.py`` - CSV-to-RDF conversion logic
- ``build_graph.py`` - Graph building CLI
- ``run_eval.py`` - SPARQL evaluation
- ``stats_eval_graph.py`` - Statistics generation

