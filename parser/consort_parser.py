"""Reference parser for the Consort Prompt DSL (spec v0.12).

This is a reference implementation of Consort's *parseable* structure: the
eight top-level directives, ^/| entries (including nested ^ under | and
for-each generators), inline overrides, framed-form length-prefixed
payloads, and { } label references (Section 2.11) -- with the validation
rules the spec attaches to each construct.

Deliberately out of scope, because they are runtime/response-behavior rules
for the *interpreting model*, not structural parsing rules a parser can
check against a single message in isolation:
  - concurrency of ^ dispatch, halt-on-failure semantics for | (2.8/2.9)
  - the conflict-precedence ordering in Section 5
  - anything requiring the actual runtime output of a prior entry (e.g.
    verifying a for-each's declared item count, or that a stage complied
    with what a label reference told it to do -- 2.11's "parsing rigor,
    not semantic rigor" principle)

Everything else in Sections 1-3 of the spec that describes how a message is
*structured* is implemented and validated here.
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
_TOKEN_RE = re.compile(r"\\\{" rf"|\{{({LABEL_CHARS})\}}(?:\.({LABEL_CHARS}))?")

# for-each's source position must be exactly one label-reference token,
# consuming the entire source text.
_SOURCE_RE = re.compile(rf"^\{{({LABEL_CHARS})\}}(?:\.({LABEL_CHARS}))?$")

_OVERRIDE_SPLIT_RE = re.compile(r"(?:^|\s)/([$%@*])(?=\s|$)")
_FOR_EACH_RE = re.compile(rf"^for-each\s+({LABEL_CHARS})\s+in\s+(.+)$")

# Framed-form header: symbol, one or more digits, a colon -- no space
# anywhere in the header. Matched against raw UTF-8 bytes so the declared
# length is unambiguous (Section 2.10: "Length is measured in UTF-8 bytes").
_FRAMED_HEADER_RE = re.compile(rb"([!#$%*@^|])([0-9]+):")


class ConsortError(Exception):
    """Base class for all reference-parser validation errors."""


class UndefinedLabelError(ConsortError):
    pass


class ForwardReferenceError(ConsortError):
    pass


class SiblingFanoutReferenceError(ConsortError):
    pass


class DuplicateLabelError(ConsortError):
    """Section 2.8: <agent-label> must be unique across the entire message."""


class MissingIntentError(ConsortError):
    """Section 2.1/2.8/2.9: a message with ^/| entries requires a top-level !."""


class MixedTopLevelDelegationError(ConsortError):
    """Section 2.9: ^ and | may not both appear unindented at the top level."""


class MalformedFramedFormError(ConsortError):
    """Section 2.10: a framed-form header whose declared length can't be read."""


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
    framed: bool = False


@dataclass
class ParsedMessage:
    directives: Dict[str, object]
    entries: List[Entry]
    references: Dict[object, List[LabelReference]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# { } label references (Section 2.11)
# --------------------------------------------------------------------------

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
            LabelReference(label=label, field=dotted_field, raw=m.group(0), start=m.start(), end=m.end())
        )
    return refs


def render_escapes(text: str) -> str:
    """Render \\{ as a literal { (the only escape { } references define)."""
    return text.replace("\\{", "{")


# --------------------------------------------------------------------------
# for-each's %item-var% interpolation (Section 2.8)
# --------------------------------------------------------------------------

def _item_var_re(item_var: str) -> re.Pattern:
    escaped = re.escape(item_var)
    return re.compile(rf"\\%{escaped}%|%{escaped}%")


def find_item_var_refs(text: str, item_var: str) -> List[Tuple[int, int, bool]]:
    """Return (start, end, is_escaped) for each %item_var% occurrence.

    Only the exact declared item_var name matches -- a %word% that doesn't
    match is left untouched, per 2.8 ("a %word% that doesn't match the
    declared variable is left as ordinary text").
    """
    pattern = _item_var_re(item_var)
    out = []
    for m in pattern.finditer(text):
        out.append((m.start(), m.end(), m.group(0).startswith("\\")))
    return out


def interpolate_for_each(entry: Entry, item_value: str) -> str:
    """Render a for-each task template for one concrete item value.

    Unescaped %item_var% is replaced with item_value; \\%item_var% renders
    as the literal text %item_var% (backslash stripped, substitution
    suppressed) per 2.8's escaping rule.
    """
    if not entry.is_for_each:
        raise ConsortError("interpolate_for_each requires a for-each entry")
    pattern = _item_var_re(entry.item_var)

    def _sub(m: re.Match) -> str:
        if m.group(0).startswith("\\"):
            return m.group(0)[1:]
        return item_value

    return pattern.sub(_sub, entry.task)


# --------------------------------------------------------------------------
# Pass 1: byte-accurate logical-line scanning, resolving framed-form
# payloads (Section 2.10) by their declared UTF-8 byte length.
# --------------------------------------------------------------------------

@dataclass
class _LogicalLine:
    indent: int
    framed: bool
    content: str
    directive_symbol: Optional[str] = None  # only set when framed=True


def _scan_logical_lines(text: str) -> List[_LogicalLine]:
    data = text.replace("\r\n", "\n").encode("utf-8")
    n = len(data)
    lines: List[_LogicalLine] = []
    i = 0

    while i < n:
        line_start = i
        indent = 0
        while i < n and data[i : i + 1] == b" ":
            indent += 1
            i += 1

        header = _FRAMED_HEADER_RE.match(data, i)
        if header is not None:
            symbol = header.group(1).decode("ascii")
            length = int(header.group(2))
            header_end = header.end()
            if header_end < n and data[header_end : header_end + 1] == b"\n":
                payload_start = header_end + 1
            else:
                payload_start = header_end
            payload_end = payload_start + length
            if payload_end > n:
                raise MalformedFramedFormError(
                    f"framed {symbol}{length}: declares {length} bytes but only "
                    f"{n - payload_start} remain"
                )
            try:
                payload_text = data[payload_start:payload_end].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MalformedFramedFormError(
                    f"framed {symbol}{length}: payload is not valid UTF-8 at its declared length"
                ) from exc
            lines.append(_LogicalLine(indent=indent, framed=True, content=payload_text, directive_symbol=symbol))
            i = payload_end
            if i < n and data[i : i + 1] == b"\n":
                i += 1
            continue

        nl = data.find(b"\n", i)
        end = nl if nl != -1 else n
        content_text = data[i:end].decode("utf-8")
        lines.append(_LogicalLine(indent=indent, framed=False, content=content_text))
        i = end + 1 if nl != -1 else end

    return lines


# --------------------------------------------------------------------------
# Pass 2: group logical lines into segments (a top-level directive, or an
# entry with all of its wrapped continuation lines and inline overrides
# accumulated), per Section 3's loose-form scanning rules.
# --------------------------------------------------------------------------

def _open_entry_segment(kind: str, rest: str, indent: int, nested_under: Optional[str],
                         group: Optional[Tuple], framed: bool) -> dict:
    label_part, sep, task_start = rest.partition(":")
    if not sep:
        raise ConsortError(f"entry has no structural ':' separating label from task: {rest!r}")
    return {
        "type": "entry",
        "kind": kind,
        "indent": indent,
        "label_part": label_part.strip(),
        "task_buf": task_start.strip(),
        "nested_under": nested_under,
        "group": group,
        "framed": framed,
    }


def _segment_lines(logical_lines: List[_LogicalLine]) -> List[dict]:
    segments: List[dict] = []
    current: Optional[dict] = None
    enclosing_pipe_label: Optional[str] = None

    def close_current():
        nonlocal current
        if current is not None:
            segments.append(current)
            current = None

    for ll in logical_lines:
        if ll.framed:
            close_current()
            sym = ll.directive_symbol
            if sym in "^|":
                nested_under = ll.indent > 0 and enclosing_pipe_label is not None
                seg = _open_entry_segment(
                    sym,
                    ll.content,
                    ll.indent,
                    enclosing_pipe_label if nested_under else None,
                    ("nested", enclosing_pipe_label) if nested_under
                    else (("top",) if sym == "^" else None),
                    framed=True,
                )
                segments.append(seg)
                if ll.indent == 0:
                    enclosing_pipe_label = seg["label_part"] if sym == "|" else None
            else:
                segments.append({"type": "directive", "symbol": sym, "text": ll.content, "framed": True})
                if ll.indent == 0:
                    enclosing_pipe_label = None
            continue

        stripped = ll.content
        if stripped == "":
            close_current()
            enclosing_pipe_label = None
            continue

        if stripped.startswith("\\") and len(stripped) > 1 and stripped[1] in TOP_SYMBOLS:
            literal = stripped[1:]
            if current is not None:
                current["task_buf" if current["type"] == "entry" else "text"] += " " + literal
            continue

        is_bare_symbol_start = stripped[0] in TOP_SYMBOLS

        if ll.indent == 0:
            if is_bare_symbol_start:
                close_current()
                sym, rest = stripped[0], stripped[1:].strip()
                if sym in "^|":
                    group = ("top",) if sym == "^" else None
                    current = _open_entry_segment(sym, rest, 0, None, group, framed=False)
                    enclosing_pipe_label = current["label_part"] if sym == "|" else None
                else:
                    current = {"type": "directive", "symbol": sym, "text": rest, "framed": False}
                    enclosing_pipe_label = None
                continue
            else:
                if current is not None:
                    current["task_buf" if current["type"] == "entry" else "text"] += " " + stripped
                continue
        else:
            if stripped.startswith("^") and enclosing_pipe_label is not None:
                close_current()
                current = _open_entry_segment(
                    "^", stripped[1:].strip(), ll.indent, enclosing_pipe_label,
                    ("nested", enclosing_pipe_label), framed=False,
                )
                continue
            if current is not None:
                current["task_buf" if current["type"] == "entry" else "text"] += " " + stripped
            continue

    close_current()
    return segments


# --------------------------------------------------------------------------
# Pass 3: finalize segments into Entry / directive objects.
# --------------------------------------------------------------------------

def _finalize_entry_segment(seg: dict, order: int) -> Entry:
    kind = seg["kind"]
    label_part = seg["label_part"]
    task_text = seg["task_buf"].strip()
    is_for_each = label_part == "for-each" or label_part.startswith("for-each ")

    if seg["framed"]:
        # Framed payloads are opaque (2.10): only the structural label:task
        # split is honored (needed for addressing); the task text itself is
        # never scanned for overrides, for-each templates, or nested syntax.
        return Entry(
            kind=kind,
            label=label_part,
            task=task_text,
            overrides={},
            order=order,
            group=seg["group"],
            is_for_each=False,
            parent_stage=seg["nested_under"],
            framed=True,
        )

    if is_for_each:
        m = _FOR_EACH_RE.match(label_part)
        if not m:
            raise ConsortError(f"malformed for-each entry: {label_part!r}")
        item_var, source_text = m.group(1), m.group(2).strip()
        source_match = _SOURCE_RE.match(source_text)
        if not source_match:
            raise ConsortError(
                f"for-each source must be a single {{label}}[.field] reference, got {source_text!r}"
            )
        source_ref = LabelReference(
            label=source_match.group(1), field=source_match.group(2),
            raw=source_text, start=0, end=len(source_text),
        )
        overrides, base_task = _split_overrides(task_text)
        return Entry(
            kind=kind, label=f"__for_each_{order}__", task=base_task, overrides=overrides,
            order=order, group=seg["group"], is_for_each=True, item_var=item_var,
            source_ref=source_ref, parent_stage=seg["nested_under"], framed=False,
        )

    if not LABEL_RE.match(label_part):
        raise ConsortError(f"invalid agent-label: {label_part!r}")
    overrides, base_task = _split_overrides(task_text)
    return Entry(
        kind=kind, label=label_part, task=base_task, overrides=overrides, order=order,
        group=seg["group"], parent_stage=seg["nested_under"], framed=False,
    )


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


def _parse_entries(text: str) -> Tuple[Dict[str, object], List[Entry]]:
    logical_lines = _scan_logical_lines(text)
    segments = _segment_lines(logical_lines)

    directives: Dict[str, object] = {"!": None, "#": [], "$": [], "%": None, "*": None, "@": None}
    entries: List[Entry] = []
    order = 0

    for seg in segments:
        if seg["type"] == "directive":
            sym, value = seg["symbol"], seg["text"].strip()
            if sym in ACCUMULATING_TOP_SYMBOLS:
                directives[sym].append(value)
            else:
                directives[sym] = value
        else:
            entries.append(_finalize_entry_segment(seg, order))
            order += 1

    return directives, entries


# --------------------------------------------------------------------------
# Structural validation (Sections 2.1, 2.8, 2.9) and { } reference
# resolution (Section 2.11)
# --------------------------------------------------------------------------

def _validate_message_shape(directives: Dict[str, object], entries: List[Entry]) -> None:
    if entries and not directives.get("!"):
        raise MissingIntentError(
            "message contains ^/| entries but no top-level ! stating the goal they serve"
        )

    has_top_level_fanout = any(e.kind == "^" and e.group == ("top",) for e in entries)
    has_top_level_pipeline = any(e.kind == "|" and e.parent_stage is None for e in entries)
    if has_top_level_fanout and has_top_level_pipeline:
        raise MixedTopLevelDelegationError(
            "^ and | both appear unindented at the top level -- pick one shape "
            "at the top level and nest the other one level deep inside a single stage"
        )

    seen: Dict[str, int] = {}
    for e in entries:
        if e.is_for_each:
            continue
        if e.label in seen:
            raise DuplicateLabelError(
                f"agent-label {e.label!r} is used by more than one entry; labels must be "
                f"unique across the entire message"
            )
        seen[e.label] = e.order


def _validate_reference(ref: LabelReference, referencing_entry: Entry,
                         label_to_entry: Dict[str, Entry]) -> None:
    target = label_to_entry.get(ref.label)
    if target is None:
        raise UndefinedLabelError(f"'{referencing_entry.label}' references undefined label {{{ref.label}}}")
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
    label_to_entry: Dict[str, Entry] = {e.label: e for e in entries if not e.is_for_each}

    references: Dict[object, List[LabelReference]] = {}
    for entry in entries:
        key = entry.label if not entry.is_for_each else id(entry)
        entry_refs: List[LabelReference] = []

        if not entry.framed:
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
        # Framed entries (2.10): task text is opaque and never scanned for
        # { } references, so entry_refs stays empty.

        references[key] = entry_refs

    return references


def _collect_warnings(entries: List[Entry]) -> List[str]:
    warnings: List[str] = []
    for e in entries:
        if e.is_for_each and not e.framed:
            if not find_item_var_refs(e.task, e.item_var):
                warnings.append(
                    f"for-each entry (item_var={e.item_var!r}) does not reference "
                    f"%{e.item_var}% in its task template: {e.task!r}"
                )
    return warnings


def parse(text: str) -> ParsedMessage:
    """Parse `text` as a Consort message and validate its structure.

    Raises ConsortError (or a subclass) on the first structural problem
    found: an invalid { } reference, a duplicate agent-label, ^/| entries
    with no top-level !, ^ and | both at the top level, or a malformed
    framed-form header/length. Returns a ParsedMessage on success.
    """
    directives, entries = _parse_entries(text)
    _validate_message_shape(directives, entries)
    references = _resolve_references(entries)
    warnings = _collect_warnings(entries)
    return ParsedMessage(directives=directives, entries=entries, references=references, warnings=warnings)
