"""The escrow bundle, encrypted with the pinned age binary (spec §8.4 H4; plan §2: age v1.3.2).

Only public recipients are accepted. No message carries a recipient value or bundle content.
"""

import os
import re
import subprocess
from pathlib import Path

AGE = Path("/usr/local/bin/age")  # checksum-verified install on hosts (DECISIONS 2026-10-14, M1f)
AGE_VERSION = "v1.3.2"
HEADER = b"age-encryption.org/v1\n"
RECIPIENT = re.compile(r"age1[0-9a-z]{58,}")
SETTING = "SKIW_ESCROW_RECIPIENTS"


class EscrowError(Exception):
    pass


def recipients(env_file: Path) -> list[str]:
    """The owner's public escrow recipients from the host env file (G5); fails closed."""
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        raise EscrowError(f"{env_file} cannot be read") from None
    values = [
        value
        for line in lines
        if line.startswith(f"{SETTING}=")
        for value in line.partition("=")[2].replace(",", " ").split()
    ]
    if not values:
        raise EscrowError(f"{SETTING} is empty in {env_file}: the owner's public recipients (G5)")
    for value in values:
        if "AGE-SECRET-KEY-" in value.upper():
            raise EscrowError(
                f"{SETTING} holds a private age identity (not shown): remove it from this host "
                "and treat that identity as exposed"
            )
        if not RECIPIENT.fullmatch(value):
            raise EscrowError(f"{SETTING} holds a value that is not an age1 recipient (not shown)")
    return values


def encrypt(path: Path, plaintext: bytes, to: list[str], age: Path) -> None:
    """Encrypt `plaintext` to `to` into the new 0400 file `path`; nothing is left on failure."""
    try:
        version = subprocess.run([age, "--version"], capture_output=True, text=True, check=False)  # noqa: S603 - fixed binary, no shell
    except OSError:
        raise EscrowError(f"age cannot run from {age}") from None
    if version.returncode != 0 or version.stdout.strip() != AGE_VERSION:
        raise EscrowError(f"{age} is not the pinned age {AGE_VERSION}")
    flags = [arg for recipient in to for arg in ("--recipient", recipient)]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        with os.fdopen(fd, "wb") as out:
            result = subprocess.run(  # noqa: S603 - fixed binary and flags, no shell
                [age, "--encrypt", *flags], input=plaintext, stdout=out, stderr=subprocess.DEVNULL
            )
            os.fsync(out.fileno())
        with path.open("rb") as written:
            head = written.read(len(HEADER))
        if result.returncode != 0 or head != HEADER:
            raise EscrowError(f"age wrote no encrypted bundle (exit {result.returncode})")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
