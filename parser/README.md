# Consort Reference Parser

A small Python reference implementation of `{label}` / `{label}.field`
LABEL REFERENCES — Section 2.11 of the
[Consort spec](<../Consort 0.12 system prompt.txt>).

This is **not** a full, production-grade Consort parser. It understands
just enough of the surrounding grammar — top-level directives, `^`/`|`
entries, nested `^` under `|`, `for-each`, and inline overrides — to parse
the contexts a label reference can legally appear in, and to enforce
Section 2.11's validation rules:

- a `{label}` reference must resolve to a label already defined earlier in
  the message (undefined and forward references are errors);
- a `{label}` reference from a `^` entry to a sibling `^` entry in the same
  fan-out group (top-level, or nested under one `|` stage) is an error —
  `^` entries are independent by definition;
- `\{` escapes a literal `{`, suppressing reference parsing;
- a `{` not immediately followed by a run of label characters and a
  closing `}` never becomes a candidate token at all — it's left as
  ordinary text, not an error.

Multi-line loose-form scanning across blank lines and framed-form
byte-exact payload parsing are intentionally out of scope; every entry is
expected to occupy one logical line, optionally followed by indented
continuation or nested-`^` lines, matching every worked example in the
spec.

## Usage

```python
from parser import parse

msg = parse("""
! draft, review, and finalize a design doc
| drafter: write the initial draft, including a worked examples section
| reviewer: review the draft for correctness and clarity
| finalizer: rewrite {drafter}'s draft addressing {reviewer}'s
  feedback, but keep {drafter}.examples verbatim
""")

msg.references["finalizer"]  # -> list[LabelReference]
```

`parse()` raises `UndefinedLabelError`, `ForwardReferenceError`, or
`SiblingFanoutReferenceError` (all subclasses of `ConsortError`) on the
first invalid reference found, in document order.

## Running the tests

From the repository root:

```
pip install pytest
pytest parser
```
