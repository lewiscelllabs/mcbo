# Evaluation (Competency Questions)

This directory contains artifacts used to reproduce the paper’s evaluation:
- the RDF graph used for CQ execution
- the SPARQL queries for CQ1/CQ2/CQ5
- the query outputs

## Directory layout

```

eval/
├── graph.ttl              # OPTIONAL: full evaluation graph (private: not part of repo now)
├── graph.sample.ttl       # PUBLIC: small shareable graph for reviewers
├── queries/
│   ├── cq1.rq
│   ├── cq2.rq
│   └── cq5.rq
├── results/
│   ├── cq1.tsv
│   ├── cq2.tsv
│   └── cq5.tsv
└── README.md

````

## What is eval/graph*.ttl?

The evaluation graph is the *union graph* used by SPARQL engines:

- **Ontology (schema / TBox)**: `ontology/mcbo.owl.ttl`
- **Instances (data / ABox)**: `data/processed/mcbo_instances.ttl`: these data were used to generate the eval in the 

`eval/graph.ttl` is the merged TTL produced from those inputs. It exists so that CQ queries can be executed against a single RDF file.

### Public vs private evaluation data

Some instance data may be non-public (e.g., derived from non-shareable metadata files). In that case:
- `eval/graph.ttl` is generated locally and not committed
- `eval/graph.sample.ttl` is committed and contains a small, shareable subset (or synthetic/redacted example instances) that still exercises CQ1/CQ2/CQ5 end-to-end
- `eval/results/*.tsv` can be published for the sample graph, and optionally also for the private full graph if shareable.

This provides reviewers a runnable path while respecting data restrictions.

## How to run the evaluation (recommended: rdflib)

From the repo root:

```bash
python run_eval.py \
  --ontology ontology/mcbo.owl.ttl \
  --instances data/processed/mcbo_instances.ttl \
  --queries eval/queries \
  --results eval/results
````

If you do not have the private instance data, run on the public sample graph:

```bash
python run_eval.py \
  --graph eval/graph.sample.ttl \
  --queries eval/queries \
  --results eval/results
```

## How to generate eval/graph.ttl

`run_eval.py` can generate a merged graph automatically if you supply `--ontology` and `--instances`.
Optionally, you can also build the graph with ROBOT:

```bash
robot merge \
  --input ontology/mcbo.owl.ttl \
  --input data/processed/mcbo_instances.ttl \
  --output eval/graph.ttl
```

## Alternative runners (optional)

### ROBOT query

```bash
robot query \
  --input eval/graph.sample.ttl \
  --query eval/queries/cq1.rq \
  --output eval/results/cq1.tsv
```

### Apache Jena (arq)

```bash
arq --data eval/graph.sample.ttl --query eval/queries/cq1.rq > eval/results/cq1.tsv
```

(If using `arq`, ensure prefixes are included in the `.rq` files.)

## Notes on CQ semantics

* CQ1 currently returns culture conditions for instances categorized as medium/high/very-high productivity.
* CQ2 returns engineered CHO lines (overexpressesGene) along with maximum observed productivity.
* CQ5 currently reports counts by process type; it is a lightweight proxy for the eventual “differential expression / pathways” CQ.

See the paper’s Evaluation section for interpretation and limitations.

