MCBO: Mammalian Cell Bioprocessing Ontology
============================================

.. image:: https://github.com/lewiscelllabs/mcbo/actions/workflows/qc.yml/badge.svg
   :target: https://github.com/lewiscelllabs/mcbo/actions/workflows/qc.yml
   :alt: CI/CD

.. image:: https://readthedocs.org/projects/mcbo/badge/?version=latest
   :target: https://mcbo.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://img.shields.io/badge/YouTube-Video-red?logo=youtube
   :target: https://youtu.be/YTvCv-l0ia4
   :alt: YouTube Video

**MCBO** is a hub-and-spoke, IOF-anchored application ontology for mammalian cell bioprocessing
and RNA-seq data curation. It builds on IOF process patterns and BFO foundations, with 
domain-specific extensions that reference OBO ontology classes for measurement, sequencing, 
and biological entities.

The ontology is designed to support:

- RNA-seq analysis and gene expression integration
- Culture condition optimization (temperature, pH, dissolved oxygen)
- Product development for CHO and HEK293 cell bioprocessing
- Integration of curated bioprocessing samples from published studies

**Repository:** https://github.com/lewiscelllabs/mcbo

**New Term Request:** Please visit the `GitHub Issues <https://github.com/lewiscelllabs/mcbo/issues>`_ 
and select "MCBO Term Request" to submit your request.

Citation
--------

Please cite:

   Robasky, K., Morrissey, J., Riedl, M., Dräger, A., Borth, N., Betenbaugh, M. J., & Lewis, N. E. (2025). 
   MCBO: Mammalian Cell Bioprocessing Ontology, A Hub-and-Spoke, IOF-Anchored Application Ontology.
   *ICBO-EAST 2025*.

**Authors:**

- Kimberly Robasky :sup:`1,*` - University of Georgia
- James Morrissey :sup:`2` - Johns Hopkins University
- Markus Riedl :sup:`3` - BOKU University, Vienna
- Andreas Dräger :sup:`4` - Martin Luther University Halle-Wittenberg
- Nicole Borth :sup:`3` - BOKU University, Vienna
- Michael J. Betenbaugh :sup:`2` - Johns Hopkins University
- Nathan E. Lewis :sup:`1` - University of Georgia

:sup:`*` Corresponding author: kimberly.robasky@uga.edu

Evaluation Summary
------------------

MCBO has been evaluated with real curated bioprocessing data:

- **724 cell culture process instances** curated from published studies
- **326 unique bioprocess samples** across culture runs
- **Process breakdown:** Batch (518), Fed-batch (135), Perfusion (49), Unknown (22)
- **75% competency question coverage** with sub-second query times

Competency Questions
--------------------

MCBO is evaluated against 8 competency questions (CQs):

1. **CQ1**: Under what culture conditions (pH, dissolved oxygen, temperature) do the cells reach peak recombinant protein productivity?
2. **CQ2**: Which cell lines have been engineered to overexpress gene Y?
3. **CQ3**: Which nutrient concentrations in cell line K are most associated with viable cell density above Z at day 6 of culture?
4. **CQ4**: How does the expression of gene X vary between clone A and clone B?
5. **CQ5**: What pathways are differentially expressed under Fed-batch vs Perfusion in cell line K?
6. **CQ6**: Which are the top genes correlated with recombinant protein productivity in the stationary phase of all experiments?
7. **CQ7**: Which genes have the highest fold change between cells with viability (>90%) and those without (<50%)?
8. **CQ8**: Which cell lines or subclones are best suited for glycosylation profiles required for therapeutic protein X?

All 8 CQs have SPARQL query implementations in ``eval/queries/``.

License
-------

MCBO is released under the **MIT License**. See the `LICENSE <https://github.com/lewiscelllabs/mcbo/blob/main/LICENSE>`_ file for details.

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart
   workflows
   cli

.. toctree::
   :maxdepth: 2
   :caption: Ontology

   ontology

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api

.. toctree::
   :maxdepth: 2
   :caption: Development

   development

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
