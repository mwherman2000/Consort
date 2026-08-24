"""Closes specific documented-but-previously-untested gaps in Section 5's
edge-case list, run through both parser implementations:

  - a for-each entry's own {label}.field source being undefined or a
    forward reference (shares validate_reference with plain { } refs,
    but was never exercised through a for-each specifically);
  - the "#123: (no space) is unconditionally framed form, even if a
    hand-typed line only coincidentally starts with digits+colon" gotcha
    (2.10/5) -- and, for contrast, that a digit-colon line with NO
    preceding symbol is never mistaken for one;
  - the documented (not prevented) "Multi-line collision risk" (2.8/5):
    an unescaped continuation line starting with a bare top-level symbol
    really does split the entry, and escaping it really does prevent that;
  - the "no symbols at all" and "one or two symbols only" baseline cases.
"""

import pytest

from parser import consort_parser
from parser.consort_parser import ForwardReferenceError, MalformedFramedFormError, UndefinedLabelError
from parser.peg import peg_parser

PARSERS = [
    pytest.param(consort_parser.parse, id="hand-written"),
    pytest.param(peg_parser.parse, id="peg"),
]


# ---- for-each's own source: undefined / forward reference -----------------

@pytest.mark.parametrize("parse", PARSERS)
def test_for_each_source_undefined_label_is_invalid(parse):
    text = (
        "! draft chapters\n"
        "| draft: write chapters\n"
        "  ^ for-each category in {nonexistent}.outline: draft this chapter\n"
    )
    with pytest.raises(UndefinedLabelError):
        parse(text)


@pytest.mark.parametrize("parse", PARSERS)
def test_for_each_source_forward_reference_is_invalid(parse):
    text = (
        "! draft chapters\n"
        "| draft: write chapters\n"
        "  ^ for-each category in {categorize}.outline: draft this chapter\n"
        "| categorize: derive an outline of chapter categories\n"
    )
    with pytest.raises(ForwardReferenceError):
        parse(text)


# ---- digit-immediately-after-symbol is always framed (2.10/5) ------------

@pytest.mark.parametrize("parse", PARSERS)
def test_digit_colon_immediately_after_symbol_is_framed_not_loose(parse):
    # "#123:" with no space is ALWAYS a framed-form header (2.10's Syntax
    # rule), even though "123" here reads like an issue number rather
    # than a byte count -- a documented, intentional sharp edge, not a bug.
    payload = "needs backporting to the 1.x branch"
    text = f"! track a followup\n#{len(payload.encode('utf-8'))}:\n{payload}\n"
    msg = parse(text)
    assert msg.directives["#"] == [payload]


@pytest.mark.parametrize("parse", PARSERS)
def test_digit_colon_with_wrong_declared_length_fails_loudly(parse):
    # Same gotcha, but nothing after the header actually has 123 bytes --
    # demonstrating this is genuinely consumed AS a framed header (and
    # thus fails) rather than silently falling back to loose-form prose.
    text = "! track a followup\n#123: needs backporting\n"
    with pytest.raises(MalformedFramedFormError):
        parse(text)


@pytest.mark.parametrize("parse", PARSERS)
def test_digit_colon_with_no_preceding_symbol_is_never_framed(parse):
    # By contrast: digits+colon with NO top-level symbol before them
    # (e.g. a plain continuation line) never matches framed-form's own
    # Syntax rule (2.10 requires "symbol, digits, colon") and is just
    # ordinary continuation text.
    text = "! track a followup\n# see issue\n  123: needs backporting\n"
    msg = parse(text)
    assert msg.directives["#"] == ["see issue 123: needs backporting"]


# ---- documented (not prevented) multi-line collision risk (2.8/5) --------

@pytest.mark.parametrize("parse", PARSERS)
def test_unescaped_symbol_at_start_of_wrapped_continuation_splits_the_entry(parse):
    text = (
        "! research a library\n"
        "^ researcher: research it, checking\n"
        "$ licensing terms before reporting back\n"
    )
    msg = parse(text)
    assert len(msg.entries) == 1
    assert msg.entries[0].task == "research it, checking"
    assert msg.directives["$"] == ["licensing terms before reporting back"]


@pytest.mark.parametrize("parse", PARSERS)
def test_escaping_the_symbol_prevents_the_split(parse):
    text = (
        "! research a library\n"
        "^ researcher: research it, checking\n"
        "\\$ licensing terms before reporting back\n"
    )
    msg = parse(text)
    assert len(msg.entries) == 1
    assert msg.entries[0].task == "research it, checking $ licensing terms before reporting back"
    assert msg.directives["$"] == []


# ---- baseline cases: no symbols, and one or two symbols only -------------

@pytest.mark.parametrize("parse", PARSERS)
def test_no_symbols_at_all_is_ordinary_text(parse):
    msg = parse("just an ordinary English request with no Consort symbols at all\n")
    assert msg.entries == []
    assert msg.directives == {"!": None, "#": [], "$": [], "%": None, "*": None, "@": None}
    assert msg.references == {}
    assert msg.warnings == []


@pytest.mark.parametrize("parse", PARSERS)
def test_minimal_one_or_two_symbols_is_valid(parse):
    msg = parse("! summarize this document\n% bullet list\n")
    assert msg.directives["!"] == "summarize this document"
    assert msg.directives["%"] == "bullet list"
    assert msg.entries == []
