"""Tests for the parts of the Consort grammar beyond { } label references:
framed-form payloads (2.10), multi-line loose-form continuation (3),
for-each %item-var% interpolation (2.8), and structural validation
(agent-label uniqueness, missing !, and ^/| mixed at the top level)."""

import pytest

from parser.consort_parser import (
    DuplicateLabelError,
    MalformedFramedFormError,
    MissingIntentError,
    MixedTopLevelDelegationError,
    find_item_var_refs,
    interpolate_for_each,
    parse,
)


def test_framed_top_level_directive():
    # Spec Example A: a framed # context block, byte-exact and opaque.
    payload = "Expected: 12.50, Actual: 12.495"
    text = (
        f"! locate root cause of a failing test\n"
        f"#{len(payload.encode('utf-8'))}:\n{payload}\n"
        f"$ do not modify any files\n"
    )
    msg = parse(text)
    assert msg.directives["!"] == "locate root cause of a failing test"
    assert msg.directives["#"] == [payload]
    assert msg.directives["$"] == ["do not modify any files"]


def test_framed_entry_extracts_label_but_keeps_task_opaque():
    # Spec 2.8: "Framed form: unchanged mechanism" -- the label is still
    # used for addressing, but the task text is never re-scanned.
    payload = "polly-researcher: research Polly and report NuGet version"
    text = f"! research a library\n^{len(payload.encode('utf-8'))}:\n{payload}\n"
    msg = parse(text)
    entry = msg.entries[0]
    assert entry.framed is True
    assert entry.label == "polly-researcher"
    assert entry.task == "research Polly and report NuGet version"


def test_framed_entry_content_never_scanned_for_label_references():
    # Even an undefined-looking {ref} inside a framed payload must not be
    # resolved or raise -- 2.11's "Interaction with framed form".
    payload = "finalizer: keep {nonexistent} verbatim"
    text = f"! test framed opacity\n|{len(payload.encode('utf-8'))}:\n{payload}\n"
    msg = parse(text)  # must not raise UndefinedLabelError
    assert msg.references["finalizer"] == []


def test_malformed_framed_length_raises():
    payload = "short"
    declared_len = len(payload.encode("utf-8")) + 100
    text = f"! t\n#{declared_len}:\n{payload}\n"
    with pytest.raises(MalformedFramedFormError):
        parse(text)


def test_multiline_context_directive_accumulates_across_lines():
    text = (
        "! research three independent C# libraries\n"
        "# evaluating for a .NET solution; libraries are unrelated\n"
        "  no shared state between the research tasks\n"
        "^ polly-researcher: research Polly\n"
    )
    msg = parse(text)
    assert msg.directives["#"] == [
        "evaluating for a .NET solution; libraries are unrelated "
        "no shared state between the research tasks"
    ]


def test_override_value_wraps_across_a_continuation_line():
    # Spec Example C's mediatr-researcher entry.
    text = (
        "! research three independent C# libraries\n"
        "^ mediatr-researcher: research MediatR /$ flag any recent licensing\n"
        "  changes explicitly /% bullet list, not prose\n"
    )
    msg = parse(text)
    entry = msg.entries[0]
    assert entry.overrides["$"] == "flag any recent licensing changes explicitly"
    assert entry.overrides["%"] == "bullet list, not prose"


def test_duplicate_agent_label_is_invalid():
    text = "! t\n^ a: do x\n^ a: do y\n"
    with pytest.raises(DuplicateLabelError):
        parse(text)


def test_duplicate_label_across_nested_and_top_level_is_invalid():
    text = (
        "! t\n"
        "| review: gather feedback\n"
        "  ^ style-reviewer: check formatting\n"
        "| style-reviewer: unrelated later stage reusing the same label\n"
    )
    with pytest.raises(DuplicateLabelError):
        parse(text)


def test_entries_without_top_level_intent_is_invalid():
    text = "^ a: do x\n"
    with pytest.raises(MissingIntentError):
        parse(text)


def test_mixed_top_level_fanout_and_pipeline_is_invalid():
    text = "! t\n^ a: do x\n| b: do y\n"
    with pytest.raises(MixedTopLevelDelegationError):
        parse(text)


def test_nested_fanout_under_pipeline_does_not_trigger_mixed_delegation_error():
    # Spec Example E: ^ nested inside | is the one sanctioned way they coexist.
    text = (
        "! review and merge feedback on a pull request\n"
        "| review: gather feedback before merging\n"
        "  ^ style-reviewer: check formatting and naming conventions\n"
        "  ^ substance-reviewer: check logical correctness\n"
        "| merge: combine {style-reviewer} and {substance-reviewer} feedback\n"
    )
    msg = parse(text)  # must not raise
    assert len(msg.entries) == 4


def test_for_each_interpolation_substitutes_item_var():
    text = (
        "! outline a book, then draft every chapter\n"
        "| categorize: derive an outline of chapter categories\n"
        "| draft: write chapters from the outline\n"
        "  ^ for-each category in {categorize}.outline: draft this chapter from %category%'s assigned posts\n"
    )
    msg = parse(text)
    fe = next(e for e in msg.entries if e.is_for_each)
    rendered = interpolate_for_each(fe, "Chapter 1: Origins")
    assert rendered == "draft this chapter from Chapter 1: Origins's assigned posts"
    assert msg.warnings == []


def test_for_each_template_without_item_var_is_flagged_not_an_error():
    text = (
        "! outline a book, then draft every chapter\n"
        "| categorize: derive an outline of chapter categories\n"
        "| draft: write chapters from the outline\n"
        "  ^ for-each category in {categorize}.outline: draft this chapter\n"
    )
    msg = parse(text)  # must not raise
    assert len(msg.warnings) == 1
    assert "category" in msg.warnings[0]


def test_item_var_escaping_suppresses_interpolation():
    text = (
        "! outline a book, then draft every chapter\n"
        "| categorize: derive an outline of chapter categories\n"
        "| draft: write chapters from the outline\n"
        "  ^ for-each category in {categorize}.outline: "
        "mention the literal text \\%category% then use %category%\n"
    )
    msg = parse(text)
    fe = next(e for e in msg.entries if e.is_for_each)
    assert msg.warnings == []  # an unescaped occurrence exists, so no flag
    rendered = interpolate_for_each(fe, "Intro")
    assert rendered == "mention the literal text %category% then use Intro"


def test_item_var_non_matching_word_left_untouched():
    refs = find_item_var_refs("check %APPDATA% but not %category%", "category")
    assert len(refs) == 1  # only the declared item_var name matches
