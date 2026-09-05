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

## Results

_(filled in after the runs; see `docs/evidence/`)_
