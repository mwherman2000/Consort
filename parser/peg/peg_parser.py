"""PEG-based reference parser for the Consort Prompt DSL (spec v0.12).

Drives parser/peg/consort.peg (loaded via parsimonious) to do the actual
tokenizing/parsing work that parser/consort_parser.py does with hand-rolled
regexes and string checks: physical-line classification (Section 3),
<agent-label> ":" <task> splitting (2.8), for-each header parsing (2.8),
inline-override splitting (2.8/2.9), and { } label-reference / \\{-escape
tokenization (2.11).

What is, and isn't, PEG-driven here -- and why:

  - Framed-form's length-prefixed byte payload (2.10) is resolved by
    reusing consort_parser.scan_logical_lines(), NOT by this grammar.
    The number of bytes to consume is itself part of the input, a
    data-dependent ("context-sensitive") fact no context-free PEG rule
    can express -- consort.peg's header comment explains this in full.

  - The stateful bookkeeping of "which directive or entry is currently
    accumulating continuation lines" and "what pipe stage, if any, is a
    later indented ^ line nested under" (Section 2.9) is done by a small
    Python state machine (_segment_records, below), not by the grammar.
    A PEG rule has no notion of "what came several lines ago and is still
    open" without an explicit lexer/INDENT-DEDENT-style preprocessing
    pass -- the same reason Python's own grammar doesn't parse indentation
    directly either. Every other structural decision -- is *this* line
    blank, escaped, a directive/entry start, or a continuation; how does
    *this* entry's assembled text split into label/task, overrides, or
    { } references -- is delegated to consort.peg.

Validation (agent-label uniqueness, undefined/forward/sibling-^ reference
checks, missing-!, mixed ^/| at the top level, the for-each %item-var%
warning) is intentionally NOT reimplemented here: it's the same structural
rule regardless of which parser produced the Entry objects, so this module
calls the shared, already-tested implementation in consort_parser.py
instead of maintaining a second copy that could quietly drift out of sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from parsimonious.exceptions import IncompleteParseError, ParseError
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

from ..consort_parser import (
    ACCUMULATING_OVERRIDE_SYMBOLS,
    ACCUMULATING_TOP_SYMBOLS,
    LABEL_RE,
    ConsortError,
    Entry,
    LabelReference,
    ParsedMessage,
    collect_warnings,
    scan_logical_lines,
    validate_message_shape,
    validate_reference,
)

_GRAMMAR_PATH = Path(__file__).with_name("consort.peg")
GRAMMAR = Grammar(_GRAMMAR_PATH.read_text(encoding="utf-8"))


def _unwrap(children):
    if children and len(children) == 1:
        return children[0]
    return children or ""


# --------------------------------------------------------------------------
# Layer 2c: { } LABEL REFERENCES and \{ escaping (Section 2.11)
# --------------------------------------------------------------------------

class _ContentVisitor(NodeVisitor):
    def generic_visit(self, node, children):
        return _unwrap(children) if children else node.text

    def visit_content(self, node, children):
        # Always a flat list, even for zero or exactly one token -- the
        # generic single-child unwrap would otherwise collapse a one-token
        # message into a bare item instead of a one-item list.
        return list(children)

    def visit_label_ref(self, node, children):
        label = children[1]
        field_part = children[3]
        field = field_part[1] if isinstance(field_part, list) and len(field_part) == 2 else None
        return LabelReference(label=label, field=field, raw=node.text, start=node.start, end=node.end)

    def visit_escaped_brace(self, node, children):
        return "{"  # \{ renders as a literal brace (2.11)


def find_label_refs(text: str) -> List[LabelReference]:
    """Tokenize `text` and return every structurally well-formed { } token.

    Mirrors consort_parser.find_label_refs's contract exactly (same
    escaping and non-matching-brace behavior), but the tokenizing itself
    is done by consort.peg's `content` rule instead of a hand-written
    regex scan.
    """
    tree = GRAMMAR["content"].parse(text)
    tokens = _ContentVisitor().visit(tree)
    return [t for t in tokens if isinstance(t, LabelReference)]


def render_escapes(text: str) -> str:
    tree = GRAMMAR["content"].parse(text)
    tokens = _ContentVisitor().visit(tree)
    return "".join(t.raw if isinstance(t, LabelReference) else t for t in tokens)


def _parse_label_ref_only(text: str) -> LabelReference:
    try:
        tree = GRAMMAR["label_ref_only"].parse(text)
    except (ParseError, IncompleteParseError) as exc:
        raise ConsortError(
            f"for-each source must be a single {{label}}[.field] reference, got {text!r}"
        ) from exc
    return _ContentVisitor().visit(tree)


# --------------------------------------------------------------------------
# Layer 2a/2b: entry_body (label:task split) and for_each_header
# --------------------------------------------------------------------------

class _EntryBodyVisitor(NodeVisitor):
    def generic_visit(self, node, children):
        return _unwrap(children) if children else node.text

    def visit_entry_body(self, node, children):
        return (children[0].strip(), children[3])


class _ForEachHeaderVisitor(NodeVisitor):
    def generic_visit(self, node, children):
        return _unwrap(children) if children else node.text

    def visit_for_each_header(self, node, children):
        return (children[2], children[6])

    def visit_label_ref(self, node, children):
        # Reuse the same shape/positions as _ContentVisitor for consistency.
        label = children[1]
        field_part = children[3]
        field = field_part[1] if isinstance(field_part, list) and len(field_part) == 2 else None
        return LabelReference(label=label, field=field, raw=node.text, start=node.start, end=node.end)


def _split_label_and_task(rest: str) -> Tuple[str, str]:
    try:
        tree = GRAMMAR["entry_body"].parse(rest)
    except (ParseError, IncompleteParseError) as exc:
        raise ConsortError(f"entry has no structural ':' separating label from task: {rest!r}") from exc
    return _EntryBodyVisitor().visit(tree)


# --------------------------------------------------------------------------
# Layer 2d: inline overrides /$ /% /@ /* (Section 2.8/2.9)
# --------------------------------------------------------------------------

class _OverridesVisitor(NodeVisitor):
    def generic_visit(self, node, children):
        return _unwrap(children) if children else node.text

    def visit_task_with_overrides(self, node, children):
        base, overrides = children
        return (base, overrides)

    def visit_overrides(self, node, children):
        # Always a flat list, even for zero or exactly one override -- see
        # _ContentVisitor.visit_content for why this can't be left to
        # generic_visit's single-child unwrap.
        return list(children)

    def visit_base_run(self, node, children):
        return node.text

    def visit_value_run(self, node, children):
        return node.text

    def visit_override(self, node, children):
        sym, _ws0, value = children
        return (sym, value.strip())

    def visit_override_start(self, node, children):
        # ws1 "/" override_symbol boundary -- only the symbol matters.
        return children[2]

    def visit_override_symbol(self, node, children):
        return node.text


def split_overrides(text: str) -> Tuple[Dict[str, str], str]:
    """Split `text`'s inline /$ /% /@ /* overrides from its base task/value.

    A single leading space is prepended before parsing so that
    override_start's "preceded by whitespace" requirement (consort.peg)
    is satisfied uniformly even for an override at the very start of the
    real text -- see the grammar file's comment on task_with_overrides.
    """
    tree = GRAMMAR["task_with_overrides"].parse(" " + text)
    base, override_list = _OverridesVisitor().visit(tree)
    overrides: Dict[str, str] = {}
    for sym, value in override_list:
        if sym in ACCUMULATING_OVERRIDE_SYMBOLS and sym in overrides:
            overrides[sym] = f"{overrides[sym]}; {value}"
        else:
            overrides[sym] = value
    return overrides, base.strip()


# --------------------------------------------------------------------------
# Layer 1: physical-line classification (Section 3)
# --------------------------------------------------------------------------

@dataclass
class _Rec:
    kind: str  # 'framed' | 'blank' | 'escaped' | 'symbol' | 'continuation'
    indent: int
    symbol: Optional[str] = None
    text: str = ""
    payload: str = ""


class _LineVisitor(NodeVisitor):
    def __init__(self, indent: int):
        super().__init__()
        self.indent = indent

    def generic_visit(self, node, children):
        return _unwrap(children) if children else node.text

    def visit_blank_line(self, node, children):
        return _Rec(kind="blank", indent=self.indent)

    def visit_escaped_line(self, node, children):
        return _Rec(kind="escaped", indent=self.indent, text=children[3])

    def visit_symbol_line(self, node, children):
        return _Rec(kind="symbol", indent=self.indent, symbol=children[1], text=children[2])

    def visit_continuation_line(self, node, children):
        return _Rec(kind="continuation", indent=self.indent, text=children[4])


def _classify(logical_line) -> _Rec:
    if logical_line.framed:
        return _Rec(
            kind="framed", indent=logical_line.indent,
            symbol=logical_line.directive_symbol, payload=logical_line.content,
        )
    tree = GRAMMAR["single_line"].parse(logical_line.content + "\n")
    return _LineVisitor(logical_line.indent).visit(tree)


# --------------------------------------------------------------------------
# Stateful segment accumulation (Section 2.9) -- see module docstring for
# why this orchestration isn't itself expressed as a PEG rule.
# --------------------------------------------------------------------------

def _open_entry_segment(kind: str, rest: str, indent: int, nested_under: Optional[str],
                         group: Optional[Tuple]) -> dict:
    label, task_start = _split_label_and_task(rest)
    return {
        "type": "entry", "kind": kind, "indent": indent, "label": label,
        "task_buf": task_start, "nested_under": nested_under, "group": group, "framed": False,
    }


def _open_entry_segment_framed(kind: str, payload: str, indent: int,
                                nested_under: Optional[str], group: Optional[Tuple]) -> dict:
    label, sep, task = payload.partition(":")
    if not sep:
        raise ConsortError(f"framed entry has no structural ':' separating label from task: {payload!r}")
    return {
        "type": "entry", "kind": kind, "indent": indent, "label": label.strip(),
        "task_buf": task.strip(), "nested_under": nested_under, "group": group, "framed": True,
    }


def _segment_records(records: List[_Rec]) -> List[dict]:
    segments: List[dict] = []
    current: Optional[dict] = None
    enclosing_pipe_label: Optional[str] = None

    def close_current():
        nonlocal current
        if current is not None:
            segments.append(current)
            current = None

    def append_text(text: str):
        if current is None:
            return
        key = "task_buf" if current["type"] == "entry" else "text"
        current[key] = f"{current[key]} {text}" if current[key] else text

    for rec in records:
        if rec.kind == "framed":
            close_current()
            sym = rec.symbol
            if sym in "^|":
                nested = rec.indent > 0 and enclosing_pipe_label is not None
                seg = _open_entry_segment_framed(
                    sym, rec.payload, rec.indent,
                    enclosing_pipe_label if nested else None,
                    ("nested", enclosing_pipe_label) if nested else (("top",) if sym == "^" else None),
                )
                segments.append(seg)
                if rec.indent == 0:
                    enclosing_pipe_label = seg["label"] if sym == "|" else None
            else:
                segments.append({"type": "directive", "symbol": sym, "text": rec.payload, "framed": True})
                if rec.indent == 0:
                    enclosing_pipe_label = None
            continue

        if rec.kind == "blank":
            close_current()
            enclosing_pipe_label = None
            continue

        if rec.kind == "escaped":
            append_text(rec.text)
            continue

        if rec.kind == "symbol":
            sym, rest = rec.symbol, rec.text.strip()
            if rec.indent == 0:
                close_current()
                if sym in "^|":
                    group = ("top",) if sym == "^" else None
                    current = _open_entry_segment(sym, rest, 0, None, group)
                    enclosing_pipe_label = current["label"] if sym == "|" else None
                else:
                    current = {"type": "directive", "symbol": sym, "text": rest, "framed": False}
                    enclosing_pipe_label = None
            elif sym == "^" and enclosing_pipe_label is not None:
                close_current()
                current = _open_entry_segment(
                    "^", rest, rec.indent, enclosing_pipe_label, ("nested", enclosing_pipe_label)
                )
            else:
                # Indentation carries meaning only for a nested ^ under an
                # active | stage (2.9/3) -- anything else indented is plain
                # continuation text, symbol character included.
                append_text(sym + rest)
            continue

        if rec.kind == "continuation":
            append_text(rec.text)
            continue

    close_current()
    return segments


# --------------------------------------------------------------------------
# Finalize segments into Entry / directive objects
# --------------------------------------------------------------------------

def _finalize_entry_segment(seg: dict, order: int) -> Entry:
    kind = seg["kind"]
    label = seg["label"]
    task_text = seg["task_buf"].strip()

    if seg["framed"]:
        # Framed payloads are opaque (2.10): only the structural label:task
        # split is honored; the task text is never handed to for-each,
        # override, or { }-reference parsing.
        return Entry(
            kind=kind, label=label, task=task_text, overrides={}, order=order,
            group=seg["group"], is_for_each=False, parent_stage=seg["nested_under"], framed=True,
        )

    is_for_each = label == "for-each" or label.startswith("for-each ")
    if is_for_each:
        try:
            tree = GRAMMAR["for_each_header"].parse(label)
        except (ParseError, IncompleteParseError) as exc:
            raise ConsortError(f"malformed for-each entry: {label!r}") from exc
        item_var, source_ref = _ForEachHeaderVisitor().visit(tree)
        overrides, base_task = split_overrides(task_text)
        return Entry(
            kind=kind, label=f"__for_each_{order}__", task=base_task, overrides=overrides,
            order=order, group=seg["group"], is_for_each=True, item_var=item_var,
            source_ref=source_ref, parent_stage=seg["nested_under"], framed=False,
        )

    if not LABEL_RE.match(label):
        raise ConsortError(f"invalid agent-label: {label!r}")
    overrides, base_task = split_overrides(task_text)
    return Entry(
        kind=kind, label=label, task=base_task, overrides=overrides, order=order,
        group=seg["group"], parent_stage=seg["nested_under"], framed=False,
    )


def _finalize_segments(segments: List[dict]) -> Tuple[Dict[str, object], List[Entry]]:
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
# { } reference resolution -- structurally identical to consort_parser's
# _resolve_references, reusing its validate_reference (undefined/forward/
# sibling-^ checks are the same rule regardless of which parser found the
# reference) but scanning with THIS module's PEG-driven find_label_refs,
# so parse()'s output genuinely reflects grammar-driven tokenization
# end to end rather than silently falling back to the regex scanner.
# --------------------------------------------------------------------------

def _resolve_references(entries: List[Entry]) -> Dict[object, List[LabelReference]]:
    label_to_entry: Dict[str, Entry] = {e.label: e for e in entries if not e.is_for_each}

    references: Dict[object, List[LabelReference]] = {}
    for entry in entries:
        key = entry.label if not entry.is_for_each else id(entry)
        entry_refs: List[LabelReference] = []

        if not entry.framed:
            for ref in find_label_refs(entry.task):
                validate_reference(ref, entry, label_to_entry)
                entry_refs.append(ref)
            for value in entry.overrides.values():
                for ref in find_label_refs(value):
                    validate_reference(ref, entry, label_to_entry)
                    entry_refs.append(ref)
            if entry.is_for_each:
                validate_reference(entry.source_ref, entry, label_to_entry)
                entry_refs.append(entry.source_ref)
        # Framed entries (2.10): task text is opaque and never scanned for
        # { } references, so entry_refs stays empty.

        references[key] = entry_refs

    return references


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def parse(text: str) -> ParsedMessage:
    """Parse `text` as a Consort message using the PEG grammar in consort.peg.

    Produces the same ParsedMessage shape, and raises the same ConsortError
    subclasses, as consort_parser.parse() -- the two are meant to agree on
    every input; see parser/peg/tests for cross-checks against the other
    parser's test suite.
    """
    logical_lines = scan_logical_lines(text)
    records = [_classify(ll) for ll in logical_lines]
    segments = _segment_records(records)
    directives, entries = _finalize_segments(segments)
    validate_message_shape(directives, entries)
    references = _resolve_references(entries)
    warnings = collect_warnings(entries)
    return ParsedMessage(directives=directives, entries=entries, references=references, warnings=warnings)
