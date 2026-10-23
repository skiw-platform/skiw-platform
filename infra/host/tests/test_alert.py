"""The alert sender (spec §8.4 H7; plan §3 M1j; UNI-09, G8).

The payload is exactly check, host and value, and the value is scrubbed. Without a channel the
alert reaches the journal only and is not delivered. No transport is built yet (M1j-2): any
SKIW_ALERT_* value refuses, and the host env files keep them empty until G8.
"""

import secrets
import time
from pathlib import Path

import pytest

from skiw_host import alert
from skiw_host.alert import Alert, deliver
from skiw_host.bootstrap_secrets import Refused

HOST = Path(__file__).resolve().parents[1]
WHERE = "staging:vps-1"


def test_the_payload_is_exactly_check_host_and_value() -> None:
    message = Alert("disk", WHERE, "/var/lib/docker space 83% used")
    assert message.payload() == {
        "check": "disk",
        "host": WHERE,
        "value": "/var/lib/docker space 83% used",
    }
    assert (
        message.render() == f"check: disk\nhost: {WHERE}\nvalue: /var/lib/docker space 83% used\n"
    )


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ("mail ops.lead@example.com now", "mail [email] now"),
        ("a@b", "[email]"),
        ("ic 900101-14-5678 seen", "ic [ic] seen"),
        ("ic 900101145678", "ic [ic]"),
        ("id=900101145678;", "id=[ic];"),
        ("9001011456789 is 13 digits", "9001011456789 is 13 digits"),  # not an IC shape
        ("line\nbreak\x1b[31m", "line break [31m"),
    ],
)
def test_the_value_is_scrubbed_of_emails_ic_numbers_and_control_characters(
    value: str, shown: str
) -> None:
    assert Alert("x", WHERE, value).value == shown  # UNI-09


def test_the_value_is_capped() -> None:
    assert len(Alert("x", WHERE, "9" * 1000).value) == alert.VALUE_MAX


@pytest.mark.parametrize(
    ("check", "host"), [("Disk", WHERE), ("disk check", WHERE), ("disk", "dev:x"), ("disk", "a@b")]
)
def test_a_check_or_host_that_is_not_a_plain_name_is_refused(check: str, host: str) -> None:
    with pytest.raises(ValueError, match="plain name"):
        Alert(check, host, "v")


class Fake:
    def __init__(self, error: BaseException | None = None, wait: float = 0) -> None:
        self.sent: list[Alert] = []
        self.error, self.wait = error, wait

    def send(self, message: Alert) -> None:
        if self.wait:
            time.sleep(self.wait)
        if self.error:
            raise self.error
        self.sent.append(message)


def test_without_a_channel_the_alert_goes_to_the_journal_and_is_not_delivered() -> None:
    journal: list[str] = []
    assert deliver(Alert("disk", WHERE, "full"), None, journal.append) is False
    assert journal == [
        f"disk {WHERE} full",
        "disk: not sent off the host: no alert channel (G8 open)",
    ]


def test_a_failure_is_named_by_type_never_its_text() -> None:
    planted = secrets.token_hex(16)
    journal: list[str] = []
    error = ConnectionRefusedError(f"refused {planted}")
    assert deliver(Alert("disk", WHERE, "full"), Fake(error), journal.append) is False
    assert journal[-1] == "disk: not sent off the host (ConnectionRefusedError)"
    assert not any(planted in line for line in journal)


def test_one_deadline_bounds_a_send() -> None:
    journal: list[str] = []
    start = time.monotonic()
    assert deliver(Alert("disk", WHERE, "full"), Fake(wait=5), journal.append, bound=0.2) is False
    assert time.monotonic() - start < 2 and journal[-1].endswith("(Deadline)")


def values(**extra: str) -> dict[str, str]:
    return {**dict.fromkeys(alert.KEYS, ""), **extra}


def test_no_alert_setting_is_off() -> None:
    assert alert.channel(values()) is None
    assert alert.channel({}) is None


@pytest.mark.parametrize(
    "key", ["SKIW_ALERT_CHANNEL", "SKIW_ALERT_SERVER", "SKIW_ALERT_FROM", "SKIW_ALERT_TO"]
)
def test_any_alert_setting_refuses_until_a_transport_is_built(key: str) -> None:
    with pytest.raises(Refused, match="M1j-2"):
        alert.channel(values(**{key: "x"}))


def test_production_and_staging_send_nothing_off_the_host_until_g8() -> None:
    for name in ("production.env", "staging.env", "ci.env"):
        lines = (HOST / "env" / name).read_text().splitlines()
        assert "SKIW_ALERT_CHANNEL=" in lines, name  # G8 open, UNI-11 not recorded
