# Fixture expectations — written before any run against the sample configuration

Configuration under test: exactly `.env.sample` (Anthropic, `claude-haiku-4-5`,
temperature 0), with the reducer applied. Each fixture is run **twice**; the
derived verdict must match on both passes. Raw outputs are committed under
`docs/evidence/` after the runs, never before.

| Fixture | Expected derived verdict | Why |
|---|---|---|
| `pr-591.md` | NO | dense project shorthand with no glosses; > 2 items should survive the reducer |
| `plain-591.md` | NO | plain-language rewrite, but still names plans and sections the reader was not part of; the earlier spike drew 8 items on sonnet |
| `pr-591-v2.md` | NO | second rewrite of the same PR; earlier spike drew 7 items |
| `positive.md` | YES | glossed throughout; earlier spike's items were paths, identifiers and glossed phrases — exactly what the reducer demotes |

Derived rule (computed in code, not asked of the model): YES iff at most two
retained "could not understand" items and the restatement contains none of
`does not say`, `something called`, `not stated`, `cannot tell`.

Prior evidence (different configuration, no reducer): sonnet-4-5 at T=0 drew
7 then 6 items on `positive.md` — all paths/identifiers/glossed — and NO on all
four. It does not establish the result above; the runs recorded in
`docs/evidence/` do.

## Results — 2026-09-05, `.env.sample` configuration (anthropic / claude-haiku-4-5, T=0), reducer on

Raw readings and reports: `docs/evidence/<fixture>-run{1,2}.{json,md}`. Both
runs agreed on every fixture. **The pre-written sequence did not hold.**

| Fixture | Expected | Run 1 | Run 2 | Raw items | What happened |
|---|---|---|---|---|---|
| `pr-591.md` | NO | REJECTED | REJECTED | 9 | The model listed nine "could not understand" items; the cap is eight. Fail-closed: no report. The text is that dense. |
| `plain-591.md` | NO | NO | NO | 4 | Hedge in the restatement (`does not say`); items are real ("capabilities", "shape anchors"). |
| `pr-591-v2.md` | NO | **YES** | **YES** | 1 | One item ("Someone writing a graph"), no hedge. The second rewrite passes on haiku. |
| `positive.md` | YES | **NO** | **NO** | 5 | 4 retained ("someone writing a graph", "mercury-2", "\"retire\" rows", "cross-cutting"), 1 demoted (`FR-990`, identifier) — and a `does not say` hedge in the restatement. |

Reading the raw output: haiku is *not* over-flagging paths — the reducer set
aside exactly one item across eight runs (`FR-990`). Its items are phrases the
text genuinely leaves undefined ("mercury-2" is named but never said to be a
model; "cross-cutting" is used without saying in what sense). The `positive`
fixture was written to pass sonnet's failure mode, not to be fully glossed.

Consequences, recorded and not silently fixed: `tests/test_fixtures.py::
test_prewritten_expectations_hold` is a **strict xfail** carrying this finding;
the deterministic tests assert only that the code reproduces the recorded
verdicts and that both runs agree. Revising the fixture set (a genuinely glossed
positive, a pr-591 that fits under the cap) is follow-up work under its own
expectations, not an edit to these.
