# yamlgraph-outsider

Shows a pull request's title and description to a reader who has never seen
your project, and reports what that reader could not follow. The reader is a
language model that gets only the text — no files, no history, no project
rules. The result is advisory: it tells the author which phrases only make
sense to insiders, before a human reviewer's time is spent.

## Install

```bash
pipx install yamlgraph          # or: pip install yamlgraph
gh auth login                   # GitHub CLI: https://cli.github.com/
git clone https://github.com/sheikkinen/yamlgraph-outsider
cd yamlgraph-outsider
cp .env.sample .env             # add one provider key
```

`.env.sample` is the **tested sample configuration**: Anthropic,
`claude-haiku-4-5`. The pipeline itself names no provider and no model; edit
`.env` to change either (one variable per line — `PROVIDER=openai`,
`OPENAI_API_KEY=…`, `OPENAI_MODEL=…`). Omit `<PROVIDER>_MODEL` and yamlgraph's
own default applies; the report then records `framework-default`, never a
guessed name.

## Use

```bash
./yamlgraph-outsider 123 --repo owner/name          # report under out/
./yamlgraph-outsider 123 --repo owner/name --comment  # and post it on the PR
./yamlgraph-outsider --input some-text.md           # any title + body text
```

`--repo` defaults to the `origin` remote of the current directory.

## Read the report

The first line is the **derived verdict** — computed in code, not asked of the
model: YES if at most two "could not understand" items remain and the
restatement contains no hedge (`does not say`, `not stated`, …). Then four
sections:

1. **In my own words** — the reader's restatement.
2. **Could I decide whether to merge this from the description alone?** — the
   model's own opinion, labelled non-authoritative.
3. **Words and references I could not understand** — one line each: the
   quoted phrase and the question it raised. This is the author's list: gloss
   or remove each one.
4. **What a merge decision would still need** — for the reviewer, who can tell
   *exists but unlinked* from *genuinely absent*. It ends with the items the
   reducer set aside and why.

The **reducer** is a small deterministic rule that runs before the verdict. It
has exactly three tests, applied in this order: (1) the quoted phrase is a bare
ticket-style identifier (`FR-995`, `CAP-12`, `REQ-…`); (2) it is a file path
(contains `/` or ends in `.yaml`, `.yml`, `.py`, `.md`); (3) the text itself
explains it right after quoting it (` (`, ` — `, `: `). A phrase matching any
test is set aside — printed, labelled with the test that matched, not counted.
Nothing else is ever removed.

## Before review

Two readers, deliberately opposite: the human reviewer is given everything —
files, history, the plan. The outsider is given nothing but the description.
Informed readers cannot see private language; the outsider can see nothing
else. Run it once when the PR is opened, gloss what it flags, then ask for
review.

## The record

When you pass `--comment`, the posted comment is the record — timestamped,
attributed, public. There is no other log. One run per PR; do not loop until
it says YES.

## Tests

```bash
pip install --group test        # or: uv sync --group test
pytest                          # deterministic: models, reducer, gh calls, launcher
pytest -m live                  # paid: 4 fixtures × 2 runs on the .env.sample configuration
```

The launcher and `gh` tests run fake executables written as POSIX shell scripts;
on Windows they skip with that reason, and the model, reducer and fixture tests
still run.

Tested against yamlgraph 0.5.17+ (the checkout used was 0.5.24). Fixture
expectations were written before the runs (`fixtures/EXPECTATIONS.md`); the
recorded runs are in `docs/evidence/`. **They did not all match**: on haiku,
the "positive" fixture drew four genuine items and the densest fixture exceeded
the eight-item cap and was rejected. The mismatch is kept as a strict expected
failure in the tests, not edited away.

## Known limits

- Over-flagging is capped by the reducer, not solved; different models draw
  different items from the same text.
- The verdict is advisory. Nothing here gates, approves or blocks a merge.
- Fail-closed: a malformed model answer produces no report and no comment; the
  launcher trusts the graph's exit status **and** the report's content.

## This README, read by the tool

The report is in [`docs/evidence/README-self-run.md`](docs/evidence/README-self-run.md).
On the first version of this text it derived **YES**: one item retained
("the reducer" — the paragraph above was expanded in response), three set
aside (two identifiers, one path). Its header records the input SHA-256,
provider, model, timestamp and source commit.

## Provenance

Built from a spike in [sheikkinen/yamlgraph](https://github.com/sheikkinen/yamlgraph)
(feature request FR-1001; the reader itself is FR-995). MIT.
