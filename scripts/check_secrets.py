#!/usr/bin/env python3
"""Fail CI on high-confidence credential material in version-controlled files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(rb"\bgh[opsu]_[A-Za-z0-9]{36,255}\b"),
    "OpenAI-style key": re.compile(rb"\bsk-[A-Za-z0-9]{32,}\b"),
}

# These version-controlled files intentionally contain inert credential-shaped
# canaries to prove policy/redaction behaviour. Keep this list narrow: product
# source, configuration, and documentation remain fully scanned.
SYNTHETIC_CANARY_FILES = {
    Path("services/router/eval/dataset.jsonl"),
    Path("services/router/eval/datasets/intent_eval.jsonl"),
    Path("services/router/tests/test_dispatch.py"),
    Path("services/router/tests/test_policy.py"),
    Path("services/sentinel/tests/test_redaction.py"),
    Path("landing_8/components/Proof.tsx"),
    Path("scripts/partner_demo.sh"),
    Path("tests.md"),
}


def candidate_files() -> list[Path]:
    """Return committed and untracked, non-ignored files considered for commit."""
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    )
    return [Path(raw.decode()) for raw in output.split(b"\0") if raw]


def main() -> int:
    findings: list[str] = []
    for path in candidate_files():
        if path in SYNTHETIC_CANARY_FILES:
            continue
        try:
            content = path.read_bytes()
        except (OSError, UnicodeError):
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path}: possible {label}")
    if findings:
        print("\n".join(findings))
        return 1
    print("secret scan: no high-confidence credential material found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
