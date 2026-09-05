# Recorded runs

Every file here is the raw record of one model call on the sample
configuration (`.env.sample`: Anthropic, `claude-haiku-4-5`, temperature 0).

- `<fixture>-run<N>.json` — the model's answer exactly as it arrived (before
  validation), plus the configured provider and model, the fixture name, run
  number, timestamp, and the pipeline's exit code. A rejected answer still has
  a `.json`; it has no `.md`.
- `<fixture>-run<N>.md` — the rendered report, when the answer validated.
- `README-self-run.md` — the project README read by the tool before
  publication; the header carries the input's SHA-256.

Expectations were written before any run: `../../fixtures/EXPECTATIONS.md`.
Where they did not hold, that file says so; the records here are not edited.
