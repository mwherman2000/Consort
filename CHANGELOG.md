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

## v0.16 to v0.17

Reintroduced `+` as TOOL / CAPABILITY DECLARATION (spec 2.12): declares
that a task — the top-level request as a whole, or, via inline `/+`
(2.8/2.9), a single `^`/`|` entry — requires a specific tool or external
capability to execute (e.g. live web search, file-system read access, a
database connection). `+` was retired in v0.10 as a vague, undefined
"Extras" catch-all with no defined semantics; v0.17 reuses the symbol for
this unrelated, narrowly-scoped purpose — the v0.10 and v0.17 meanings
share only the character, and a pre-v0.10 document's free-form `+` usage
is not equivalent to, and will now be parsed as, a capability
declaration.

Motivating problem: there was previously no way to declare, at parse
time, that a `^`/`|` entry needs a specific tool or external capability
before it can execute. In practice this was being expressed by misusing
`*`/`/*` (Think/Reasoning-style, spec 2.6) for values like `web-search`,
which is not a defined reasoning style and is simply misinterpreted as
an unrecognized custom-reasoning instruction rather than flagged.

Grammar:
- Top-level `+` accumulates (like `#`/`$`) and is inherited by every
  `^`/`|` entry unless overridden inline — the same inheritance model as
  `$`/`@`.
- Inline `/+` uses the identical override grammar as `/$`/`/%`/`/@`/`/*`
  (2.8/2.9) and accumulates (matching `/$`'s behavior, not `/%`/`/@`/`/*`'s
  replace behavior).
- `+` has no closed, enumerated vocabulary — capability names are
  open-ended free text, the same design as `@` (persona) and `%`
  (format), since which capabilities exist is a property of the
  deployment/orchestrator, not of Consort itself.
- Multiple capabilities for one entry are written as repeated `/+`
  overrides (`/+ web-search /+ file-read`), not comma-separated within
  one `/+` value — resolving an open question from the original proposal
  by matching 2.8's existing "multiple overrides may be chained, each
  introduced by its own `/`" rule, and keeping `+` consistent with how no
  other Consort directive uses a comma as structural syntax.
- `+` is declared, not guaranteed — the same advisory principle as `$`
  (2.3), `^`'s concurrency signal, and `|`'s sequencing signal: an
  external orchestrator (e.g. AgentOrchestrator/SubAgentTool in
  AgentSharp) remains the actual mechanism that must route an entry to a
  tool-capable execution path. No new enforcement machinery is added to
  the spec itself.
- `+` has no labeled form (2.5's labeled-form scope remains `#`/`$`/`*`
  only), and is grouped with `!`/`%`/`@` (not `#`/`$`) for Section 3's
  global bare-colon rule, despite accumulating like `#`/`$` — a bare `+:`
  or `+ :` is invalid.

This is new grammar, not a documentation change — it adds a construct a
v0.16 parser would not recognize (a ninth top-level symbol and its `/+`
override), hence its own version per the versioning rule above.

Also removed version-provenance commentary (`[NEW in vX]` tags, "vX
adds/reintroduces Y", "prior to vX this took Y", "no longer parses",
"as of vX", and similar historical asides) throughout the spec file
wherever it didn't affect current grammar — that narrative now lives
here instead. This is a documentation cleanup, not a grammar change.

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
