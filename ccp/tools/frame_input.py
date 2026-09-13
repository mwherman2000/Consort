"""Build a framed-form Consort block (spec 2.10) from one or more input
files, for injecting per-instance data (e.g. a patient record) into a CCP
message without risking accidental or adversarial symbol collision --
free-text clinical notes routinely contain a stray '#', '$', '|', or '*'
character that would otherwise be misread as a new directive.

Usage:
    python ccp/tools/frame_input.py <file-or-folder> [--symbol #] [--out PATH]

If given a folder, concatenates every file in it (sorted by name, files
only, not recursive) with a blank line between files -- e.g. a working
folder holding symptoms.txt, labs.txt, history.txt separately. If given
a single file, its content is used directly, e.g. one combined record
like ccp/samples/jane-doe-health-record.txt.

Computes the exact UTF-8 byte length of the resulting payload and emits
the framed block:

    #<N>:
    <payload>

The output is self-validated by round-tripping it through this repo's
own reference parser (parser.consort_parser) before being emitted, so a
byte-count mistake fails loudly here rather than silently once it
reaches an LLM.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from parser import consort_parser as cp  # noqa: E402

_ACCUMULATING = {"#", "$", "+"}
_SCALAR = {"!", "%", "*", "@"}


def collect_payload(source: Path) -> str:
    if source.is_dir():
        parts = [f.read_text(encoding="utf-8").strip() for f in sorted(source.iterdir()) if f.is_file()]
        if not parts:
            raise ValueError(f"{source} contains no files to frame")
        payload = "\n\n".join(parts)
    else:
        payload = source.read_text(encoding="utf-8")
    # The reference parser strips every directive value it stores (loose
    # or framed) for consistency (consort_parser._parse_entries); stripping
    # here too means the byte count we compute matches what a downstream
    # parse() will actually report back, so validate()'s equality check
    # is meaningful rather than failing on a harmless trailing newline.
    return payload.strip()


def build_framed_block(payload: str, symbol: str) -> str:
    length = len(payload.encode("utf-8"))
    return f"{symbol}{length}:\n{payload}"


def validate(block: str, symbol: str, payload: str) -> None:
    """Round-trip `block` through the reference parser.

    A bad byte count raises MalformedFramedFormError from parse() itself.
    For symbols whose parsed value is directly comparable (everything
    except ^/|, which need their own label:task split even when framed),
    also confirm the payload survived byte-for-byte.
    """
    wrapper = f"! validate framed block\n{block}\n"
    msg = cp.parse(wrapper)
    if symbol in _ACCUMULATING:
        actual = msg.directives[symbol][-1] if msg.directives[symbol] else None
    elif symbol in _SCALAR:
        actual = msg.directives[symbol]
    else:
        actual = None  # ^/| entries require label:task -- skip equality check
    if actual is not None and actual != payload:
        raise AssertionError("framed payload did not round-trip through the parser unchanged")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help="A file or folder of files to frame")
    ap.add_argument("--symbol", default="#", choices=list("!#$%*@^|+"),
                     help="Which Consort symbol to frame the payload under (default: #)")
    ap.add_argument("--out", type=Path, default=None,
                     help="Write the framed block here instead of printing to stdout")
    args = ap.parse_args()

    if not args.source.exists():
        ap.error(f"{args.source} does not exist")

    payload = collect_payload(args.source)
    block = build_framed_block(payload, args.symbol)
    validate(block, args.symbol, payload)

    byte_len = len(payload.encode("utf-8"))
    if args.out:
        args.out.write_text(block, encoding="utf-8")
        print(f"Wrote framed {args.symbol} block ({byte_len} bytes) to {args.out}", file=sys.stderr)
    else:
        print(block)


if __name__ == "__main__":
    main()
