# Outsider Doctrine — the context-free reader

## What it is

A reader beside the human reviewer. The reviewer reads a pull request with the
files open and the project in mind. The outsider reads the pull request's
**title and body only**, as someone who has never seen the project, and
reports in four fixed sections: restatement in its own words; could it decide
to merge from the text alone; words and references it could not understand
(≤ 8); what a merge decision would still need (≤ 10).

Its ignorance is the instrument; files, history and project rules would blunt
it.

## Input closure (hard boundary)

- Input: the PR title and body. Nothing else. Not the diff, not the plan, not
  the repository, not this file.
- The model call is a plain provider-API `llm` node with structured output and
  no tools. The graph names no provider and no model; both come from `.env`
  (`PROVIDER`, `<PROVIDER>_MODEL`) through yamlgraph's own resolution. Copying
  `.env.sample` selects the tested sample configuration.

## Three readers of the output

1. **Author** ← section 3 (*could not understand*): gloss or remove each
   phrase. Project shorthand is a pointer into a document the reader has not
   opened; it is not content.
2. **Reviewer** ← section 4 (*would still need*): partition each item into
   *exists but unlinked* and *genuinely absent*. Only someone with the files
   can do this; the outsider must not try.
3. **Derived verdict** (first line, computed in code, never asked of the
   model): YES iff section 3 has at most two **retained** items **and** the
   restatement contains none of `does not say`, `something called`,
   `not stated`, `cannot tell`. The model's own YES/NO is recorded as opinion.
   Models over-flag; the same text can draw different items on different
   runs. Hence advisory, and one run per PR, never a loop to YES.

## The reducer

Before the verdict, code sets aside items the model should not have counted:
a bare identifier (`CAP-12`, `FR-995`, `REQ-YG-001`), a file path, or a phrase
the body itself explains right after quoting it (` (`, ` — `, `: `). Set-aside
items are still printed, under their own heading inside section 4, with the
reason. Nothing is dropped; nothing counts twice.

## Fail closed

The model's answer is a claim. It is validated into typed fields or rejected:
non-empty restatement, YES/NO opinion with a reason, item caps, every unclear
item carrying both a quote and a question. A rejected answer produces no
report, no verdict and no comment. The launcher trusts the graph's exit status
**and** the report's content; either alone is insufficient.

## The record

When asked (`--comment`), the report is posted on the PR as a comment. That
comment — timestamped, attributed, public — is the record. There is no other
log.

## What it is not

Not a reviewer, not a rewriter, not a gate, not automated. It does not
comment unless `--comment` is passed, does not approve, merge, or block.
Output is advisory until a human acts on it.
