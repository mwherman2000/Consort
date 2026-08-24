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
pip install pytest
pytest parser
```
