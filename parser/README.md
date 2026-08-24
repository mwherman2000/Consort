# Consort Reference Parser

A Python reference implementation of the Consort DSL's parseable structure
(spec v0.12), covering:

- **Top-level directives** `! # $ % * @` — including multi-line loose-form
  scanning (a directive's value continues across lines until a blank line
  or the next directive) and `#`/`$` accumulation.
- **`^`/`|` entries** — label:task parsing, one level of nested `^` under
  `|` (2.9), and inline overrides `/$ /% /@ /*` with the spec's
  accumulate-vs-replace rule and wrapped-continuation-line values.
- **`for-each` generators** (2.8) — `{label}.field` source parsing and
  `%item-var%` interpolation, including `\%item-var%` escaping and the
  "template never references `%item-var%`" flag (a warning, not an error).
- **`{label}` / `{label}.field` LABEL REFERENCES** (2.11) — the original
  focus of this parser: undefined-label, forward-reference, and
  sibling-`^`-fan-out validation, `\{` escaping, and non-matching braces
  left as plain text.
- **Framed form** (2.10) — byte-exact, length-prefixed payloads for any
  symbol, read by their declared UTF-8 byte count with no in-band
  scanning. A framed `^`/`|` entry's label is still extracted (needed for
  addressing), but its task text is fully opaque: never split into
  overrides, never scanned for `{ }` references.
- **Structural validation** — agent-label uniqueness across the whole
  message (2.8), `^`/`|` entries with no top-level `!` (2.1/2.8/2.9), and
  `^`/`|` both appearing unindented at the top level (2.9).

**Deliberately out of scope**, because these are runtime/response-behavior
rules for the *interpreting model*, not structural parsing rules checkable
against a single message in isolation: `^` concurrency and `|`
halt-on-failure semantics, the conflict-precedence ordering in Section 5,
and anything requiring a prior entry's actual runtime output (verifying a
`for-each`'s declared item count, or that a stage complied with what a
label reference told it to do — 2.11's "parsing rigor, not semantic
rigor" principle).

## PEG grammar

[`peg/`](peg/) is a second, independent implementation of the same
grammar, driven by an actual [PEG](https://en.wikipedia.org/wiki/Parsing_expression_grammar)
grammar file — [`peg/consort.peg`](peg/consort.peg), loaded at runtime via
[Parsimonious](https://github.com/erikrose/parsimonious) — rather than the
hand-written regexes and string checks above. It covers the same ground
(line classification, label:task splitting, overrides, `for-each`
headers, and `{ }` label-reference tokenization) using grammar rules
instead, reuses this module's *validation* logic (agent-label uniqueness,
reference resolution, etc. — the same rule regardless of which parser
found the entries), and cross-checks against the same worked examples in
its own test suite. See [`peg/README.md`](peg/README.md) for what is and
isn't expressed as PEG rules, and why (framed form's byte-exact length
prefix, and the stateful "what's currently open" bookkeeping Section 2.9
needs, are both explained there).

```
pip install -r parser/peg/requirements.txt
pytest parser/peg
```

## Usage

```python
from parser import parse, interpolate_for_each

msg = parse("""
! draft, review, and finalize a design doc
| drafter: write the initial draft, including a worked examples section
| reviewer: review the draft for correctness and clarity
| finalizer: rewrite {drafter}'s draft addressing {reviewer}'s
  feedback, but keep {drafter}.examples verbatim
""")

msg.references["finalizer"]  # -> list[LabelReference]
msg.entries                  # -> list[Entry]
msg.warnings                 # -> e.g. a for-each template missing %item-var%
```

`parse()` raises `UndefinedLabelError`, `ForwardReferenceError`,
`SiblingFanoutReferenceError`, `DuplicateLabelError`, `MissingIntentError`,
`MixedTopLevelDelegationError`, or `MalformedFramedFormError` (all
subclasses of `ConsortError`) on the first structural problem found, in
document order.

## Running the tests

From the repository root:

```
pip install pytest -r parser/peg/requirements.txt
pytest parser
```

`parsimonious` is required even for this plain run: `parser/tests` also
contains `test_spec_examples.py` (all seven worked examples from Section 7
of the spec, run verbatim) and `test_edge_cases.py`, both parametrized to
run every case through *both* this module's `parse()` and
[`parser.peg`](peg/)'s `parse()` and assert they agree, so they import
`parser.peg` unconditionally. To run only this module's own suite without
installing `parsimonious`, target the individual files directly, e.g.
`pytest parser/tests/test_label_references.py parser/tests/test_full_dsl.py`.
