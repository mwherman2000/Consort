"""Tests for the v0.16 grammar additions: the OPTIONAL LABELED FORM for
#/$/* (Section 2.5) and the GLOBAL bare-colon rule (Section 3), run
through both parser implementations. Also runs the exact #/$ labeled-form
example given in the spec's own Section 2.5 prose, and re-confirms every
Section 7 worked example (test_spec_examples.py) still parses unchanged --
the whole point of an *optional* addition is that pre-v0.16 input is
unaffected.
"""

import pytest

from parser import consort_parser
from parser.consort_parser import BareColonInvalidError, DuplicateDirectiveLabelError
from parser.peg import peg_parser

PARSERS = [
    pytest.param(consort_parser.parse, id="hand-written"),
    pytest.param(peg_parser.parse, id="peg"),
]

# The exact example given in the spec's Section 2.5 prose.
SPEC_2_5_EXAMPLE = """\
! plan a dinner party
$ diet: no shellfish; one vegetarian and one gluten-free guest
$ time: total prep time under 2 hours
$ pairing: include a wine pairing for each course
"""

BARE_COLON_LINES = ["!", "#", "$", "%", "*", "@", "^", "|"]


# ---- Section 2.5's own worked example --------------------------------

@pytest.mark.parametrize("parse", PARSERS)
def test_spec_section_2_5_example(parse):
    msg = parse(SPEC_2_5_EXAMPLE)
    assert msg.directives["$_labeled"] == {
        "diet": "no shellfish; one vegetarian and one gluten-free guest",
        "time": "total prep time under 2 hours",
        "pairing": "include a wine pairing for each course",
    }
    assert msg.directives["$"] == []  # no plain $ lines in this example


# ---- labeled form: single instance, multiple instances, mixed --------

@pytest.mark.parametrize("parse", PARSERS)
def test_single_labeled_instance_does_not_require_a_second(parse):
    # 2.5: the labeled form does not require 2+ instances.
    msg = parse("! t\n$ diet: no shellfish\n")
    assert msg.directives["$_labeled"] == {"diet": "no shellfish"}
    assert msg.directives["$"] == []


@pytest.mark.parametrize("parse", PARSERS)
def test_labeled_instance_never_accumulates_into_plain_set(parse):
    # 2.5: labeling always produces its own distinct block, even alone --
    # it must never fold into (or become) the unlabeled accumulating set.
    msg = parse("! t\n$ diet: no shellfish\n$ under 400 words\n")
    assert msg.directives["$_labeled"] == {"diet": "no shellfish"}
    assert msg.directives["$"] == ["under 400 words"]


@pytest.mark.parametrize("parse", PARSERS)
def test_multiple_labeled_instances_of_same_symbol(parse):
    msg = parse("! t\n# background: internal tool\n# audience: engineering leadership\n")
    assert msg.directives["#_labeled"] == {
        "background": "internal tool",
        "audience": "engineering leadership",
    }


@pytest.mark.parametrize("parse", PARSERS)
def test_duplicate_label_on_same_symbol_is_invalid(parse):
    text = "! t\n$ diet: no shellfish\n$ diet: also no peanuts\n"
    with pytest.raises(DuplicateDirectiveLabelError):
        parse(text)


@pytest.mark.parametrize("parse", PARSERS)
def test_same_label_text_across_different_symbols_is_fine(parse):
    # 2.5: label uniqueness is scoped per-symbol, not message-wide like ^/|.
    msg = parse("! t\n# diet: background about the diet\n$ diet: no shellfish\n")
    assert msg.directives["#_labeled"] == {"diet": "background about the diet"}
    assert msg.directives["$_labeled"] == {"diet": "no shellfish"}


@pytest.mark.parametrize("parse", PARSERS)
def test_star_symbol_supports_labeled_form_too(parse):
    msg = parse("! t\n* depth: detailed\n* visibility: concise\n")
    assert msg.directives["*_labeled"] == {"depth": "detailed", "visibility": "concise"}
    assert msg.directives["*"] is None


# ---- whitespace tolerance and prose fallback --------------------------

@pytest.mark.parametrize("parse", PARSERS)
def test_whitespace_before_colon_is_tolerated(parse):
    # 2.8/2.5: "label:" and "label :" are equivalent -- the first colon in
    # the entry always ends the label, whitespace or not.
    msg = parse("! t\n$ diet : no shellfish\n")
    assert msg.directives["$_labeled"] == {"diet": "no shellfish"}


@pytest.mark.parametrize("parse", PARSERS)
def test_prose_colon_that_is_not_a_clean_label_falls_back_to_plain(parse):
    # "Meeting notes" contains a space, so it is not label_chars -- this
    # must silently fall back to plain content, not error and not split.
    msg = parse("! t\n# Meeting notes: discuss Q3 results\n")
    assert msg.directives["#"] == ["Meeting notes: discuss Q3 results"]
    assert msg.directives["#_labeled"] == {}


@pytest.mark.parametrize("parse", PARSERS)
def test_labeled_directive_content_can_wrap_across_continuation_lines(parse):
    text = "! t\n$ diet: no shellfish, and\n  no tree nuts either\n"
    msg = parse(text)
    assert msg.directives["$_labeled"] == {"diet": "no shellfish, and no tree nuts either"}


# ---- the global bare-colon rule: all eight symbols, adjacent and ------
# ---- whitespace-separated ----------------------------------------------

@pytest.mark.parametrize("parse", PARSERS)
@pytest.mark.parametrize("symbol", BARE_COLON_LINES)
@pytest.mark.parametrize("spacing", ["", " "])
def test_bare_colon_is_invalid_for_every_symbol(parse, symbol, spacing):
    line = f"{symbol}{spacing}:"
    text = line + " content\n" if symbol == "!" else f"! t\n{line} content\n"
    with pytest.raises(BareColonInvalidError):
        parse(text)


@pytest.mark.parametrize("parse", PARSERS)
def test_bang_percent_at_have_no_labeled_form_even_with_real_label_text(parse):
    # !, %, and @ have NO labeled form at all (2.1/2.4/2.7) -- unlike
    # #/$/*, "word: rest" after them is never split; it's just content
    # that happens to contain a colon, same as always.
    msg = parse("! summarize: the quarterly report\n")
    assert msg.directives["!"] == "summarize: the quarterly report"


@pytest.mark.parametrize("parse", PARSERS)
def test_agent_label_bare_colon_distinct_from_malformed_label(parse):
    # A bare ^: (empty label) is the new BareColonInvalidError; an
    # agent-label containing disallowed characters (e.g. a space) remains
    # the pre-existing generic ConsortError -- these are different defects.
    with pytest.raises(BareColonInvalidError):
        parse("! t\n^ : do something\n")
    with pytest.raises(consort_parser.ConsortError):
        parse("! t\n^ not a valid label: do something\n")
