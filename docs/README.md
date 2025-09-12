# A Hub-and-Spoke, IOF-Anchored Application Ontology for Mammalian Cell Bioprocessing and RNA-seq Curation

The International Biomanufacturing Network (IBioNe) aims to accelerate discoveries and developments by providing a network of biomanufacturing training and workforce development to educate the next generation of biomanufacturing experts. This effort includes the construction of tools and data for sharing knowledge around bioprocessing with mammalian cells. In this effort, we are developing a central datahub, which we call iBioHub. Currently, knowledge-sharing suffers from several problems, which can be addressed as publically-available data are curated and assembled into iBioNe. There, tools can be provided to explore and model these data to better understand and optimize mammalian biomanufacturing processes. One of the most impactful challenges is linking protein outputs to known CHO cell line genetic variation, phenotypes, and bioreactor conditions. iBioHub will serve public data and tools for overcoming these other other challenges. Indeed, it will also provide first-in-kind curation tools that can be leveraged by LLMs for automating the generation of structured metadata from unstructured publications and electronic notebooks. Here, we report on preliminary work and design plans for a new ontology, the CHO Cell Cultivation Ontology, for organizing and accelerating efforts in AI-ready data to enable our understanding of CHO cell line protein production, facilitating more efficient biomanufacturing of biologics.

## Background and Related work
### Introduction
Motivation: fragmented bioprocess + omics metadata; need for interoperable, computable curation.
Contributions (bullet list): AO design; IOF anchoring; product & assay modeling; extraction pipeline; reference implementation.
Paper roadmap.
 (Cite: ASME/NIST overview, IOF Core.) NISTASME Digital CollectionCEUR-WS
### Related Work
Industrial ontology stacks (IOF, SCRO→AO), NIIMBL BPMO efforts, prior bio/biobank ontologies that demonstrate reuse patterns (OBI/OBIB), and harmonization/bridge-concept methods. CEUR-WS+1NISTNIIMBLBioMed Central

## Ontology Design
Hub-and-spoke architecture; high vs low ontological commitment at application level.
Reuse policy: CLO/CL (cells & lines), OBI (assays), IAO (data), UO (units), SO/GO/PRO (molecular), EFO/ENVO/PATO/ChEBI (factors/chemicals/phenotypes).
 (Cite: ASME/NIST, IOF.) NISTCEUR-WS

## Ontology Scope & Competency Questions
CQ examples (e.g., “Which runs (batch/fed-batch/perfusion) under condition X yielded product Y with expression signature Z?”).
In/out of scope; versioning and governance.

## Ontology Development
### Modeling Decisions
Core classes and object properties (bioprocess → sample → assay → ICE).
Product modeling: hasProduct/sampleContainsProduct, alignment to ChEBI/PRO.
Assay modeling: OBI has specified input/output; data as IAO ICEs.
Cell line/type reuse: CLO↔CL linkage.

| Ontology  | Scope / Coverage          | Example Terms Used                                | Role in MCBO                              |
|-----------|---------------------------|--------------------------------------------------|-------------------------------------------|
| IOF Core  | Industrial processes      | ProductProductionProcess, hasOutput              | Hub anchor for all processes/outputs       |
| CLO       | Cell lines                | CHO-K1                                           | Standardized cell line IDs                 |
| CL        | Cell types                | Chinese hamster ovary cell                       | Biological cell type grounding             |
| OBI       | Assays                    | RNA-seq assay, has specified input/output        | Experimental processes                     |
| EFO/ENVO  | Conditions, environments  | Hypoxia, culture pH                              | Capture experimental context               |
| ChEBI     | Chemicals                 | Glucose, L-glutamine                             | Media components                           |
| UO        | Units                     | gram per liter                                   | Normalize quantitative values              |
| PATO      | Phenotypes                | Cell viability                                   | Describe traits                            |
| SO/GO/PRO | Molecular entities        | Transcript, gene ontology term, IgG protein      | Link outputs to biology                    |

### Implementation 
Protégé modeling; owl:imports.
ROBOT MIREOT pipeline: merge → extract → reduce; seed list; catalog management.
Deliverables (TTL/OWL + modular slim).
 (Cite: IOF RDF, NIIMBL context as relevance.) CEUR-WSNIIMBL

## Evaluation / Case Study (pull from application & impact)
Successfully integrated 725 curated bioprocessing samples from published studies, distributed across Batch (482), Cell Culture (241), Fed-batch (1), and Perfusion (1) processes.

CQ's:
- CQ1 (Culture optimization): 402 results correlating culture conditions with productivity measurements
- CQ2 (CHO engineering): 1 result demonstrating engineered cell line tracking
- CQ5 (Process comparison): 4 process types identified for comparative analysis

Overall Coverage: 75% of competency questions returned results with real data
All competency questions executed within sub-second response times on the 725-sample dataset. Complex multi-table relationship traversals successfully processed culture condition-productivity correlations. Full compatibility with OBO Foundry ontologies (OBI, BFO, ChEBI, GO) ensures interoperability with existing life sciences semantic infrastructure. CQ1 results enable systematic culture optimization analysis across multiple studies; insights not achievable with traditional tabular approaches. The ontology successfully harmonized heterogeneous experimental data into queryable knowledge graphs. Gene expression integration (CQ3) requires additional RNA-seq processing workflows. The current dataset lacks detailed nutrient concentration linkages. Overall, MCBO demonstrates effective bioprocessing data integration with 725 real samples, 75% competency question coverage, and practical analytical capabilities. The framework provides a robust foundation for systematic bioprocess optimization and cross-study comparative analysis.

## Discussion ( pull from application & impact)
Benefits (interoperability, reuse, modularity).
Limits (coverage, term gaps in CLO/OBI, IOF/OBO evolution).
Lessons learned about application-level commitment.

## Conclusion & Future Work
Extensions: downstream purification, proteomics, digital-twin alignment, community release plan.
Invite feedback and contributions (Git repo & issue templates).


