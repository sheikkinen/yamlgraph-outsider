"""The launcher does prerequisites and start, nothing else; success needs two witnesses."""

from __future__ import annotations

import re
from pathlib import Path

from conftest import ROOT, VALID_REPORT

SCRIPT = (ROOT / "yamlgraph-outsider").read_text(encoding="utf-8")


def test_script_static_shape():
    assert SCRIPT.count("yamlgraph graph run") == 1
    invocation = r"(^|[;&|(]\s*|\$\()\s*{}\s"
    assert not re.search(invocation.format("gh"), SCRIPT, re.M), "the launcher must not call gh"
    assert len(re.findall(invocation.format("git"), SCRIPT, re.M)) == 1, "exactly one git call (remote lookup)"
    assert "--model" not in SCRIPT and "--provider" not in SCRIPT
    assert not re.search(r"claude|gpt-|mistral-|haiku|sonnet", SCRIPT, re.I)


def test_pr_run_passes_exactly_the_five_vars(run_wrapper):
    proc, argv = run_wrapper("7", "--repo", "acme/widgets")
    assert proc.returncode == 0, proc.stderr
    kv = [a for a in argv if "=" in a]
    assert sorted(k.split("=", 1)[0] for k in kv) == ["comment", "input_path", "pr", "repo", "report_path"]
    d = dict(k.split("=", 1) for k in kv)
    assert d["pr"] == "7" and d["repo"] == "acme/widgets" and d["comment"] == "false" and d["input_path"] == ""
    assert re.fullmatch(r"out/7-\d{8}T\d{6}Z\.md", d["report_path"])
    assert "**Derived verdict:** NO" in proc.stdout


def test_repo_defaults_from_git_remote(run_wrapper):
    proc, argv = run_wrapper("7", env_extra={"FAKE_GIT_REMOTE": "git@github.com:acme/gizmos.git"})
    assert proc.returncode == 0, proc.stderr
    assert "repo=acme/gizmos" in argv


def test_no_remote_and_no_repo_fails_before_graph(run_wrapper):
    proc, argv = run_wrapper("7", env_extra={"FAKE_GIT_RC": "2", "FAKE_GIT_REMOTE": ""})
    assert proc.returncode != 0 and argv is None
    assert "--repo" in proc.stderr


def test_input_mode_and_label(run_wrapper, demo_dir):
    (demo_dir / "some-text.md").write_text("# T\n\nB", encoding="utf-8")
    proc, argv = run_wrapper("--input", "some-text.md")
    assert proc.returncode == 0, proc.stderr
    assert "pr=" in argv and "input_path=some-text.md" in argv
    assert any(re.fullmatch(r"report_path=out/some-text-\d{8}T\d{6}Z\.md", a) for a in argv)


def test_comment_true_passes_canonical_string(run_wrapper):
    proc, argv = run_wrapper("7", "--repo", "acme/widgets", "--comment")
    assert proc.returncode == 0, proc.stderr
    assert "comment=true" in argv


def test_input_with_comment_rejected_at_parse(run_wrapper, demo_dir):
    (demo_dir / "t.md").write_text("# T\n\nB", encoding="utf-8")
    proc, argv = run_wrapper("--input", "t.md", "--comment")
    assert proc.returncode == 64 and argv is None


def test_missing_input_file_fails_before_graph(run_wrapper):
    proc, argv = run_wrapper("--input", "nope.md")
    assert proc.returncode != 0 and argv is None


def test_unknown_flag_and_missing_pr(run_wrapper):
    assert run_wrapper("--bogus")[0].returncode == 64
    assert run_wrapper()[0].returncode == 64


def test_each_missing_prerequisite_distinct_exit_and_hint(run_wrapper, fake_bin):
    for tool, code in (("yamlgraph", 70), ("gh", 71), ("git", 72)):
        exe = fake_bin / tool
        exe.rename(fake_bin / f"{tool}.off")
        try:
            proc, argv = run_wrapper("7", "--repo", "acme/widgets")
        finally:
            (fake_bin / f"{tool}.off").rename(exe)
        assert proc.returncode == code, (tool, proc.stderr)
        assert tool in proc.stderr and "install" in proc.stderr.lower()
        assert argv is None


def test_missing_env_fails_before_graph(run_wrapper, demo_dir):
    (demo_dir / ".env").unlink()
    proc, argv = run_wrapper("7", "--repo", "acme/widgets")
    assert proc.returncode == 73 and argv is None
    assert ".env.sample" in proc.stderr


def test_graph_nonzero_fails_despite_valid_report(run_wrapper):
    proc, argv = run_wrapper("7", "--repo", "acme/widgets", rc=1)
    assert proc.returncode != 0 and argv is not None
    assert "graph" in proc.stderr.lower()


def test_graph_zero_but_no_report_fails(run_wrapper):
    proc, _ = run_wrapper("7", "--repo", "acme/widgets", report=None)
    assert proc.returncode != 0
    assert "report" in proc.stderr.lower()


def test_graph_zero_but_invalid_report_fails(run_wrapper):
    proc, _ = run_wrapper("7", "--repo", "acme/widgets", report="**Derived verdict:** MAYBE\\n\\n## 1. x\\n")
    assert proc.returncode != 0


def test_report_missing_section_fails(run_wrapper):
    proc, _ = run_wrapper("7", "--repo", "acme/widgets", report=VALID_REPORT.replace("## 4.", "## 5."))
    assert proc.returncode != 0


def test_report_path_chosen_before_run(run_wrapper):
    _, argv = run_wrapper("7", "--repo", "acme/widgets")
    rp = next(a for a in argv if a.startswith("report_path="))
    assert "claude" not in rp and "anthropic" not in rp
