# Alchemist Demo Script

A short, narratable walkthrough showing what each part of the assistant
does. Aim for ~10 minutes total. Open Alchemist in the browser, make sure
the sidebar lists the four tables (`samples`, `expression_long`,
`gene_annotations`, `samples_with_expression`), and click **"+ New
conversation"** before each question.

> Speaker note for the whole demo: Alchemist sits on top of two kinds of
> knowledge about the same data. A **knowledge graph** (the ontology +
> linked records) that captures *what things mean* — e.g. that a "mAb" is
> an antibody. And a **local DuckDB** that captures *what was measured* —
> the rows and columns from every experiment, fast to slice and aggregate.
> The assistant decides which one to reach for, just like a person would.

---

## 1. "What does the assistant *know*?" — firing the knowledge-graph tool

**Ask:**

> Which cell lines or strains have been engineered to produce antibodies?

**What's happening behind the scenes:**

The CSV files only contain raw strings — a column called `ProductType`
with values like `mAb`, `IgG`, `BsAb`, `AMBP`, and so on. There is no
column that says *"is this an antibody?"* That judgment lives in the
**knowledge graph**: when the data was ingested, terms like `mAb` and
`IgG` were classified as `AntibodyProduct`, gene symbols like `AMBP` were
classified as `ProteinProduct`, and the cell lines using them were linked
to those product categories.

So when you ask this in plain English, Alchemist reaches for the
**SPARQL tool** to ask the knowledge graph directly: *"give me every cell
line linked to something classified as an antibody."* That's a one-line
question against the graph, but a fragile guessing game against the raw
CSV (the assistant would have to invent the rule for what "antibody" means
every single time).

**What to point out:**

- The answer comes back clean, with no keyword juggling.
- The same question on a fresh data ingest would still work — the
  classification rule lives in the ontology, not in the prompt.
- This is the value of curating an ontology: *you're teaching the system
  your team's vocabulary once*, and every future question gets the benefit.

---

## 2. "What did the data say?" — firing the SQL tool

**Ask:**

> Across the whole dataset, what's the average culture temperature for
> each process type, how many samples of each are there, and which
> process type runs hottest on average?

**What's happening behind the scenes:**

This is the kind of question a process scientist asks every week:
*group, aggregate, rank.* No vocabulary judgment is needed — just numbers.

Alchemist reaches for the **DuckDB SQL tool**: roughly,
`SELECT ProcessType, COUNT(*), AVG(Temperature) FROM samples GROUP BY ProcessType ORDER BY 3 DESC`,
runs it in milliseconds against the local file, and reads the result back.

> Note: the demo dataset has `ViabilityPercentage`/`TiterValue`/`pH`
> populated, but the real-world corpus in `.data/` doesn't, so we pick
> a column that's well populated in *whichever* dataset you're on.
> `Temperature`, `GlutamineConcentration`, `Productivity` (categorical)
> and `CulturePhase` are safe choices on both.

**What to point out:**

- Fast: the DuckDB file is local, the query is a couple of milliseconds.
- Transparent: the assistant writes real SQL — you can ask "what query did
  you run?" and it will tell you. No black box.
- This is the right tool 80% of the time. The previous question was the
  10% where the ontology earns its keep.

---

## 3. "Show me the structure" — a real plot from a real question

**Ask** (this is what the demo card sends; pasting it manually works too):

> Show me a PCA plot of all CHO cell line samples, colored by which CHO
> cell line each sample is from. Focus on the genes that vary the most
> across these samples (use about 200 of them) so the picture is clean
> and the differences between cell lines stand out.

**What's happening behind the scenes:**

That short question is doing a *lot* of work that you don't see. To
draw this single PCA, Alchemist has to: choose the right table (the
metadata has a convenient pre-joined view, but it has duplicates that
would crash the math); rank every gene by how much it varies across the
selected samples; pull just the top-200 genes for just the CHO samples;
pivot the long-form expression into a samples-by-genes matrix; fill
sparse cells with zeros; z-score each gene (raw expression values span
5 orders of magnitude per sample, so without z-scoring a single
high-magnitude gene dominates PC1 and the picture looks like noise);
run PCA; look up each sample's cell line for color-coding; and draw
the chart.

The user doesn't write any of that. It's baked into the agent's
operating instructions ("default recipe for expression-matrix plots"),
so plain-English questions about expression structure get the
biostatistician-quality preprocessing applied automatically.

The 200-gene cap is also defensive: the plot sandbox refuses to
materialize more than 200,000 rows in any single fetch, and 325 CHO
samples × 200 genes ≈ 65,000 rows — comfortably under the cap and
plenty of dimensionality for PCA.

**Bonus: it remembers the plot.** After the chart appears you can ask
*"which CHO-K1 samples are in the upper-left cluster, and are they from
the same experiment?"* and Alchemist answers without redoing the PCA.
The intermediate (`pca_cho_top200`) is stashed and queryable as a
virtual table for the rest of the conversation.

**What to point out:**

- Open the **Canvas** panel below the chat to show the PCA appear.
- Point out the clustering — or the lack of it — between cell lines.
  That's a real biological signal coming out of one English sentence.
- Mention the **Undo** button if you want to ask a follow-up like
  *"replot it but with 500 genes and log2(value+1) instead of z-score"*
  — undo wipes the previous attempt so the context window doesn't fill up.
- Mention the **model** and **context** pills above the input: the
  assistant is honest about which model is running and how much of its
  attention budget the last turn used.

---

## 4. "Just for these conditions, please" — using the Slice panel

**Setup:** click the small **&#9776;** icon to the left of the input box.
The Slice panel slides in from the right. Find `samples`, then:

- Set `CellLine` &rarr; `CHO-K1`
- Set `ProcessType` &rarr; `FedBatch`

Click **Apply slice**. A cyan badge appears above the input:
`samples.CellLine = 'CHO-K1' AND samples.ProcessType = 'FedBatch'`.

**Ask:**

> Among these runs, what temperatures and glutamine concentrations are
> being used, and how does the Productivity label break down across them?

**What's happening behind the scenes:**

The slice badge is silently appended to your question as a bracketed
instruction: *"\[Active data slice: samples.CellLine = 'CHO-K1' AND
samples.ProcessType = 'FedBatch'. Apply these filters unless I say
otherwise.\]"* The assistant treats it as a default `WHERE` clause for
every query and plot in this turn (and every future turn, until you
clear it).

So instead of describing temperature ranges and Productivity mix across
all 723 samples — most of which are irrelevant to a CHO-K1 fed-batch
campaign — you get the answer for *your* campaign.

**What to point out:**

- The slice is a *natural-language hint*, not a hard filter — if the
  assistant needs to deviate (say, to show a baseline comparison from
  outside the slice) it can. You're guiding it, not handcuffing it.
- Click **Save** in the slice panel to bookmark the slice for next time.
- This is the bridge between "playing with the data" and "writing a
  report": you fix a scope, then have a conversation inside it.

---

## Wrap-up

Three working principles you've just shown:

1. **The ontology earns its keep** when a question hinges on a *concept*
   the team has defined (Question 1).
2. **DuckDB earns its keep** when a question is a *measurement* (Question 2).
3. **The assistant decides** — you don't have to know which is which.
   Plots (Question 3) and slices (Question 4) are accelerators on top.

If a question hangs or errors, it's almost always one of these:

- The assistant is trying to pull *every* row of expression data. The
  plot sandbox now refuses any single `run_sql` returning more than
  200,000 rows, so this fails fast with a clear "pre-filter your query"
  error instead of OOM-ing the server. The fix is one phrase added to
  the question: *"limit to the top N most variable genes"* or *"use just
  the CHO-K1 samples"*.
- The assistant tried to use `samples_with_expression` for PCA and hit
  a duplicate-key error on the pivot. The fix: tell it to use
  `expression_long` directly (the card-4 demo script shows the exact
  wording). The duplicate fan-out comes from multi-run samples in the
  metadata; it's a data shape, not a bug.
- PCA / clustering chokes on missing values. Add *"fill missing values
  with 0"* (or *"drop rows with missing values"*) to the question. The
  PCA demo card already does this.
