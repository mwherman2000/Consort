"""Dispatch a CCP prompt bundle to the Claude API and print the response.

Assembles the same pieces as build_bundle.py -- the Consort
specification, ccp.consort, a domain-specific process prompt, and
(optionally) per-instance data framed as a # block -- but instead of
writing them to one file for manual copy-paste, sends them as a single
Claude API call: the specification and ccp.consort as the system
prompt (establishing how to interpret Consort and the CCP framework),
the domain prompt and framed data as the user message (the actual work
order), per the delivery order in ccp/COORDINATION-FRAMEWORK.md.

Requires the `anthropic` package (pip install anthropic) and an
ANTHROPIC_API_KEY environment variable. Neither is required just to
read this file or use build_bundle.py/frame_input.py -- only to
actually execute this script.

Usage:
    python ccp/tools/run_pipeline.py ccp/medical-care.consort \
        --data ccp/samples/jane-doe-health-record.txt \
        --out ccp/samples/jane-doe-run-output.md
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import frame_input  # noqa: E402

_SPEC_PATH = _REPO_ROOT / "CONSORT Markdown for Intelligent Coordination.txt"
_CCP_PATH = _REPO_ROOT / "ccp" / "ccp.consort"

_DEFAULT_MODEL = "claude-sonnet-5"
_DEFAULT_MAX_TOKENS = 8000


def build_system_and_user(domain_path: Path, data_path: Optional[Path], data_symbol: str = "#") -> Tuple[str, str]:
    """Split the bundle into (system, user) the way the API expects.

    System = the spec + ccp.consort: how to interpret Consort, and the
    domain-agnostic CCP framework. User = the domain-specific prompt
    (the actual work order) + any framed per-instance data. This mirrors
    build_bundle.py's single-file concatenation, just split across the
    API's two roles instead of one pasted blob.
    """
    system = (
        _SPEC_PATH.read_text(encoding="utf-8").strip()
        + "\n\n"
        + _CCP_PATH.read_text(encoding="utf-8").strip()
    )

    user_parts = [domain_path.read_text(encoding="utf-8").strip()]
    if data_path is not None:
        payload = frame_input.collect_payload(data_path)
        block = frame_input.build_framed_block(payload, data_symbol)
        frame_input.validate(block, data_symbol, payload)
        user_parts.append(block)
    user = "\n\n".join(user_parts)

    return system, user


def run(domain_path: Path, data_path: Optional[Path], data_symbol: str, model: str, max_tokens: int) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise SystemExit("The 'anthropic' package is required: pip install anthropic") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set the ANTHROPIC_API_KEY environment variable before running this.")

    system, user = build_system_and_user(domain_path, data_path, data_symbol)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("domain", type=Path, help="The domain-specific .consort prompt (e.g. ccp/medical-care.consort)")
    ap.add_argument("--data", type=Path, default=None,
                     help="A raw data file or folder to frame and append (e.g. a patient record)")
    ap.add_argument("--data-symbol", default="#", choices=list("!#$%*@^|+"),
                     help="Symbol to frame --data under (default: #)")
    ap.add_argument("--model", default=_DEFAULT_MODEL, help=f"Claude model ID (default: {_DEFAULT_MODEL})")
    ap.add_argument("--max-tokens", type=int, default=_DEFAULT_MAX_TOKENS,
                     help=f"Max output tokens (default: {_DEFAULT_MAX_TOKENS})")
    ap.add_argument("--out", type=Path, default=None, help="Write the model's response here instead of stdout")
    args = ap.parse_args()

    for p in (_SPEC_PATH, _CCP_PATH, args.domain):
        if not p.exists():
            ap.error(f"{p} does not exist")
    if args.data is not None and not args.data.exists():
        ap.error(f"{args.data} does not exist")

    output = run(args.domain, args.data, args.data_symbol, args.model, args.max_tokens)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"Wrote response ({len(output.encode('utf-8'))} bytes) to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
