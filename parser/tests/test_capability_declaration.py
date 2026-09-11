"""Tests for the v0.17 grammar addition: + TOOL / CAPABILITY DECLARATION
(spec 2.12), run through both parser implementations. + reuses the symbol
retired in v0.10 with unrelated, narrower semantics -- these tests only
cover the current (v0.17) grammar, not the v0.10 one.
"""

import pytest

from parser import consort_parser
from parser.consort_parser import BareColonInvalidError
from parser.peg import peg_parser

PARSERS = [
    pytest.param(consort_parser.parse, id="hand-written"),
    pytest.param(peg_parser.parse, id="peg"),
]

# The motivating example from the v0.17 proposal, corrected to use /+
# instead of misusing /* for a capability requirement.
CAPABILITY_EXAMPLE = """\
! research and summarize third-party recordings of an announcement
+ web-search
^ youtube-search-extractor: search YouTube for third-party recordings of the announcement /+ transcription
"""


# ---- the proposal's own motivating example -----------------------------

@pytest.mark.parametrize("parse", PARSERS)
def test_capability_declaration_example(parse):
    msg = parse(CAPABILITY_EXAMPLE)
    assert msg.directives["+"] == ["web-search"]
    entry = msg.entries[0]
    assert entry.label == "youtube-search-extractor"
    # /+ accumulates onto the inherited top-level +, not just its own value.
    assert entry.overrides["+"] == "transcription"


# ---- top-level + accumulates, like # and $ -----------------------------

@pytest.mark.parametrize("parse", PARSERS)
def test_top_level_plus_accumulates(parse):
    msg = parse("! t\n+ web-search\n+ file-read\n")
    assert msg.directives["+"] == ["web-search", "file-read"]


@pytest.mark.parametrize("parse", PARSERS)
def test_single_top_level_plus_is_a_one_item_list(parse):
    msg = parse("! t\n+ web-search\n")
    assert msg.directives["+"] == ["web-search"]


# ---- inline /+ override: accumulate behavior, chaining -----------------

@pytest.mark.parametrize("parse", PARSERS)
def test_inline_override_accumulates_matching_dollar(parse):
    # 2.12: /+ accumulates like /$, not replace like /%//@//*.
    msg = parse(
        "! t\n"
        "+ web-search\n"
        "^ a: do the task /+ file-read\n"
    )
    entry = msg.entries[0]
    assert entry.overrides["+"] == "file-read"


@pytest.mark.parametrize("parse", PARSERS)
def test_multiple_capabilities_via_repeated_override_not_comma(parse):
    # 2.12: repeated /+ overrides, each introduced by its own /,
    # NOT comma-separated within a single /+ value.
    msg = parse("! t\n^ a: do the task /+ web-search /+ file-read\n")
    entry = msg.entries[0]
    assert entry.overrides["+"] == "web-search; file-read"


@pytest.mark.parametrize("parse", PARSERS)
def test_comma_in_a_single_plus_value_is_just_part_of_the_name(parse):
    # A comma inside one /+ value is ordinary text, not a delimiter --
    # same treatment as a comma inside a $ or % value.
    msg = parse("! t\n^ a: do the task /+ web-search, results only\n")
    entry = msg.entries[0]
    assert entry.overrides["+"] == "web-search, results only"


@pytest.mark.parametrize("parse", PARSERS)
def test_plus_override_combines_with_other_overrides(parse):
    msg = parse(
        "! t\n^ a: do the task /$ under 200 words /+ web-search /@ skeptical researcher\n"
    )
    entry = msg.entries[0]
    assert entry.overrides["$"] == "under 200 words"
    assert entry.overrides["+"] == "web-search"
    assert entry.overrides["@"] == "skeptical researcher"


# ---- + has no labeled form (unlike #/$/*) -------------------------------

@pytest.mark.parametrize("parse", PARSERS)
def test_plus_has_no_labeled_form(parse):
    # "web-search: extra note" is NOT split into a label -- + never
    # gained the 2.5 labeled form, it just accumulates like # and $.
    msg = parse("! t\n+ web-search: extra note\n")
    assert msg.directives["+"] == ["web-search: extra note"]


# ---- open-ended vocabulary: any free-text capability name --------------

@pytest.mark.parametrize("parse", PARSERS)
def test_plus_accepts_arbitrary_free_text_capability_names(parse):
    msg = parse("! t\n+ browser automation with headless Chrome\n")
    assert msg.directives["+"] == ["browser automation with headless Chrome"]


# ---- bare-colon rule now covers + (nine symbols total) ------------------

@pytest.mark.parametrize("parse", PARSERS)
@pytest.mark.parametrize("spacing", ["", " "])
def test_bare_colon_invalid_for_plus(parse, spacing):
    line = f"+{spacing}:"
    with pytest.raises(BareColonInvalidError):
        parse(f"! t\n{line} content\n")


# ---- framed form applies to + like any other symbol ---------------------

@pytest.mark.parametrize("parse", PARSERS)
def test_framed_form_applies_to_plus(parse):
    payload = "web-search"
    text = f"! t\n+{len(payload.encode('utf-8'))}:\n{payload}\n"
    msg = parse(text)
    assert msg.directives["+"] == [payload]


# ---- escaping \+ at line start ------------------------------------------

@pytest.mark.parametrize("parse", PARSERS)
def test_escaped_plus_is_literal_text(parse):
    msg = parse("! t\n^ a: do it\n\\+ literal plus, not a directive\n")
    entry = msg.entries[0]
    assert entry.task == "do it + literal plus, not a directive"
    assert msg.directives["+"] == []


# ---- + does not require a top-level ! (unlike ^/|) ----------------------

@pytest.mark.parametrize("parse", PARSERS)
def test_plus_alone_does_not_require_intent(parse):
    # 2.12: + is a capability declaration, not a delegation signal, so it
    # doesn't carry ^/|'s "no ! is invalid" requirement (2.1).
    msg = parse("+ web-search\n% bullet list\n")  # must not raise
    assert msg.directives["+"] == ["web-search"]
    assert msg.directives["!"] is None
