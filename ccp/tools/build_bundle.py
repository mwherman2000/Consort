"""Assemble a complete, ready-to-paste CCP prompt bundle: the Consort
specification, ccp.consort, a domain-specific process prompt, and
(optionally) per-instance data framed as a # block -- in the order
documented in ccp/COORDINATION-FRAMEWORK.md's "Delivery Order" section.

This is the simplest way to run a CCP pipeline end to end: concatenate
everything into one prompt and paste it into any LLM chat interface as a
single message. No orchestration code is needed at this level -- a `|`
pipeline executes as a single reasoning pass, so one combined prompt is
sufficient to exercise the whole thing (though it won't exercise the
closed-loop/checkpoint-restart pattern, which needs real per-stage
orchestration -- see ccp/COORDINATION-FRAMEWORK.md's "Closed-Loop
Processes" section).

Usage:
    python ccp/tools/build_bundle.py ccp/medical-care.consort \
        --data ccp/samples/jane-doe-health-record.txt \
        --out ccp/samples/jane-doe-full-run.consort
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import frame_input  # noqa: E402

_SPEC_PATH = _REPO_ROOT / "CONSORT Markdown for Intelligent Coordination.txt"
_CCP_PATH = _REPO_ROOT / "ccp" / "ccp.consort"


def build_bundle(domain_path: Path, data_path: Optional[Path], data_symbol: str = "#") -> str:
    parts = [
        _SPEC_PATH.read_text(encoding="utf-8").strip(),
        _CCP_PATH.read_text(encoding="utf-8").strip(),
        domain_path.read_text(encoding="utf-8").strip(),
    ]
    if data_path is not None:
        payload = frame_input.collect_payload(data_path)
        block = frame_input.build_framed_block(payload, data_symbol)
        frame_input.validate(block, data_symbol, payload)
        parts.append(block)
    return "\n\n".join(parts) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("domain", type=Path, help="The domain-specific .consort prompt (e.g. ccp/medical-care.consort)")
    ap.add_argument("--data", type=Path, default=None,
                     help="A raw data file or folder to frame and append (e.g. a patient record)")
    ap.add_argument("--data-symbol", default="#", choices=list("!#$%*@^|+"),
                     help="Symbol to frame --data under (default: #)")
    ap.add_argument("--out", type=Path, default=None, help="Write the bundle here instead of stdout")
    args = ap.parse_args()

    for p in (_SPEC_PATH, _CCP_PATH, args.domain):
        if not p.exists():
            ap.error(f"{p} does not exist")
    if args.data is not None and not args.data.exists():
        ap.error(f"{args.data} does not exist")

    bundle = build_bundle(args.domain, args.data, args.data_symbol)

    if args.out:
        args.out.write_text(bundle, encoding="utf-8")
        print(f"Wrote bundle ({len(bundle.encode('utf-8'))} bytes) to {args.out}", file=sys.stderr)
    else:
        print(bundle)


if __name__ == "__main__":
    main()
