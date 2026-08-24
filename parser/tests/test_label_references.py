"""Tests for { } LABEL REFERENCES (spec Section 2.11) against parser.consort_parser.

Each test corresponds to a case called out explicitly in the design task:
valid reference, valid reference with a .field, undefined label, forward
reference, reference inside an inline override, reference inside a
for-each source, escaped literal '{', a non-matching brace left as plain
text, and a reference between sibling ^ entries (an additional case implied
by the independence rule in 2.11's "Where invalid").
"""

import pytest

from parser.consort_parser import (
    ForwardReferenceError,
    SiblingFanoutReferenceError,
    UndefinedLabelError,
    find_label_refs,
    parse,
    render_escapes,
)


def test_valid_reference_full_output():
    text = (
        "! draft then finalize\n"
        "| drafter: write the initial draft\n"
        "| finalizer: polish {drafter}'s draft\n"
    )
    msg = parse(text)
    refs = msg.references["finalizer"]
    assert len(refs) == 1
    assert refs[0].label == "drafter"
    assert refs[0].field is None


def test_valid_reference_with_field():
    # Example G from the spec: a non-adjacent reference narrowed to one part
    # of the referenced entry's output.
    text = (
        "! draft, review, and finalize a design doc\n"
        "| drafter: write the initial draft, including a worked examples section\n"
        "| reviewer: review the draft for correctness and clarity\n"
        "| finalizer: rewrite {drafter}'s draft addressing {reviewer}'s "
        "feedback, but keep {drafter}.examples verbatim\n"
    )
    msg = parse(text)
    refs = msg.references["finalizer"]
    labels_and_fields = {(r.label, r.field) for r in refs}
    assert labels_and_fields == {("drafter", None), ("reviewer", None), ("drafter", "examples")}


def test_undefined_label_reference():
    text = (
        "! finalize\n"
        "| finalizer: polish {nobody}'s draft\n"
    )
    with pytest.raises(UndefinedLabelError):
        parse(text)


def test_forward_reference():
    text = (
        "! draft then finalize\n"
        "| finalizer: polish {drafter}'s draft\n"
        "| drafter: write the initial draft\n"
    )
    with pytest.raises(ForwardReferenceError):
        parse(text)


def test_reference_inside_override():
    text = (
        "! draft then revise\n"
        "| drafter: write initial draft\n"
        "| reviser: revise /$ match {drafter}'s original word count\n"
    )
    msg = parse(text)
    reviser = next(e for e in msg.entries if e.label == "reviser")
    assert reviser.overrides["$"] == "match {drafter}'s original word count"
    refs = msg.references["reviser"]
    assert any(r.label == "drafter" for r in refs)


def test_reference_inside_for_each_source():
    # Example F from the spec: for-each's source is a unified { }.field
    # label reference, not the bare label[.field] token used pre-v0.12.
    text = (
        "! outline a book, then draft every chapter\n"
        "| categorize: derive an outline of chapter categories\n"
        "| draft: write chapters from the outline\n"
        "  ^ for-each category in {categorize}.outline: draft this chapter from %category%'s assigned posts\n"
    )
    msg = parse(text)
    for_each_entries = [e for e in msg.entries if e.is_for_each]
    assert len(for_each_entries) == 1
    fe = for_each_entries[0]
    assert fe.item_var == "category"
    assert fe.source_ref.label == "categorize"
    assert fe.source_ref.field == "outline"


def test_escaped_literal_brace():
    text = (
        "! draft\n"
        "| drafter: emit the literal text \\{drafter} in the output\n"
    )
    msg = parse(text)
    drafter = next(e for e in msg.entries if e.label == "drafter")
    assert msg.references["drafter"] == []
    assert render_escapes(drafter.task) == "emit the literal text {drafter} in the output"


def test_sibling_fanout_reference_is_invalid():
    text = (
        "! research two libraries\n"
        "^ polly-researcher: research Polly\n"
        "^ fluentvalidation-researcher: research FluentValidation, compare to {polly-researcher}\n"
    )
    with pytest.raises(SiblingFanoutReferenceError):
        parse(text)


def test_sibling_fanout_reference_invalid_when_nested_under_pipeline_stage():
    text = (
        "! review and merge feedback\n"
        "| review: gather feedback before merging\n"
        "  ^ style-reviewer: check formatting and naming conventions\n"
        "  ^ substance-reviewer: check logical correctness, per {style-reviewer}\n"
    )
    with pytest.raises(SiblingFanoutReferenceError):
        parse(text)


def test_non_sibling_nested_reference_from_pipeline_stage_is_valid():
    # Example E from the spec: a later | stage MAY reference nested ^
    # siblings by label reference -- only sibling-to-sibling is forbidden.
    text = (
        "! review and merge feedback\n"
        "| review: gather feedback before merging\n"
        "  ^ style-reviewer: check formatting and naming conventions\n"
        "  ^ substance-reviewer: check logical correctness\n"
        "| merge: combine {style-reviewer} and {substance-reviewer} feedback into one report\n"
    )
    msg = parse(text)
    refs = msg.references["merge"]
    assert {r.label for r in refs} == {"style-reviewer", "substance-reviewer"}


def test_non_matching_brace_left_as_ordinary_text():
    text = '{ "key": "value" }, and a quantifier a{2,4}'
    assert find_label_refs(text) == []


def test_non_matching_brace_inside_entry_does_not_error():
    text = (
        "! draft\n"
        '| drafter: emit a JSON example { "key": "value" } in the output\n'
    )
    msg = parse(text)  # must not raise
    assert msg.references["drafter"] == []
