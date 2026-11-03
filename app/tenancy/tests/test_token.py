"""The committed tenant-token vector (spec §4.2 item 2, v1.21: "the exact bytes are pinned by a
committed test vector that both implementations must reproduce"). The minter is checked here; the
live test `test_current_agency_live.py` checks that `guard.current_agency()` accepts the same
vector inputs. The MAC was cross-checked once with `openssl dgst -sha256 -mac HMAC`. No database."""

import uuid

import pytest

from tenancy.token import mac_input, mint

VECTOR_KEY = bytes(range(32))  # a fixed, public test key; never a real one
VECTOR_DATABASE = "skiw"
VECTOR_AGENCY = uuid.UUID("0f1e2d3c-4b5a-4968-8776-a5b4c3d2e1f0")
VECTOR_XID = 123456789
VECTOR_INPUT = (
    "0000000e" + b"skiw-tenant-v1".hex() + "00000004" + b"skiw".hex()
    + "00000010" + "0f1e2d3c4b5a49688776a5b4c3d2e1f0" + "00000008" + "00000000075bcd15"
)  # fmt: skip
VECTOR = (
    "v1.0f1e2d3c-4b5a-4968-8776-a5b4c3d2e1f0.123456789.8c7mpnTMYZVOhtlIg6Q58-fmJA9uHXNHRV_mUy2kyzk"
)


def test_the_mac_input_is_the_four_length_prefixed_fields() -> None:
    assert mac_input(VECTOR_DATABASE, VECTOR_AGENCY, VECTOR_XID).hex() == VECTOR_INPUT


def test_the_minter_reproduces_the_committed_vector() -> None:
    assert mint(1, VECTOR_KEY, VECTOR_DATABASE, VECTOR_AGENCY, VECTOR_XID) == VECTOR


def test_the_largest_version_and_xid_keep_the_form() -> None:
    minted = mint(999_999, VECTOR_KEY, VECTOR_DATABASE, VECTOR_AGENCY, 2**64 - 1)
    version, agency, xid, mac = minted.split(".")
    assert (version, agency, xid) == ("v999999", str(VECTOR_AGENCY), "18446744073709551615")
    assert len(mac) == 43
    assert "=" not in mac


def test_a_multibyte_database_name_is_counted_in_bytes() -> None:
    assert mac_input("é", VECTOR_AGENCY, 0)[18:24] == b"\x00\x00\x00\x02\xc3\xa9"


@pytest.mark.parametrize(("version", "xid"), [(0, 1), (1_000_000, 1), (1, -1), (1, 2**64)])
def test_out_of_range_values_are_refused(version: int, xid: int) -> None:
    with pytest.raises(ValueError, match="out of range"):
        mint(version, VECTOR_KEY, VECTOR_DATABASE, VECTOR_AGENCY, xid)
