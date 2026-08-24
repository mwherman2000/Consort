# Consort PEG Grammar & Parser

A second, independent implementation of the [Consort reference
parser](../README.md)'s grammar, driven by an actual
[PEG](https://en.wikipedia.org/wiki/Parsing_expression_grammar) grammar
file instead of hand-written regexes and string checks.

- [`consort.peg`](consort.peg) — the grammar itself, written in
  [Parsimonious](https://github.com/erikrose/parsimonious)'s PEG dialect
  (`=` defines a rule, `/` is ordered choice, `~"regex"` is a regex
  terminal, `*` `+` `?` `&` `!` are the usual PEG operators). It's loaded
  directly at runtime — there's no separate "documentation-only" grammar
  that could drift out of sync with what actually parses.
- [`peg_parser.py`](peg_parser.py) — loads `consort.peg` and drives it in
  two layers (see the grammar file's own header comment for the full
  rationale): Layer 1 classifies each physical line (blank / escaped /
  bare-symbol / continuation, Section 3); Layer 2 parses an assembled
  directive's or entry's text into its label:task split (2.8), `for-each`
  header (2.8), inline overrides (2.8/2.9), and `{ }` label-reference
  tokens (2.11).

## What's PEG-driven, and what isn't

**Grammar-driven (this package's actual contribution):**
- Physical-line classification — blank, `\`-escaped, bare-symbol-start
  (at any indentation), or continuation (Section 3).
- `<agent-label> ":" <task>` splitting, with the label's "cannot contain a
  colon, escaped or otherwise" rule enforced directly by excluding `:`
  from the label's character class (Section 2.8).
- `for-each <item-var> in {label}[.field]:` header parsing (Section 2.8).
- Inline override splitting: `/$ /% /@ /*`, with the boundary rule
  ("preceded by whitespace, followed by whitespace-or-end") expressed as
  ordered-choice + lookahead rather than the hand-written parser's
  `finditer` loop.
- `{label}` / `{label}.field` tokenization and `\{` escaping (Section
  2.11) — free text is parsed into a sequence of reference / escaped-brace
  / plain-run tokens by the `content` rule, rather than scanned with a
  regex.

**Deliberately not grammar rules, with the reasoning attached in
`consort.peg`'s header comment and `peg_parser.py`'s module docstring:**
- **Framed form**'s length-prefixed byte payload (Section 2.10) — the
  number of bytes to consume is itself part of the input, a
  data-dependent fact no context-free PEG rule can express directly (the
  same reason a Netstring's length prefix, or Python's own
  INDENT/DEDENT structure, is resolved by a preprocessing/lexing pass
  before the "real" grammar ever sees it). `peg_parser.py` reuses
  `consort_parser.scan_logical_lines()` for this byte-accurate
  extraction, then hands the grammar only what's left.
- **"What construct is currently open"** — Section 2.9's continuation-line
  accumulation and nested-`^`-under-`|` attachment is inherently stateful
  (it depends on what appeared several lines earlier), which a PEG rule
  has no clean way to reference without an explicit lexer pass. A small
  Python state machine (`_segment_records`) does this bookkeeping,
  informed by the grammar's per-line classification rather than replacing
  it.
- **Validation** — agent-label uniqueness, undefined/forward/sibling-`^`
  reference checks, missing-`!`, `^`/`|` mixed at the top level, and the
  `for-each` `%item-var%` warning are the same structural rule regardless
  of which parser produced the `Entry` objects, so this package calls
  [`consort_parser`](../consort_parser.py)'s already-tested implementation
  instead of maintaining a second copy that could quietly drift.

## Usage

```python
from parser.peg import parse

msg = parse("""
! draft, review, and finalize a design doc
| drafter: write the initial draft, including a worked examples section
| reviewer: review the draft for correctness and clarity
| finalizer: rewrite {drafter}'s draft addressing {reviewer}'s
  feedback, but keep {drafter}.examples verbatim
""")

msg.references["finalizer"]  # -> list[LabelReference], same shape as consort_parser's
```

`parse()` raises the same `ConsortError` subclasses as
[`consort_parser.parse()`](../consort_parser.py) — the two parsers are
meant to agree on every input.

## Running the tests

From the repository root:

```
pip install -r parser/peg/requirements.txt
pytest parser/peg
```

`parser/peg/tests/test_peg_parser.py` runs the same worked examples and
edge cases as [`parser/tests`](../tests/) through this grammar-driven
pipeline instead, as a cross-check that the two implementations agree.
