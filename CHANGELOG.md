# Consort Changelog

Version history, rationale, and prior syntax for the Consort Prompt DSL.
The operational spec (`CONSORT Markdown for Intelligent Coordination.txt`)
states current rules only — this file is where the reasoning and the
record of what changed and why actually live.

## Housekeeping: changelog moved out of the spec file

The versioning rule and the changelog entries below (previously Section
8 of the spec's "CURRENT VERSION" section) were moved into this
standalone file so the spec states current rules only, with no version
history embedded in it. Section 8 now just states the current version
and stable-symbol list, and points here for rationale, prior syntax, and
the full account of what changed and why. Cross-references elsewhere in
the spec that used to say "see the changelog entry (Section 8)" were
updated to point to this file instead. This is a documentation move, not
a grammar change — it does not affect the versioning rule below.

## Versioning rule

Adopted at v0.11: the version number changes whenever a valid Consort
string's meaning changes — a new construct, a new symbol, or a fix that
makes previously-mismatched input parse differently. Pure documentation
changes (cross-reference fixes, condensed prose, reordered sections,
comment corrections) do not bump the version, since no string's meaning
changes.

## v0.12 to v0.16

Added the LABELED FORM for `#`, `$`, and `*` (spec 2.5): `<symbol> <label>:
<content>`, using the same label/colon grammar as `^`/`|`'s `<agent-label>`
(2.8). It is optional and usable for a single instance or for several;
when two or more labeled instances of the same symbol appear, each
requires a distinct label, scoped per-symbol rather than message-wide
like `^`/`|` labels (2.8). Plain, unlabeled `#`/`$`/`*` usage — including
multiple accumulating instances, as in every pre-v0.16 example in Section
7 — is unchanged and remains fully valid. Labeled `#`/`$`/`*` instances
are deliberately not part of the `{ }` LABEL REFERENCE namespace (2.11),
since they produce no output to address.

Formalized a GLOBAL RULE (spec Section 3) that a bare `<symbol>:` or
`<symbol> :` — a directive symbol followed by a colon with no digits and
no label characters in between, adjacent or whitespace-separated — is
invalid for all eight symbols (`! # $ % * @ ^ |`), not only `#`/`$`/`*`.
For `!`, `%`, and `@` (which have no labeled form at all) this rules out
ever inferring a "label:" construct for them by analogy with `#`/`$`/`*`
or `^`/`|`. For `^`/`|` it makes explicit, for the first time, that
`<agent-label>` must be non-empty — a bare `^:` or `|:` was previously
ambiguous rather than clearly invalid.

This is new grammar, not a documentation change — it adds a construct a
v0.12 parser would not recognize and closes a previously-ambiguous case
for `^`/`|`, hence its own version per the versioning rule above. This
revision is numbered v0.16 to stay aligned with the outer Super Prompt
file version rather than continuing the v0.13/14/15 sequence.

Implemented in the reference parser (`parser/`) and its PEG grammar
(`parser/peg/consort.peg`); see `parser/tests/test_labeled_directives.py`.

## v0.11 to v0.12

Added `{ }` LABEL REFERENCES (spec 2.11): `{<label>}` and
`{<label>}.<field>` are a new structural token for naming a prior `^`/`|`
entry's output from within a `|` stage task description, an inline
override (`/$`/`/%`/`/@`/`/*`), or `for-each`'s source position — distinct
from ordinary prose mentioning the same label. Undefined and
forward-referenced labels are parse-time errors; a reference between
sibling `^` entries at the same fan-out level is also a parse-time error,
since it would smuggle a dependency into an independence assumption `^`
makes structural. Resolves the DSL's prior Open Question 1 (non-adjacent
references previously resolved only by prose). This is new grammar, not a
documentation change — it changes what a valid `|`/`^` entry can express,
and what a parser must recognize as structural versus prose.

Unified `for-each`'s source (2.8) with this syntax: `^ for-each <item-var>
in <source>: ...` now requires `{<label>}[.<field>]` rather than the bare
`label[.field]` token used in v0.11. A v0.11 `for-each` entry using the
bare, unbraced form no longer parses as written under v0.12 — authors
must add braces around the label. This is a breaking grammar change to
previously-valid input, hence its own version per the versioning rule
above.

Extended the backslash-escape convention (Section 3; previously covering
line-leading directive symbols and `%item-var%` interpolation, 2.8) to
`\{`, suppressing label-reference parsing for a literal brace.
