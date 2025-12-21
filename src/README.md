# QC reports

The following reports were run and placed under reports/robot/; QC passes if every report is empty; run in github actions on every check-in:

```
java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/orphan_classes.rq \
reports/robot/orphan_classes.tsv

 java -jar .robot/robot.jar query \
  --input ontology/mcbo.owl.ttl \
  --query sparql/duplicate_labels.rq \
reports/robot/duplicate_labels.tsv

 java -jar .robot/robot.jar query \ \
  --input ontology/mcbo.owl.ttl \
  --query sparql/missing_definitions.rq \
reports/robot/missing_definitions.tsv

```

**Verification***
```
# Verify ontology parses
python -c "from rdflib import Graph; g = Graph(); g.parse('ontology/mcbo.owl.ttl', format='turtle'); print(f'Parsed {len(g)} triples')"

# Verify evaluation reproducibility
# Build and evaluate demo data
bash scripts/run_all_checks.sh

# Or manually:
python scripts/build_graph.py build --studies-dir data.sample/studies --output data.sample/graph.ttl
python run_eval.py --graph data.sample/graph.ttl --queries eval/queries --results data.sample/results

# Verify sample counts (real data)
python scripts/stats_eval_graph.py --graph .data/graph.ttl > .data/STATS.txt
```
