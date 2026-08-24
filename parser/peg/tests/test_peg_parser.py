"""Cross-checks for the PEG-based parser (parser/peg/peg_parser.py) against
the same inputs used in parser/tests -- the two parsers are meant to agree
on every message; this suite exercises the label-reference cases from
test_label_references.py and the full-grammar cases from test_full_dsl.py
through the PEG pipeline instead."""

import pytest

from parser.consort_parser import (
    DuplicateLabelError,
    ForwardReferenceError,
    MalformedFramedFormError,
    MissingIntentError,
    MixedTopLevelDelegationError,
    SiblingFanoutReferenceError,
    UndefinedLabelError,
)
from parser.peg import find_label_refs, parse, render_escapes, split_overrides


def test_grammar_loads_and_has_expected_rules():
    from parser.peg import GRAMMAR

    for rule_name in ("single_line", "entry_body", "for_each_header", "content", "task_with_overrides"):
        assert rule_name in GRAMMAR


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


def test_valid_reference_with_field_example_g():
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
    with pytest.raises(UndefinedLabelError):
        parse("! finalize\n| finalizer: polish {nobody}'s draft\n")


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


def test_reference_inside_for_each_source():
    text = (
        "! outline a book, then draft every chapter\n"
        "| categorize: derive an outline of chapter categories\n"
        "| draft: write chapters from the outline\n"
        "  ^ for-each category in {categorize}.outline: draft this chapter from %category%'s assigned posts\n"
    )
    msg = parse(text)
    fe = next(e for e in msg.entries if e.is_for_each)
    assert fe.item_var == "category"
    assert fe.source_ref.label == "categorize"
    assert fe.source_ref.field == "outline"


def test_escaped_literal_brace():
    text = "! draft\n| drafter: emit the literal text \\{drafter} in the output\n"
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


def test_non_sibling_nested_reference_from_pipeline_stage_is_valid():
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
    assert find_label_refs('{ "key": "value" }, and a quantifier a{2,4}') == []


def test_framed_top_level_directive():
    payload = "Expected: 12.50, Actual: 12.495"
    text = (
        f"! locate root cause of a failing test\n"
        f"#{len(payload.encode('utf-8'))}:\n{payload}\n"
        f"$ do not modify any files\n"
    )
    msg = parse(text)
    assert msg.directives["#"] == [payload]
    assert msg.directives["$"] == ["do not modify any files"]


def test_framed_entry_extracts_label_but_keeps_task_opaque():
    payload = "polly-researcher: research Polly and report NuGet version"
    text = f"! research a library\n^{len(payload.encode('utf-8'))}:\n{payload}\n"
    msg = parse(text)
    entry = msg.entries[0]
    assert entry.framed is True
    assert entry.label == "polly-researcher"
    assert entry.task == "research Polly and report NuGet version"


def test_framed_entry_content_never_scanned_for_label_references():
    payload = "finalizer: keep {nonexistent} verbatim"
    text = f"! test framed opacity\n|{len(payload.encode('utf-8'))}:\n{payload}\n"
    msg = parse(text)  # must not raise
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
    with pytest.raises(DuplicateLabelError):
        parse("! t\n^ a: do x\n^ a: do y\n")


def test_entries_without_top_level_intent_is_invalid():
    with pytest.raises(MissingIntentError):
        parse("^ a: do x\n")


def test_mixed_top_level_fanout_and_pipeline_is_invalid():
    with pytest.raises(MixedTopLevelDelegationError):
        parse("! t\n^ a: do x\n| b: do y\n")


def test_nested_fanout_under_pipeline_does_not_trigger_mixed_delegation_error():
    text = (
        "! review and merge feedback on a pull request\n"
        "| review: gather feedback before merging\n"
        "  ^ style-reviewer: check formatting and naming conventions\n"
        "  ^ substance-reviewer: check logical correctness\n"
        "| merge: combine {style-reviewer} and {substance-reviewer} feedback\n"
    )
    msg = parse(text)  # must not raise
    assert len(msg.entries) == 4


def test_for_each_missing_item_var_is_flagged_not_an_error():
    text = (
        "! outline a book, then draft every chapter\n"
        "| categorize: derive an outline of chapter categories\n"
        "| draft: write chapters from the outline\n"
        "  ^ for-each category in {categorize}.outline: draft this chapter\n"
    )
    msg = parse(text)  # must not raise
    assert len(msg.warnings) == 1
    assert "category" in msg.warnings[0]


def test_split_overrides_matches_entry_parsing():
    overrides, base = split_overrides("revise addressing the critique /@ skeptical editor /$ under 400 words")
    assert base == "revise addressing the critique"
    assert overrides == {"@": "skeptical editor", "$": "under 400 words"}


def test_example_d_full_pipeline_matches_spec():
    text = (
        "! draft, critique, and revise a product announcement\n"
        "# internal tool launch; audience is engineering leadership\n"
        "$ under 400 words final\n"
        "$ show intermediate stages\n"
        "| drafter: write initial draft /@ enthusiastic product writer\n"
        "| critic: critique the draft above for unsubstantiated claims and\n"
        "  jargon /@ skeptical engineering lead\n"
        "| reviser: revise drafter's draft addressing critic's critique\n"
        "  /@ enthusiastic product writer\n"
        "% final polished announcement, followed by the critique that shaped it\n"
    )
    msg = parse(text)
    assert msg.directives["!"] == "draft, critique, and revise a product announcement"
    assert msg.directives["$"] == ["under 400 words final", "show intermediate stages"]
    labels = [e.label for e in msg.entries]
    assert labels == ["drafter", "critic", "reviser"]
    assert msg.entries[1].task == "critique the draft above for unsubstantiated claims and jargon"
    assert msg.entries[2].overrides["@"] == "enthusiastic product writer"
