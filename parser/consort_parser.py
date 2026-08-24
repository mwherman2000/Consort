"""Reference parser for Consort's { } LABEL REFERENCES (spec Section 2.11).

This is a *reference implementation* scoped to validating the label-reference
grammar against concrete inputs -- not a full, production-grade Consort
parser. It understands enough of the surrounding grammar (top-level
directives, ^/| entries, nested ^ under |, for-each, and inline overrides)
to parse the contexts a label reference can legally appear in, and enforces
Section 2.11's validation rules:

  - a { } reference must resolve to a label already defined earlier in the
    message (undefined and forward references are errors);
  - a { } reference from a ^ entry to a sibling ^ entry in the same
    fan-out group (top-level or nested under one | stage) is an error;
  - \\{ escapes a literal brace, suppressing reference parsing;
  - a { not immediately followed by a run of label characters and a
    closing } never becomes a candidate token at all (left as plain text).

Each entry is expected to occupy a single logical line, optionally followed
by indented continuation/nested-^ lines -- matching every worked example in
the spec. Multi-line loose-form scanning across blank lines, and framed-form
byte-exact payload parsing, are intentionally out of scope for this
reference parser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

TOP_SYMBOLS = "!#$%*@^|"
ACCUMULATING_TOP_SYMBOLS = {"#", "$"}
OVERRIDE_SYMBOLS = {"$", "%", "@", "*"}
ACCUMULATING_OVERRIDE_SYMBOLS = {"$"}

LABEL_CHARS = r"[A-Za-z0-9_-]+"
LABEL_RE = re.compile(rf"^{LABEL_CHARS}$")

# Either an escaped opening brace (\{, always literal) or a candidate label
# reference token: {label} or {label}.field, no internal whitespace.
_TOKEN_RE = re.compile(
    r"\\\{" rf"|\{{({LABEL_CHARS})\}}(?:\.({LABEL_CHARS}))?"
)

# for-each's source position must be exactly one label-reference token,
# consuming the entire source text.
_SOURCE_RE = re.compile(rf"^\{{({LABEL_CHARS})\}}(?:\.({LABEL_CHARS}))?$")

_OVERRIDE_SPLIT_RE = re.compile(r"(?:^|\s)/([$%@*])(?=\s|$)")
_FOR_EACH_RE = re.compile(rf"^for-each\s+({LABEL_CHARS})\s+in\s+(.+)$")


class ConsortError(Exception):
    """Base class for all reference-parser validation errors."""


class UndefinedLabelError(ConsortError):
    pass


class ForwardReferenceError(ConsortError):
    pass


class SiblingFanoutReferenceError(ConsortError):
    pass


@dataclass(frozen=True)
class LabelReference:
    label: str
    field: Optional[str]
    raw: str
    start: int
    end: int


@dataclass
class Entry:
    kind: str  # '^' or '|'
    label: str
    task: str
    overrides: Dict[str, str]
    order: int
    group: Optional[Tuple]
    is_for_each: bool = False
    item_var: Optional[str] = None
    source_ref: Optional[LabelReference] = None
    parent_stage: Optional[str] = None


@dataclass
class ParsedMessage:
    directives: Dict[str, object]
    entries: List[Entry]
    references: Dict[object, List[LabelReference]] = field(default_factory=dict)


def find_label_refs(text: str) -> List[LabelReference]:
    """Scan `text` for candidate { } tokens, skipping escaped braces.

    Only tokens that are *structurally* well-formed ({label} or
    {label}.field, immediately-adjacent characters, no internal
    whitespace) are returned. \\{ is consumed as an escape and produces no
    reference. Anything else containing a bare '{' (JSON, quantifiers,
    unmatched braces) never matches and is silently left as plain text --
    it will not appear in the returned list at all.
    """
    refs: List[LabelReference] = []
    for m in _TOKEN_RE.finditer(text):
        if m.group(0) == "\\{":
            continue
        label, dotted_field = m.group(1), m.group(2)
        refs.append(
            LabelReference(
                label=label,
                field=dotted_field,
                raw=m.group(0),
                start=m.start(),
                end=m.end(),
            )
        )
    return refs


def render_escapes(text: str) -> str:
    """Render \\{ as a literal { (the only escape this grammar defines)."""
    return text.replace("\\{", "{")


def _split_overrides(text: str) -> Tuple[Dict[str, str], str]:
    matches = list(_OVERRIDE_SPLIT_RE.finditer(text))
    if not matches:
        return {}, text.strip()

    base_task = text[: matches[0].start()].strip()
    overrides: Dict[str, str] = {}
    for i, m in enumerate(matches):
        sym = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start:end].strip()
        if sym in ACCUMULATING_OVERRIDE_SYMBOLS and sym in overrides:
            overrides[sym] = f"{overrides[sym]}; {value}"
        else:
            overrides[sym] = value
    return overrides, base_task


def _parse_entry_line(kind: str, rest: str, order: int, nested_under: Optional[str],
                       group: Optional[Tuple]) -> Entry:
    label_part, sep, task_part = rest.partition(":")
    if not sep:
        raise ConsortError(f"entry has no structural ':' separating label from task: {rest!r}")
    label_part = label_part.strip()
    task_part = task_part.strip()

    is_for_each = label_part == "for-each" or label_part.startswith("for-each ")
    if is_for_each:
        m = _FOR_EACH_RE.match(label_part)
        if not m:
            raise ConsortError(f"malformed for-each entry: {rest!r}")
        item_var, source_text = m.group(1), m.group(2).strip()
        source_match = _SOURCE_RE.match(source_text)
        if not source_match:
            raise ConsortError(
                f"for-each source must be a single {{label}}[.field] reference, got {source_text!r}"
            )
        source_ref = LabelReference(
            label=source_match.group(1),
            field=source_match.group(2),
            raw=source_text,
            start=0,
            end=len(source_text),
        )
        label = f"__for_each_{order}__"
    else:
        label = label_part
        if not LABEL_RE.match(label):
            raise ConsortError(f"invalid agent-label: {label!r}")
        item_var = None
        source_ref = None

    overrides, base_task = _split_overrides(task_part)

    return Entry(
        kind=kind,
        label=label,
        task=base_task,
        overrides=overrides,
        order=order,
        group=group,
        is_for_each=is_for_each,
        item_var=item_var,
        source_ref=source_ref,
        parent_stage=nested_under,
    )


def _parse_entries(lines: List[str]) -> Tuple[Dict[str, object], List[Entry]]:
    directives: Dict[str, object] = {"!": None, "#": [], "$": [], "%": None, "*": None, "@": None}
    entries: List[Entry] = []
    current_entry: Optional[Entry] = None
    order = 0

    for raw_line in lines:
        if not raw_line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        content = raw_line.strip()

        if content.startswith("\\") and len(content) > 1 and content[1] in TOP_SYMBOLS:
            if current_entry is not None:
                current_entry.task = f"{current_entry.task} {content[1:]}".strip()
            continue

        if indent == 0 and content[0] in "!#$%*@":
            sym, rest = content[0], content[1:].strip()
            if sym in ACCUMULATING_TOP_SYMBOLS:
                directives[sym].append(rest)
            else:
                directives[sym] = rest
            current_entry = None
            continue

        if indent == 0 and content[0] in "^|":
            kind = content[0]
            rest = content[1:].strip()
            group = ("top",) if kind == "^" else None
            entry = _parse_entry_line(kind, rest, order, None, group)
            order += 1
            entries.append(entry)
            current_entry = entry
            continue

        if indent > 0 and content[0] == "^" and current_entry is not None and current_entry.kind == "|":
            rest = content[1:].strip()
            group = ("nested", current_entry.label)
            nested_entry = _parse_entry_line("^", rest, order, current_entry.label, group)
            order += 1
            entries.append(nested_entry)
            continue

        if indent > 0 and current_entry is not None:
            current_entry.task = f"{current_entry.task} {content}".strip()
            continue

        # Free-form preamble/interstitial text: out of scope for this
        # reference parser, ignored.

    return directives, entries


def _validate_reference(ref: LabelReference, referencing_entry: Entry,
                         label_to_entry: Dict[str, Entry]) -> None:
    target = label_to_entry.get(ref.label)
    if target is None:
        raise UndefinedLabelError(
            f"'{referencing_entry.label}' references undefined label {{{ref.label}}}"
        )
    if target.order >= referencing_entry.order:
        raise ForwardReferenceError(
            f"'{referencing_entry.label}' references {{{ref.label}}}, "
            f"which is not yet defined at that point in the message"
        )
    if (
        referencing_entry.kind == "^"
        and target.kind == "^"
        and referencing_entry.group is not None
        and target.group == referencing_entry.group
    ):
        raise SiblingFanoutReferenceError(
            f"'{referencing_entry.label}' references sibling ^ entry {{{ref.label}}} "
            f"in the same fan-out group -- ^ entries are independent by definition"
        )


def _resolve_references(entries: List[Entry]) -> Dict[object, List[LabelReference]]:
    label_to_entry: Dict[str, Entry] = {
        e.label: e for e in entries if not e.is_for_each
    }

    references: Dict[object, List[LabelReference]] = {}
    for entry in entries:
        key = entry.label if not entry.is_for_each else id(entry)
        entry_refs: List[LabelReference] = []

        for ref in find_label_refs(entry.task):
            _validate_reference(ref, entry, label_to_entry)
            entry_refs.append(ref)

        for value in entry.overrides.values():
            for ref in find_label_refs(value):
                _validate_reference(ref, entry, label_to_entry)
                entry_refs.append(ref)

        if entry.is_for_each:
            _validate_reference(entry.source_ref, entry, label_to_entry)
            entry_refs.append(entry.source_ref)

        references[key] = entry_refs

    return references


def parse(text: str) -> ParsedMessage:
    """Parse `text` and validate every { } label reference it contains.

    Raises ConsortError (or a subclass) on the first invalid reference
    encountered, in document order. Returns a ParsedMessage on success.
    """
    lines = text.splitlines()
    directives, entries = _parse_entries(lines)
    references = _resolve_references(entries)
    return ParsedMessage(directives=directives, entries=entries, references=references)
