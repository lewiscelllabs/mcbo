# Paper Reviews

## Paper Information
- **Paper ID:** 23  
- **Title:** MCBO: Mammalian Cell Bioprocessing Ontology, A Hub-and-Spoke, IOF-Anchored Application Ontology  
- **Track:** ICBO-EAST

---

## Reviewer #1

### Review
The authors describe the development of the Mammalian Cell Bioprocessing Ontology (MCBO), a novel ontology designed to support a network of biomanufacturing training and knowledge sharing.

**Issues & Suggestions**
1. The MCBO classification/hierarchy has issues between subclasses and parents.  
   - Example: a dataset is an information content entity (ICE) but does not fall under ICE in BFO.
   - Some terms need reclassification under BFO.
2. Reclassify all terms under the BFO hierarchy to improve interoperability.
3. Reorganize MCBO following *Building Ontologies with BFO* and OBO principles.
4. No textual or logical definitions are provided for terms in the hierarchy.
   - Existing relation classes (e.g., Relations Ontology) should be reused before creating new ones.

### Recommendation
**Borderline**

---

## Reviewer #2

### Review
This paper describes ontology work related to industrial manufacturing processes, especially CHO cell-based biologics production. The work is innovative, as no prior ontology exists.

**Strengths**
- Use of IOF and BFO
- Clear industrial use case

**Weaknesses**
1. Ontology development is only briefly described; only one figure is provided.
   - Example issue: `has culture condition` links a process to a quality, which conflicts with BFO.
2. Section order does not follow LOT ontology development methodology.
3. Evaluation claims (724 curated samples, CQ answers) are not supported with data or SPARQL queries.
4. Few textual definitions are provided for ontology terms.
5. Key semantic design patterns are missing.
6. Grammar and wording issues.
7. License inconsistency: “permissive license” vs MIT License.
8. LLM usage claims are aspirational and unsupported.

### Recommendation
**Borderline**

---

## Reviewer #3

### Review
The paper presents an initial version of the MCBO and its applications, with use cases and future outlooks for biopharmaceutical manufacturing optimization.

**Strengths**
- Good awareness and reuse of existing ontologies
- Strong alignment with IOF BMIC direction

**Novelty**
- Seminal use of IOF ontology
- Encouraging future development and community involvement

### Feedback
- Consider using “biopharmaceutical manufacturing” instead of “biomanufacturing.”
- Reevaluate use of IOF Product Production Process (PPP) for manufacturing processes.
- Some processes may fit better under IOF Manufacturing Process or Planned Process.
- Clarify whether all Cell Culture Processes are Mammalian Cell Bioprocesses.
- Distinguish mammalian vs non-mammalian (e.g., yeast) processes.

### Recommendation
**Borderline**
