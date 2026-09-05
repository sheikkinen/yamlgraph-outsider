"""The graph owns GitHub: fetch_pr and finalize call gh with exact argument lists; failures are visible."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def gh_env(fake_bin: Path, tmp_path: Path, monkeypatch):
    log = tmp_path / "ghlog"
    log.mkdir()
    monkeypatch.setenv("PATH", f"{fake_bin}:/usr/bin:/bin")
    monkeypatch.setenv("FAKE_LOG_DIR", str(log))
    monkeypatch.setenv("FAKE_GH_JSON", json.dumps({"title": "Add widgets", "body": "Body text.\n\nMore."}))
    monkeypatch.delenv("FAKE_GH_RC", raising=False)
    return log


def _reading():
    return {
        "restatement": "Adds widgets for users.",
        "opinion": "YES",
        "opinion_reason": "Clear enough.",
        "unclear": "",
        "needs": "",
    }


def test_fetch_pr_exact_argv_and_shape(tools, gh_env):
    text = tools.fetch_pr({"pr": "7", "repo": "acme/widgets", "input_path": ""})
    assert text == "# Add widgets\n\nBody text.\n\nMore."
    assert (gh_env / "gh.argv").read_text().splitlines() == ["pr", "view", "7", "-R", "acme/widgets", "--json", "title,body"]


def test_fetch_pr_input_path_never_calls_gh(tools, gh_env, tmp_path):
    f = tmp_path / "in.md"
    f.write_text("# T\n\nB", encoding="utf-8")
    assert tools.fetch_pr({"pr": "", "repo": "", "input_path": str(f)}) == "# T\n\nB"
    assert not (gh_env / "gh.argv").exists()


@pytest.mark.parametrize("pr,repo", [("abc", "acme/widgets"), ("7", "not-a-slug"), ("", "acme/widgets"), ("7", "a/b/c")])
def test_fetch_pr_rejects_invalid_pr_or_repo_before_gh(tools, gh_env, pr, repo):
    with pytest.raises(ValueError):
        tools.fetch_pr({"pr": pr, "repo": repo, "input_path": ""})
    assert not (gh_env / "gh.argv").exists()


def test_fetch_pr_gh_failure_raises(tools, gh_env, monkeypatch):
    monkeypatch.setenv("FAKE_GH_RC", "1")
    with pytest.raises(Exception):
        tools.fetch_pr({"pr": "7", "repo": "acme/widgets", "input_path": ""})


def test_fetch_pr_missing_gh_raises(tools, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(RuntimeError):
        tools.fetch_pr({"pr": "7", "repo": "acme/widgets", "input_path": ""})


def _state(tmp_path, **over):
    s = {
        "pr": "7",
        "repo": "acme/widgets",
        "input_path": "",
        "comment": "false",
        "report_path": str(tmp_path / "out" / "r.md"),
        "pr_text": "# Add widgets\n\nBody text.",
        "reading": _reading(),
    }
    s.update(over)
    return s


def test_finalize_writes_valid_report_and_records_provenance(tools, gh_env, tmp_path, monkeypatch):
    monkeypatch.setenv("PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    result = tools.finalize(_state(tmp_path))
    text = Path(result["report_path"]).read_text(encoding="utf-8")
    assert tools.validate_report_text(text) == "YES"
    assert "provider: anthropic | model: claude-haiku-4-5" in text.splitlines()[1]
    assert result["posted"] is False
    assert not (gh_env / "gh.argv").exists()


def test_finalize_provenance_framework_default_when_omitted(tools, gh_env, tmp_path, clean_env):
    result = tools.finalize(_state(tmp_path))
    text = Path(result["report_path"]).read_text(encoding="utf-8")
    assert "provider: framework-default | model: framework-default" in text.splitlines()[1]


def test_finalize_posts_only_for_strict_true_with_pr_source(tools, gh_env, tmp_path):
    result = tools.finalize(_state(tmp_path, comment="true"))
    assert result["posted"] is True
    argv = (gh_env / "gh.argv").read_text().splitlines()
    assert argv == ["pr", "comment", "7", "-R", "acme/widgets", "--body-file", result["report_path"]]


def test_finalize_input_source_with_comment_true_does_not_post(tools, gh_env, tmp_path):
    with pytest.raises(ValueError):
        tools.finalize(_state(tmp_path, comment="true", pr="", input_path=str(tmp_path / "x.md")))
    assert not (gh_env / "gh.argv").exists()


@pytest.mark.parametrize("bad", ["True", "yes", "1", ""])
def test_finalize_rejects_non_canonical_comment_flag(tools, gh_env, tmp_path, bad):
    with pytest.raises(ValueError):
        tools.finalize(_state(tmp_path, comment=bad))
    assert not (tmp_path / "out" / "r.md").exists()


def test_finalize_comment_failure_raises_and_keeps_report(tools, gh_env, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_GH_RC", "1")
    with pytest.raises(RuntimeError):
        tools.finalize(_state(tmp_path, comment="true"))
    text = (tmp_path / "out" / "r.md").read_text(encoding="utf-8")
    assert tools.validate_report_text(text) == "YES"


def test_finalize_invalid_reading_writes_nothing(tools, gh_env, tmp_path):
    with pytest.raises(ValueError):
        tools.finalize(_state(tmp_path, reading={"restatement": "", "opinion": "YES", "opinion_reason": "r", "unclear": "", "needs": ""}))
    assert not (tmp_path / "out" / "r.md").exists()
    assert not (gh_env / "gh.argv").exists()


def test_finalize_applies_reducer_before_verdict(tools, gh_env, tmp_path):
    reading = _reading() | {"unclear": "“a/b.py” · a?\n“FR-1” · f?\n“glossed (x)” · g?\n“real” · r?"}
    result = tools.finalize(_state(tmp_path, reading=reading, pr_text="# T\n\nglossed (x) and real"))
    assert result["derived_verdict"] == "YES"
    assert result["retained_count"] == 1 and result["demoted_count"] == 3
