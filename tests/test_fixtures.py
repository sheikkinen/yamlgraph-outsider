"""Fixtures: deterministic derivation over committed evidence, and the paid live runs."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import ROOT

EXPECTED = {"pr-591": "NO", "plain-591": "NO", "pr-591-v2": "NO", "positive": "YES"}
EVIDENCE = ROOT / "docs" / "evidence"
RUNS = (1, 2)


def _evidence_readings():
    files = sorted(EVIDENCE.glob("*-run[12].json"))
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in files}


def _derive(tools, name: str, raw: dict) -> str:
    """What the code says about a recorded raw reading: YES, NO, or REJECTED."""
    source = (ROOT / "fixtures" / f"{name}.md").read_text(encoding="utf-8")
    try:
        reading = tools.parse_reading(raw["reading"])
    except ValueError:
        return "REJECTED"
    reduced = tools.reduce_items(source, reading.unclear)
    return tools.derive_verdict(reading.restatement, reduced.retained)


def test_evidence_complete_and_on_sample_configuration():
    readings = _evidence_readings()
    missing = [f"{n}-run{r}" for n in EXPECTED for r in RUNS if f"{n}-run{r}" not in readings]
    assert not missing, f"no committed evidence for {missing}; run `pytest -m live` after the human spend decision"
    for stem, raw in readings.items():
        assert raw["provider"] == "anthropic" and raw["model"] == "claude-haiku-4-5", stem


def test_derivation_reproduces_recorded_verdicts(tools):
    """The committed report (if any) and the code agree on every recorded run."""
    readings = _evidence_readings()
    assert readings
    for stem, raw in readings.items():
        name = stem.rsplit("-run", 1)[0]
        derived = _derive(tools, name, raw)
        report = EVIDENCE / f"{stem}.md"
        if derived == "REJECTED":
            assert not report.exists(), f"{stem}: rejected reading must produce no report"
        else:
            assert report.exists(), stem
            assert tools.validate_report_text(report.read_text(encoding="utf-8")) == derived, stem


def test_both_runs_agree_per_fixture(tools):
    readings = _evidence_readings()
    for name in EXPECTED:
        results = {_derive(tools, name, readings[f"{name}-run{r}"]) for r in RUNS if f"{name}-run{r}" in readings}
        assert len(results) == 1, (name, results)


@pytest.mark.xfail(
    strict=True,
    reason="2026-09-05 finding on the sample configuration (haiku-4-5, T=0): pr-591 REJECTED both runs "
    "(9 raw items > 8 cap), pr-591-v2 YES both runs, positive NO both runs (4 retained: 'someone writing a graph', "
    "'mercury-2', '\"retire\" rows', 'cross-cutting'). The pre-written NO/NO/NO/YES did not hold; fixture-set "
    "revision is a follow-up, not a silent edit. See fixtures/EXPECTATIONS.md → Results.",
)
def test_prewritten_expectations_hold(tools):
    readings = _evidence_readings()
    for name, expected in EXPECTED.items():
        for r in RUNS:
            assert _derive(tools, name, readings[f"{name}-run{r}"]) == expected, (name, r)


@pytest.mark.live
@pytest.mark.parametrize("run_no", [1, 2])
@pytest.mark.parametrize("name", list(EXPECTED))
def test_live_fixture_twice(tools, name, run_no):
    """Paid. Requires `.env` == `.env.sample` + key. Writes docs/evidence/<name>-run<N>.{json,md}."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        pytest.skip("no .env")
    env = dict(os.environ)
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    if not env.get(f"{env.get('PROVIDER', 'anthropic').upper()}_API_KEY"):
        pytest.skip("no provider key in .env")
    assert env.get("PROVIDER") == "anthropic" and env.get("ANTHROPIC_MODEL") == "claude-haiku-4-5", "live test runs the .env.sample configuration only"

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    report = EVIDENCE / f"{name}-run{run_no}.md"
    reading_dump = EVIDENCE / f"{name}-run{run_no}.json"
    env["OUTSIDER_DUMP_READING"] = str(reading_dump)
    proc = subprocess.run(  # noqa: S603
        [
            "yamlgraph", "graph", "run", str(ROOT / "graph.yaml"),
            "--var", "pr=", "--var", "repo=", "--var", f"input_path={ROOT / 'fixtures' / name}.md",
            "--var", "comment=false", "--var", f"report_path={report}", "--full",
        ],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
    )
    assert reading_dump.exists(), f"no raw reading captured; the model call itself failed:\n{proc.stderr[-2000:]}"
    dump = json.loads(reading_dump.read_text(encoding="utf-8"))
    dump.update({"fixture": name, "run": run_no, "recorded": datetime.now(UTC).isoformat(), "graph_rc": proc.returncode})
    reading_dump.write_text(json.dumps(dump, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if proc.returncode != 0:
        assert not report.exists(), "a failed run must not leave a report"
        assert "reading rejected (fail closed)" in proc.stderr, proc.stderr[-2000:]
        pytest.fail(f"{name} run {run_no}: reading REJECTED (recorded); expected {EXPECTED[name]}")
    verdict = tools.validate_report_text(report.read_text(encoding="utf-8"))
    assert verdict == EXPECTED[name], f"{name} run {run_no}: derived {verdict}, expected {EXPECTED[name]} (recorded)"
