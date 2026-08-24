"""Runs every worked example (A-G) from Section 7 of the v0.12 spec,
verbatim, through BOTH parser implementations (parser.consort_parser and
parser.peg.peg_parser), asserting each parses without error and matches
the structural facts called out in the spec's own "Interpretation" notes.

This is the one place both parsers are cross-checked against the complete,
unmodified spec text rather than against ad hoc or trimmed-down inputs
built while developing each parser -- the closest thing to "did we test
every documented example" this repo has.
"""

import pytest

from parser import consort_parser
from parser.peg import peg_parser

PARSERS = [
    pytest.param(consort_parser.parse, id="hand-written"),
    pytest.param(peg_parser.parse, id="peg"),
]

EXAMPLE_A = """\
! locate root cause of a failing test
#31:
Expected: 12.50, Actual: 12.495
$ do not modify any files
$ cite exact file and line number
% plain text, under 100 words
* step-by-step
"""

EXAMPLE_B = """\
! suggest a 3-course dinner menu
# Hosting 6 guests; one vegetarian, one gluten-free
$ no shellfish
$ total prep time under 2 hours
$ include a wine pairing for each course
% numbered list, one course per line
@ warm, experienced home cook
* concise
"""

EXAMPLE_C = """\
! research three independent C# libraries and merge results
# evaluating for a .NET solution; libraries are unrelated — no shared
  state between the research tasks
$ verify current NuGet version via search, not training data
% short summary + one-line recommendation per library, under 300 words each
^ polly-researcher: research Polly (resilience)
^ fluentvalidation-researcher: research FluentValidation
^ mediatr-researcher: research MediatR /$ flag any recent licensing
  changes explicitly
* concise
"""

EXAMPLE_D = """\
! draft, critique, and revise a product announcement
# internal tool launch; audience is engineering leadership
$ under 400 words final
$ show intermediate stages
| drafter: write initial draft /@ enthusiastic product writer
| critic: critique the draft above for unsubstantiated claims and
  jargon /@ skeptical engineering lead
| reviser: revise drafter's draft addressing critic's critique
  /@ enthusiastic product writer
% final polished announcement, followed by the critique that shaped it
"""

EXAMPLE_E = """\
! review and merge feedback on a pull request
# small internal refactor; two independent review angles needed
  before merging
| review: gather feedback before merging
  ^ style-reviewer: check formatting and naming conventions
  ^ substance-reviewer: check logical correctness
| merge: combine {style-reviewer} and {substance-reviewer} feedback
  into one report, noting any disagreement between them
% single consolidated review comment
"""

EXAMPLE_F = """\
! outline a book, then draft every chapter
| categorize: derive an outline of chapter categories from the
  source material
| draft: write chapters from the outline
  ^ for-each category in {categorize}.outline: draft this chapter
    from %category%'s assigned posts
% one section per chapter, in outline order
"""

EXAMPLE_G = """\
! draft, review, and finalize a design doc, preserving the approved
  examples section verbatim
# internal API design doc; examples section already reviewed once and
  must not be reworded
| drafter: write the initial draft, including a worked examples section
| reviewer: review the draft for correctness and clarity
| finalizer: rewrite {drafter}'s draft addressing {reviewer}'s
  feedback, but keep {drafter}.examples verbatim since it was already
  approved
% final document only
"""


@pytest.mark.parametrize("parse", PARSERS)
def test_example_a_framed_form(parse):
    msg = parse(EXAMPLE_A)
    assert msg.directives["!"] == "locate root cause of a failing test"
    assert msg.directives["#"] == ["Expected: 12.50, Actual: 12.495"]
    assert msg.directives["$"] == ["do not modify any files", "cite exact file and line number"]
    assert msg.directives["%"] == "plain text, under 100 words"
    assert msg.directives["*"] == "step-by-step"
    assert msg.entries == []


@pytest.mark.parametrize("parse", PARSERS)
def test_example_b_no_delegation_symbols(parse):
    # No ^/| at all -- exercises the "message with no entries never needs
    # a top-level !" edge case, and every scalar/accumulating directive.
    msg = parse(EXAMPLE_B)
    assert msg.directives["!"] == "suggest a 3-course dinner menu"
    assert msg.directives["#"] == ["Hosting 6 guests; one vegetarian, one gluten-free"]
    assert msg.directives["$"] == [
        "no shellfish",
        "total prep time under 2 hours",
        "include a wine pairing for each course",
    ]
    assert msg.directives["%"] == "numbered list, one course per line"
    assert msg.directives["@"] == "warm, experienced home cook"
    assert msg.directives["*"] == "concise"
    assert msg.entries == []


@pytest.mark.parametrize("parse", PARSERS)
def test_example_c_top_level_fanout(parse):
    msg = parse(EXAMPLE_C)
    labels = [e.label for e in msg.entries]
    assert labels == ["polly-researcher", "fluentvalidation-researcher", "mediatr-researcher"]
    assert all(e.kind == "^" and e.group == ("top",) for e in msg.entries)
    mediatr = msg.entries[-1]
    assert mediatr.overrides["$"] == "flag any recent licensing changes explicitly"
    # None of the three reference each other -- nothing to resolve.
    assert all(msg.references[e.label] == [] for e in msg.entries)


@pytest.mark.parametrize("parse", PARSERS)
def test_example_d_sequential_pipeline(parse):
    msg = parse(EXAMPLE_D)
    labels = [e.label for e in msg.entries]
    assert labels == ["drafter", "critic", "reviser"]
    assert msg.entries[0].overrides["@"] == "enthusiastic product writer"
    assert msg.entries[1].task == "critique the draft above for unsubstantiated claims and jargon"
    assert msg.entries[2].task == "revise drafter's draft addressing critic's critique"
    assert msg.directives["$"] == ["under 400 words final", "show intermediate stages"]


@pytest.mark.parametrize("parse", PARSERS)
def test_example_e_nested_fanout_under_pipeline(parse):
    msg = parse(EXAMPLE_E)
    labels = [e.label for e in msg.entries]
    assert labels == ["review", "style-reviewer", "substance-reviewer", "merge"]
    nested = [e for e in msg.entries if e.label in ("style-reviewer", "substance-reviewer")]
    assert all(e.parent_stage == "review" for e in nested)
    merge_refs = {r.label for r in msg.references["merge"]}
    assert merge_refs == {"style-reviewer", "substance-reviewer"}


@pytest.mark.parametrize("parse", PARSERS)
def test_example_f_for_each_generator(parse):
    msg = parse(EXAMPLE_F)
    labels = [e.label for e in msg.entries if not e.is_for_each]
    assert labels == ["categorize", "draft"]
    fe = next(e for e in msg.entries if e.is_for_each)
    assert fe.item_var == "category"
    assert fe.source_ref.label == "categorize"
    assert fe.source_ref.field == "outline"
    assert fe.parent_stage == "draft"


@pytest.mark.parametrize("parse", PARSERS)
def test_example_g_non_adjacent_label_reference(parse):
    msg = parse(EXAMPLE_G)
    labels = [e.label for e in msg.entries]
    assert labels == ["drafter", "reviewer", "finalizer"]
    refs = {(r.label, r.field) for r in msg.references["finalizer"]}
    assert refs == {("drafter", None), ("reviewer", None), ("drafter", "examples")}
