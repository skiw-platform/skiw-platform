"""`python3 -m skiw_host.labels <commit> < migration_labels.json` (CI `publish` job; spec §8.4 H3
step 2; plan §3 M1h).

Reads the JSON that `manage.py migration_labels` printed inside the built image and prints the
image labels skiw-deploy reads, one `name=value` line each: the commit, the migration head and the
contract migrations (comma-joined, sorted, as `migration_labels` prints them; empty when there is
none). The input is checked exactly as skiw-deploy checks it on the host; anything else exits 1 and
prints nothing on stdout, so no label is ever built from output that is not a label list.
"""

import sys
from collections.abc import Sequence
from typing import TextIO

from skiw_host.bootstrap_db import Failed
from skiw_host.deploy import (
    COMMIT,
    COMMIT_LABEL,
    CONTRACTS_LABEL,
    HEAD_LABEL,
    parse_migration_labels,
)

MAX_INPUT = 1 << 20  # bytes; the list of every migration the image ships


def labels(commit: str, text: str) -> list[str]:
    if not COMMIT.fullmatch(commit):
        raise Failed("the commit is not 40 lowercase hex characters")
    found = parse_migration_labels(text)
    head, contracts = ",".join(found["head"]), ",".join(found["contracts"])
    return [f"{COMMIT_LABEL}={commit}", f"{HEAD_LABEL}={head}", f"{CONTRACTS_LABEL}={contracts}"]


def main(argv: Sequence[str] | None = None, stdin: TextIO | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    text = (sys.stdin if stdin is None else stdin).read(MAX_INPUT + 1)
    try:
        if len(args) != 1 or len(text) > MAX_INPUT:
            raise Failed("usage: skiw_host.labels <commit> < migration_labels.json (at most 1 MiB)")
        lines = labels(args[0], text)
    except (Failed, ValueError) as exc:  # ValueError: not JSON; the input itself is never shown
        reason = exc if isinstance(exc, Failed) else "not JSON"
        print(f"skiw_host.labels: refused: {reason}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
