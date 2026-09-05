"""yamlgraph-outsider — the graph's Python tools.

fetch_pr : PR title + body via `gh` (argument list, no shell), or a fixture file.
finalize : validate the model's structured answer into typed models, reduce, derive
           the verdict in code, render four sections, write the report, and — when
           asked — post it on the PR via `gh`. Anything malformed raises; nothing
           is written or posted from an invalid reading.

The graph names no provider or model; the report records what `.env` configured.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

HEDGES = ("does not say", "something called", "not stated", "cannot tell")
MAX_UNCLEAR = 8
MAX_NEEDS = 10
FRAMEWORK_DEFAULT = "framework-default"

_PR_RE = re.compile(r"^\d{1,7}$")
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_IDENTIFIER_RE = re.compile(r"^(CAP-\d+|FR-\d+|REQ-[A-Za-z0-9-]+)$")
_PATH_SUFFIXES = (".yaml", ".yml", ".py", ".md")
_GLOSS_MARKERS = (" (", " — ", ": ")
_ITEM_SEPARATORS = (" · ", " — ", " -- ")
_QUOTE_CHARS = "“”\"'`* "

HEADINGS = (
    "## 1. In my own words",
    "## 2. Could I decide whether to merge this from the description alone?",
    "## 3. Words and references I could not understand",
    "## 4. What a merge decision would still need",
)
DEMOTED_HEADING = "### Set aside by the reducer (not counted)"


# --- typed models --------------------------------------------------------------------------------


class UnclearItem(BaseModel):
    quote: str = Field(min_length=1)
    question: str = Field(min_length=1)


class OutsiderReading(BaseModel):
    restatement: str = Field(min_length=1)
    opinion: Literal["YES", "NO"]
    opinion_reason: str = Field(min_length=1)
    unclear: list[UnclearItem] = Field(max_length=MAX_UNCLEAR)
    needs: list[str] = Field(max_length=MAX_NEEDS)


class DemotionReason(StrEnum):
    identifier = "identifier"
    path = "path"
    inline_gloss = "inline_gloss"


class DemotedItem(BaseModel):
    item: UnclearItem
    reason: DemotionReason


class ReducedReading(BaseModel):
    retained: list[UnclearItem]
    demoted: list[DemotedItem]


class Provenance(BaseModel):
    provider: str
    model: str


# --- normalisation (provider type lie: lists arrive as JSON strings or newline text) -------------


def normalise_lines(value: Any) -> list[str]:
    """Accept list[str], a JSON-encoded list[str], or newline-delimited text. Reject the rest."""
    if value is None:
        return []
    if isinstance(value, list):
        if not all(isinstance(x, str) for x in value):
            raise ValueError("list field has non-string members")
        return [x.strip() for x in value if x.strip()]
    if not isinstance(value, str):
        raise ValueError(f"list field has unsupported type {type(value).__name__}")
    text = value.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"list field looks like JSON but does not parse: {e}") from e
        return normalise_lines(parsed)
    if text.startswith("{"):
        raise ValueError("list field is a JSON object, not a list")
    return [ln.strip().lstrip("-*• ").strip() for ln in text.splitlines() if ln.strip()]


def parse_unclear_line(raw: str) -> tuple[str, str]:
    """One item: “quoted phrase” · question. Both halves required."""
    for sep in _ITEM_SEPARATORS:
        if sep in raw:
            q, _, rest = raw.partition(sep)
            quote, question = q.strip().strip(_QUOTE_CHARS), rest.strip()
            if quote and question:
                return quote, question
            break
    raise ValueError(f"unclear item lacks a quote or a question: {raw!r}")


def parse_reading(raw: Any) -> OutsiderReading:
    """The model's answer is a claim; it becomes an OutsiderReading or raises ValueError."""
    if not isinstance(raw, dict):
        dump = getattr(raw, "model_dump", None)
        raw = dump() if callable(dump) else None
    if not isinstance(raw, dict):
        raise ValueError("reading is not a mapping")
    try:
        unclear_lines = normalise_lines(raw.get("unclear"))
        needs = normalise_lines(raw.get("needs"))
        if len(unclear_lines) > MAX_UNCLEAR:
            raise ValueError(f"{len(unclear_lines)} unclear items > {MAX_UNCLEAR}")
        if len(needs) > MAX_NEEDS:
            raise ValueError(f"{len(needs)} needs > {MAX_NEEDS}")
        items = [UnclearItem(quote=q, question=qq) for q, qq in map(parse_unclear_line, unclear_lines)]
        return OutsiderReading(
            restatement=str(raw.get("restatement") or "").strip(),
            opinion=str(raw.get("opinion") or "").strip(),  # exact "YES"/"NO" only
            opinion_reason=str(raw.get("opinion_reason") or "").strip(),
            unclear=items,
            needs=needs,
        )
    except ValueError as e:  # pydantic.ValidationError is a ValueError
        raise ValueError(f"reading rejected (fail closed): {e}") from e


# --- reducer ------------------------------------------------------------------------------------------


def _is_glossed(source: str, quote: str) -> bool:
    for start in (m.start() for m in re.finditer(re.escape(quote), source)):
        tail = source[start + len(quote) :]
        if tail.startswith(_GLOSS_MARKERS):
            return True
    for marker in _GLOSS_MARKERS:
        if marker in quote:
            prefix = quote.split(marker, 1)[0]
            if prefix and (prefix + marker) in source:
                return True
    return False


def classify(source: str, item: UnclearItem) -> DemotionReason | None:
    """Precedence: identifier → path → inline_gloss; None means retain."""
    q = item.quote
    if _IDENTIFIER_RE.match(q):
        return DemotionReason.identifier
    if "/" in q or q.lower().endswith(_PATH_SUFFIXES):
        return DemotionReason.path
    if _is_glossed(source, q):
        return DemotionReason.inline_gloss
    return None


def reduce_items(source: str, items: list[UnclearItem]) -> ReducedReading:
    retained: list[UnclearItem] = []
    demoted: list[DemotedItem] = []
    for item in items:
        reason = classify(source, item)
        if reason is None:
            retained.append(item)
        else:
            demoted.append(DemotedItem(item=item, reason=reason))
    return ReducedReading(retained=retained, demoted=demoted)


def derive_verdict(restatement: str, retained: list[UnclearItem]) -> str:
    low = restatement.casefold()
    return "YES" if len(retained) <= 2 and not any(h in low for h in HEDGES) else "NO"


# --- provenance, comment flag ---------------------------------------------------------------------


def provenance(env: Any) -> Provenance:
    """Record what .env configured — never an inferred effective model name."""
    provider = str(env.get("PROVIDER") or "").strip()
    if not provider:
        return Provenance(provider=FRAMEWORK_DEFAULT, model=FRAMEWORK_DEFAULT)
    model = str(env.get(f"{provider.upper()}_MODEL") or "").strip()
    return Provenance(provider=provider, model=model or FRAMEWORK_DEFAULT)


def parse_comment_flag(value: Any) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"comment must be exactly 'true' or 'false', got {value!r}")


# --- render + validate ------------------------------------------------------------------------------


def render(reading: OutsiderReading, reduced: ReducedReading, verdict: str, prov: Provenance, source_label: str) -> str:
    lines = [
        f"**Derived verdict:** {verdict}  (rule: ≤ 2 retained unclear items and no hedge in the restatement; computed in code)",
        f"<!-- yamlgraph-outsider | source: {source_label} | provider: {prov.provider} | model: {prov.model} | {datetime.now(UTC).isoformat()} -->",
        "",
        HEADINGS[0],
        "",
        reading.restatement,
        "",
        HEADINGS[1],
        "",
        reading.opinion,
        f"(model's non-authoritative opinion) {reading.opinion_reason}",
        "",
        HEADINGS[2],
        "",
        *([f"- **“{i.quote}”** · {i.question}" for i in reduced.retained] or ["nothing"]),
        "",
        HEADINGS[3],
        "",
        *([f"- [ ] {n}" for n in reading.needs] or ["nothing"]),
        "",
        DEMOTED_HEADING,
        "",
        *([f"- **“{d.item.quote}”** · {d.item.question} — reason: {d.reason.value}" for d in reduced.demoted] or ["none"]),
        "",
    ]
    return "\n".join(lines)


def validate_report_text(text: str) -> str:
    """A rendered report is itself checked: verdict line, four headings once and in order. Returns the verdict."""
    first = text.split("\n", 1)[0]
    m = re.match(r"^\*\*Derived verdict:\*\* (YES|NO)\b", first)
    if not m:
        raise ValueError("report does not start with a derived verdict")
    heads = [ln for ln in text.splitlines() if ln.startswith("## ")]
    if heads != list(HEADINGS):
        raise ValueError(f"report headings are {heads!r}, expected exactly the four in order")
    if DEMOTED_HEADING not in text:
        raise ValueError("report lacks the reducer subsection")
    return m.group(1)


# --- graph tools -------------------------------------------------------------------------------------


def _pr_and_repo(state: dict[str, Any]) -> tuple[str, str]:
    pr = str(state.get("pr") or "").strip()
    repo = str(state.get("repo") or "").strip()
    if not _PR_RE.match(pr):
        raise ValueError(f"pr must be a number, got {pr!r}")
    if not _REPO_RE.match(repo):
        raise ValueError(f"repo must be owner/name, got {repo!r}")
    return pr, repo


def _gh() -> str:
    path = shutil.which("gh")
    if not path:
        raise RuntimeError("gh CLI not found on PATH")
    return path


def fetch_pr(state: dict[str, Any]) -> str:
    """`# <title>\\n\\n<body>` via gh, or the fixture file named by input_path. Nothing else enters the model."""
    path = str(state.get("input_path") or "").strip()
    if path:
        return Path(path).read_text(encoding="utf-8")
    pr, repo = _pr_and_repo(state)
    out = subprocess.run(  # noqa: S603
        [_gh(), "pr", "view", pr, "-R", repo, "--json", "title,body"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    d = json.loads(out)
    return f"# {d['title']}\n\n{d['body']}"


def finalize(state: dict[str, Any]) -> dict[str, Any]:
    """Validate → reduce → derive → render → write → (post). Raises before writing on any invalid input."""
    want_comment = parse_comment_flag(state.get("comment"))
    is_pr = bool(str(state.get("pr") or "").strip())
    if want_comment and not is_pr:
        raise ValueError("comment=true requires a PR source, not --input")
    if is_pr:
        pr, repo = _pr_and_repo(state)
    reading = parse_reading(state.get("reading"))
    source_text = str(state.get("pr_text") or "")
    reduced = reduce_items(source_text, reading.unclear)
    verdict = derive_verdict(reading.restatement, reduced.retained)
    prov = provenance(os.environ)
    label = f"pr-{pr}" if is_pr else Path(str(state.get("input_path"))).stem
    report = render(reading, reduced, verdict, prov, label)
    validate_report_text(report)

    out = Path(str(state["report_path"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")

    dump_path = os.environ.get("OUTSIDER_DUMP_READING")
    if dump_path:
        Path(dump_path).write_text(
            json.dumps({"reading": _raw_dump(state.get("reading")), "provider": prov.provider, "model": prov.model}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    posted = False
    if want_comment:
        proc = subprocess.run(  # noqa: S603
            [_gh(), "pr", "comment", pr, "-R", repo, "--body-file", str(out)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"gh pr comment failed (rc={proc.returncode}); report kept at {out}: {proc.stderr.strip()}")
        posted = True
    return {
        "derived_verdict": verdict,
        "model_opinion": reading.opinion,
        "retained_count": len(reduced.retained),
        "demoted_count": len(reduced.demoted),
        "needs_count": len(reading.needs),
        "provider": prov.provider,
        "model": prov.model,
        "report_path": str(out),
        "posted": posted,
    }


def _raw_dump(reading: Any) -> Any:
    if isinstance(reading, dict):
        return reading
    dump = getattr(reading, "model_dump", None)
    return dump() if callable(dump) else reading
