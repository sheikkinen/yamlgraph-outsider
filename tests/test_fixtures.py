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


def _evidence_readings():
    files = sorted(EVIDENCE.glob("*-run[12].json"))
    return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in files}


def test_committed_structured_outputs_derive_expected_sequence(tools):
    readings = _evidence_readings()
    missing = [f"{name}-run{n}" for name in EXPECTED for n in (1, 2) if f"{name}-run{n}" not in readings]
    assert not missing, f"no committed evidence for {missing}; run `pytest -m live` after the human spend decision"
    for name, expected in EXPECTED.items():
        source = (ROOT / "fixtures" / f"{name}.md").read_text(encoding="utf-8")
        for n in (1, 2):
            raw = readings[f"{name}-run{n}"]
            reading = tools.parse_reading(raw["reading"])
            reduced = tools.reduce_items(source, reading.unclear)
            assert tools.derive_verdict(reading.restatement, reduced.retained) == expected, (name, n)


def test_evidence_records_sample_configuration(tools):
    readings = _evidence_readings()
    if not readings:
        pytest.fail("no committed evidence; run `pytest -m live` after the human spend decision")
    for stem, raw in readings.items():
        assert raw["provider"] == "anthropic" and raw["model"] == "claude-haiku-4-5", stem


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
    assert proc.returncode == 0, proc.stderr[-2000:]
    text = report.read_text(encoding="utf-8")
    verdict = tools.validate_report_text(text)
    dump = json.loads(reading_dump.read_text(encoding="utf-8"))
    dump.update({"fixture": name, "run": run_no, "recorded": datetime.now(UTC).isoformat()})
    reading_dump.write_text(json.dumps(dump, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert verdict == EXPECTED[name], text
