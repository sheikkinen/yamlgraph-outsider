---
name: outsider-view
description: "Read a PR's title and body as someone with no project context and report what was understood, what could not be understood, and what a merge decision would still need. Use when: a PR has just been opened, before human review; an author wants to know which parts of a description only make sense to insiders. Advisory. Input closure: PR title + body ONLY — no files, no tools, no project rules, no chat narrative."
argument-hint: "PR number (or --input <file.md> for any title+body text)"
---

# Outsider view of a PR description

The contract lives in the adjacent `doctrine.md`. This file tells you where
things are and how to invoke them.

## To get an outsider view

```bash
./yamlgraph-outsider <pr-number> [--repo owner/name]   # report under out/
./yamlgraph-outsider <pr-number> --comment             # additionally post it on the PR
./yamlgraph-outsider --input <file.md>                 # any title+body text
```

`--repo` defaults to the `origin` remote of the current directory. The report's
first line is the **derived verdict**, computed in code (≤ 2 retained "could
not understand" items and no hedge in the restatement). Section 2 is the
model's own opinion and is labelled non-authoritative. Section 4 ends with the
items the reducer set aside, and why.

## Bundle map

- `doctrine.md` — what the reader is, its input closure, the three readers of
  its output, the reducer, what it is not
- `graph.yaml`, `prompts/outsider.yaml`, `tools.py` — the pipeline: fetch
  (via `gh`) → one `llm` node → validate, reduce, render, optionally post
- `yamlgraph-outsider` — the launcher: checks `yamlgraph`, `gh`, `git`, `.env`;
  starts the graph; trusts exit status **and** report content
- `fixtures/` — four texts with expectations written before the runs;
  `docs/evidence/` — the recorded runs
- `tests/` — deterministic tests (`pytest`) and paid live tests (`pytest -m live`)

## Not this skill

Reviewing the code, rewriting descriptions, gating merges, reading anything
but the PR's title and body.
