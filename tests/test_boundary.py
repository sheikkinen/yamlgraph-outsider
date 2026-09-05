"""Typed boundary: normalisation, OutsiderReading validation, reducer, verdict, provenance, render."""

from __future__ import annotations

import pytest


# --- normalisation of the two list fields --------------------------------------------------

def test_lines_accepts_list_of_str(tools):
    assert tools.normalise_lines(["a", " b ", ""]) == ["a", "b"]


def test_lines_accepts_json_encoded_list_of_str(tools):
    assert tools.normalise_lines('["a", "b"]') == ["a", "b"]


def test_lines_accepts_newline_delimited_text_with_bullets(tools):
    assert tools.normalise_lines("- a\n* b\n\n• c\n") == ["a", "b", "c"]


def test_lines_empty_string_is_empty_list(tools):
    assert tools.normalise_lines("") == []
    assert tools.normalise_lines(None) == []


@pytest.mark.parametrize(
    "bad",
    ['{"a": 1}', "[1, 2]", '["a", 1]', 42, 3.5, {"a": "b"}, [["a"]], "[not json"],
)
def test_lines_rejects_non_list_json_non_string_members_and_other_containers(tools, bad):
    with pytest.raises(ValueError):
        tools.normalise_lines(bad)


# --- unclear items: quote · question ------------------------------------------------------

def test_split_item_variants(tools):
    assert tools.parse_unclear_line("“foo” · what?") == ("foo", "what?")
    assert tools.parse_unclear_line('"foo" — what?') == ("foo", "what?")
    assert tools.parse_unclear_line("**“foo”** · what?") == ("foo", "what?")


@pytest.mark.parametrize("bad", ["foo", "“foo” · ", " · what?", ""])
def test_split_item_rejects_missing_quote_or_question(tools, bad):
    with pytest.raises(ValueError):
        tools.parse_unclear_line(bad)


# --- OutsiderReading ------------------------------------------------------------------------

def _raw(**over):
    base = {
        "restatement": "This change adds a thing for someone.",
        "opinion": "NO",
        "opinion_reason": "It does not say how it was tested.",
        "unclear": "“alpha” · what is alpha?\n“beta” · what is beta?",
        "needs": "how it was tested\nwhere results are",
    }
    base.update(over)
    return base


def test_parse_reading_happy_path(tools):
    r = tools.parse_reading(_raw())
    assert r.opinion == "NO"
    assert [i.quote for i in r.unclear] == ["alpha", "beta"]
    assert r.needs == ["how it was tested", "where results are"]


def test_parse_reading_accepts_model_dump_object(tools):
    class Obj:
        def model_dump(self):
            return _raw()

    assert tools.parse_reading(Obj()).opinion == "NO"


@pytest.mark.parametrize(
    "over",
    [
        {"restatement": ""},
        {"restatement": "   "},
        {"opinion": "MAYBE"},
        {"opinion": "yes"},
        {"opinion_reason": ""},
        {"unclear": "\n".join(f"“q{i}” · why {i}?" for i in range(9))},
        {"needs": "\n".join(f"n{i}" for i in range(11))},
        {"unclear": "no separator here"},
        {"unclear": '["a", 1]'},
        {"needs": "[1, 2]"},
    ],
)
def test_parse_reading_rejects(tools, over):
    with pytest.raises(ValueError):
        tools.parse_reading(_raw(**over))


def test_parse_reading_rejects_non_mapping(tools):
    with pytest.raises(ValueError):
        tools.parse_reading("not a mapping")
    with pytest.raises(ValueError):
        tools.parse_reading(None)


def test_caps_apply_to_raw_items_before_reduction(tools):
    # nine path-like items would all be demoted, but the raw cap fires first
    raw = _raw(unclear="\n".join(f"“a/b{i}.py” · what?" for i in range(9)))
    with pytest.raises(ValueError):
        tools.parse_reading(raw)


# --- reducer -----------------------------------------------------------------------------------

def _items(tools, *quotes):
    return [tools.UnclearItem(quote=q, question=f"what is {q}?") for q in quotes]


def test_identifier_full_match_demotes(tools):
    red = tools.reduce_items("text", _items(tools, "CAP-12", "FR-995", "REQ-YG-001"))
    assert [d.reason for d in red.demoted] == [tools.DemotionReason.identifier] * 3
    assert red.retained == []


def test_identifier_partial_match_retains(tools):
    red = tools.reduce_items("text", _items(tools, "the CAP-12 census", "FR-995x", "CAP-"))
    assert len(red.retained) == 3 and red.demoted == []


def test_path_slash_or_suffix_demotes_case_insensitively(tools):
    red = tools.reduce_items("text", _items(tools, "capabilities/CAP-*.yaml", "journeys.yaml", "README.MD", "tools.Py", "x.yml"))
    assert all(d.reason == tools.DemotionReason.path for d in red.demoted)
    assert len(red.demoted) == 5


def test_path_near_miss_retains(tools):
    red = tools.reduce_items("text", _items(tools, "yaml", "the markdown", "python tooling"))
    assert len(red.retained) == 3


def test_inline_gloss_following_paren_dash_colon(tools):
    src = "We use the judge (a separate model run). The reducer — a small rule — helps. Ledger: a log file."
    red = tools.reduce_items(src, _items(tools, "the judge", "The reducer", "Ledger"))
    assert [d.reason for d in red.demoted] == [tools.DemotionReason.inline_gloss] * 3


def test_inline_gloss_inside_quote_demotes(tools):
    # the #592 case: the model's quote already contains the parenthetical
    src = "…the repository's independent plan-reviewer (a separate model run that reads only the plan) approved it."
    quote = "the repository's independent plan-reviewer (a separate model run that reads only the plan)"
    red = tools.reduce_items(src, _items(tools, quote))
    assert red.demoted[0].reason == tools.DemotionReason.inline_gloss


def test_inline_gloss_requires_exact_boundary(tools):
    src = "The judge approved it. Later, the judge (a model) said more."
    # first occurrence is not followed by a gloss but the second is: any exact occurrence at the boundary suffices
    red = tools.reduce_items(src, _items(tools, "the judge"))
    assert red.demoted and red.demoted[0].reason == tools.DemotionReason.inline_gloss
    # a quote never followed by a gloss marker is retained
    red2 = tools.reduce_items("The judge approved it.", _items(tools, "The judge"))
    assert red2.retained and not red2.demoted


def test_inline_gloss_quote_absent_from_source_retains(tools):
    red = tools.reduce_items("nothing here", _items(tools, "someone writing a graph"))
    assert [i.quote for i in red.retained] == ["someone writing a graph"]


def test_precedence_identifier_then_path_then_gloss(tools):
    src = "See FR-995 (the reader) and a/b.py (a file)."
    red = tools.reduce_items(src, _items(tools, "FR-995", "a/b.py"))
    assert [d.reason for d in red.demoted] == [tools.DemotionReason.identifier, tools.DemotionReason.path]


def test_reducer_preserves_order_never_drops_or_duplicates(tools):
    src = "alpha (x) beta gamma/d.md delta"
    items = _items(tools, "alpha", "beta", "gamma/d.md", "delta")
    red = tools.reduce_items(src, items)
    assert [i.quote for i in red.retained] == ["beta", "delta"]
    assert [d.item.quote for d in red.demoted] == ["alpha", "gamma/d.md"]
    assert len(red.retained) + len(red.demoted) == len(items)
    assert all(len([d for d in red.demoted if d.item.quote == q]) <= 1 for q in ("alpha", "gamma/d.md"))


def test_named_cases(tools):
    src = "we counted capabilities/CAP-*.yaml files; someone writing a graph; the repository's independent plan-reviewer (a separate model run that reads only the plan) approved"
    red = tools.reduce_items(
        src,
        _items(
            tools,
            "the repository's independent plan-reviewer (a separate model run that reads only the plan)",
            "capabilities/CAP-*.yaml",
            "someone writing a graph",
        ),
    )
    assert [i.quote for i in red.retained] == ["someone writing a graph"]
    assert [d.reason for d in red.demoted] == [tools.DemotionReason.inline_gloss, tools.DemotionReason.path]


# --- verdict ---------------------------------------------------------------------------------

def test_verdict_counts_retained_only(tools):
    retained = _items(tools, "a", "b")
    assert tools.derive_verdict("fine", retained) == "YES"
    assert tools.derive_verdict("fine", _items(tools, "a", "b", "c")) == "NO"


@pytest.mark.parametrize("hedge", ["does not say", "Something Called", "not stated", "cannot tell"])
def test_verdict_hedge_forces_no(tools, hedge):
    assert tools.derive_verdict(f"The text {hedge} who.", []) == "NO"


# --- provenance ------------------------------------------------------------------------------

def test_provenance_four_cases(tools):
    p = tools.provenance({"PROVIDER": "anthropic", "ANTHROPIC_MODEL": "claude-haiku-4-5"})
    assert (p.provider, p.model) == ("anthropic", "claude-haiku-4-5")
    p = tools.provenance({"PROVIDER": "openai"})
    assert (p.provider, p.model) == ("openai", "framework-default")
    p = tools.provenance({})
    assert (p.provider, p.model) == ("framework-default", "framework-default")
    p = tools.provenance({"ANTHROPIC_MODEL": "x"})  # model var without provider is not a configured pair
    assert (p.provider, p.model) == ("framework-default", "framework-default")


# --- render --------------------------------------------------------------------------------------

def test_render_four_sections_and_demoted_subsection(tools):
    reading = tools.parse_reading(_raw(unclear="“alpha (x)” · a?\n“b/c.md” · b?\n“gamma” · g?"))
    red = tools.reduce_items("alpha (x) and b/c.md and gamma", reading.unclear)
    text = tools.render(reading, red, "YES", tools.Provenance(provider="p", model="m"), "pr-1")
    heads = [ln for ln in text.splitlines() if ln.startswith("## ")]
    assert heads == [
        "## 1. In my own words",
        "## 2. Could I decide whether to merge this from the description alone?",
        "## 3. Words and references I could not understand",
        "## 4. What a merge decision would still need",
    ]
    assert text.startswith("**Derived verdict:** YES")
    assert "provider: p | model: m" in text.splitlines()[1]
    assert "### Set aside by the reducer (not counted)" in text
    assert "reason: inline_gloss" in text and "reason: path" in text
    sec3 = text.split("## 3.")[1].split("## 4.")[0]
    assert "gamma" in sec3 and "alpha" not in sec3


def test_validate_report_text_roundtrip(tools):
    reading = tools.parse_reading(_raw())
    red = tools.reduce_items("x", reading.unclear)
    text = tools.render(reading, red, "NO", tools.Provenance(provider="p", model="m"), "pr-1")
    assert tools.validate_report_text(text) == "NO"
    with pytest.raises(ValueError):
        tools.validate_report_text(text.replace("## 4.", "## 5."))
    with pytest.raises(ValueError):
        tools.validate_report_text("garbage")


def test_parse_comment_flag_strict(tools):
    assert tools.parse_comment_flag("true") is True
    assert tools.parse_comment_flag("false") is False
    for bad in ("True", "1", "yes", "", None, "TRUE "):
        with pytest.raises(ValueError):
            tools.parse_comment_flag(bad)
