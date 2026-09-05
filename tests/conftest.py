"""Shared fixtures: import tools.py by path; fake executables for wrapper tests."""

from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def tools():
    spec = importlib.util.spec_from_file_location("outsider_tools", ROOT / "tools.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["outsider_tools"] = module
    spec.loader.exec_module(module)
    return module


def _write_exe(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    """A PATH directory whose yamlgraph/gh/git record argv and obey env-controlled behaviour."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_exe(
        bin_dir / "yamlgraph",
        'printf "%s\\n" "$@" > "$FAKE_LOG_DIR/yamlgraph.argv"\n'
        'if [ -n "$FAKE_REPORT_BODY" ]; then\n'
        '  for a in "$@"; do case "$a" in report_path=*) mkdir -p "$(dirname "${a#report_path=}")"; printf "%b" "$FAKE_REPORT_BODY" > "${a#report_path=}";; esac; done\n'
        "fi\n"
        'exit "${FAKE_YAMLGRAPH_RC:-0}"\n',
    )
    _write_exe(
        bin_dir / "gh",
        'printf "%s\\n" "$@" >> "$FAKE_LOG_DIR/gh.argv"\n'
        'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then printf "%s" "$FAKE_GH_JSON"; fi\n'
        'exit "${FAKE_GH_RC:-0}"\n',
    )
    _write_exe(
        bin_dir / "git",
        'printf "%s\\n" "$@" >> "$FAKE_LOG_DIR/git.argv"\n'
        'if [ "$1" = "remote" ]; then printf "%s\\n" "${FAKE_GIT_REMOTE:-https://github.com/acme/widgets.git}"; fi\n'
        'exit "${FAKE_GIT_RC:-0}"\n',
    )
    return bin_dir


@pytest.fixture
def demo_dir(tmp_path: Path) -> Path:
    """A copy of the launcher next to a stub graph and a .env, as a user would have it."""
    d = tmp_path / "demo"
    d.mkdir()
    shutil.copy(ROOT / "yamlgraph-outsider", d / "yamlgraph-outsider")
    (d / "graph.yaml").write_text("name: stub\n", encoding="utf-8")
    (d / ".env").write_text("PROVIDER=anthropic\nANTHROPIC_API_KEY=x\n", encoding="utf-8")
    return d


VALID_REPORT = (
    "**Derived verdict:** NO  (rule: ≤ 2 retained unclear items and no hedge in the restatement; computed in code)\\n"
    "<!-- yamlgraph-outsider | source: pr-7 | provider: anthropic | model: m | 2026-01-01T00:00:00+00:00 -->\\n\\n"
    "## 1. In my own words\\n\\nx\\n\\n"
    "## 2. Could I decide whether to merge this from the description alone?\\n\\nNO\\n(model's non-authoritative opinion) y\\n\\n"
    "## 3. Words and references I could not understand\\n\\n- **“a”** · b\\n- **“c”** · d\\n- **“e”** · f\\n\\n"
    "## 4. What a merge decision would still need\\n\\n- [ ] g\\n\\n### Set aside by the reducer (not counted)\\n\\nnone\\n"
)


@pytest.fixture
def run_wrapper(fake_bin: Path, demo_dir: Path, tmp_path: Path):
    import subprocess

    log_dir = tmp_path / "log"
    log_dir.mkdir()

    def _run(*args: str, env_extra: dict[str, str] | None = None, rc: int = 0, report: str | None = VALID_REPORT):
        env = {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "FAKE_LOG_DIR": str(log_dir),
            "FAKE_YAMLGRAPH_RC": str(rc),
        }
        if report is not None:
            env["FAKE_REPORT_BODY"] = report
        env.update(env_extra or {})
        proc = subprocess.run(  # noqa: S603
            [str(demo_dir / "yamlgraph-outsider"), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(demo_dir),
        )
        argv_file = log_dir / "yamlgraph.argv"
        argv = argv_file.read_text(encoding="utf-8").splitlines() if argv_file.exists() else None
        return proc, argv

    return _run


@pytest.fixture
def clean_env(monkeypatch):
    for k in list(os.environ):
        if k in {"PROVIDER"} or k.endswith("_MODEL") or k.endswith("_API_KEY"):
            monkeypatch.delenv(k, raising=False)
    return monkeypatch
