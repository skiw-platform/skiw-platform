"""Enrolment links (spec AUTH-08; plan M3 §3 M3e, owner Q5 (a)). The operator's `accounts_invite`
creates an `invited` user of the deployment agency and prints a link; the user follows it and sets
a password (`POST /api/auth/enrol` in accounts.views calls `redeem`). The link expires after
`SKIW_ENROL_LINK_MIN` minutes and works once: its token is a `TimestampSigner` signature (salt
`skiw-enrol-v1`, key `SECRET_KEY`) over the user id, the agency id and a fingerprint of the row's
`login_blob_ct` (empty while it is NULL), and setting the password changes that blob.

The user stays `invited` after `redeem`, so the password alone signs nobody in (the password step
refuses a status other than `active`). The first second factor (M3f, M3g) makes the user `active`
(Flow 5.1 (4))."""

import hashlib
import uuid
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError

from accounts.auth import blob, passwords
from accounts.auth.password_step import Verified
from accounts.user_model import AppUser
from tenancy.binding import with_agency

SALT = "skiw-enrol-v1"
NAME_MAX = 200  # app_user.display_name


class Refused(Exception):
    """The invite was not made; the message is for the operator and names no other account."""


def fingerprint(sealed: bytes | memoryview | None) -> str:
    return "" if sealed is None else hashlib.sha256(bytes(sealed)).hexdigest()


def _token(user: AppUser) -> str:
    value = {"u": str(user.id), "a": str(user.agency_id), "f": fingerprint(user.login_blob_ct)}
    return signing.TimestampSigner(salt=SALT).sign_object(value)


def invite(email: str, name: str) -> str:
    """A new link for `email`: a new `invited` user, or an existing one that has not finished
    enrolling (a new link over the row as it is now). Anyone else is refused."""
    email = blob.normalise_email(email)  # the form the lookup and the blob's AAD use
    try:
        validate_email(email)
    except ValidationError as error:
        raise Refused("not an email address") from error
    if len(email) > blob.EMAIL_MAX:
        raise Refused(f"the address is longer than {blob.EMAIL_MAX} characters")
    if "\x00" in name or not 0 < len(name.strip()) <= NAME_MAX:
        raise Refused(f"the name must be 1 to {NAME_MAX} characters")
    agency, _ = settings.SKIW_DEPLOYMENT_AGENCY()
    try:
        with with_agency(agency):
            user = AppUser.objects.select_for_update().filter(email=email).first()
            if user is None:
                user = AppUser(agency_id=agency, email=email, display_name=name.strip())
                user.save(force_insert=True)
            elif user.status != "invited":
                raise Refused("this user has already enrolled")
            return _token(user)
    except IntegrityError as error:  # the email belongs to a user this agency cannot see
        raise Refused("this email cannot be invited") from error


def redeem(token: str, password: str) -> Verified | None:
    """Sets the password if the link is genuine, unexpired and unused, the user is still
    `invited` and the password has at least `SKIW_PW_MIN_LENGTH` characters (code points after
    NFKC, the form that is hashed; no composition rules); None otherwise, whatever the reason. A
    refusal writes nothing, so a short password leaves the link working. The row lock makes two
    uses of one link take turns, so the second sees the changed blob."""
    try:
        value = signing.TimestampSigner(salt=SALT).unsign_object(
            token, max_age=timedelta(minutes=settings.SKIW_ENROL_LINK_MIN)
        )
        user_id, agency_id, mark = uuid.UUID(value["u"]), uuid.UUID(value["a"]), value["f"]
    except (signing.BadSignature, TypeError, KeyError, ValueError):
        return None
    if len(passwords.normalise(password)) < settings.SKIW_PW_MIN_LENGTH:
        return None
    with with_agency(agency_id):
        user = AppUser.objects.select_for_update().filter(id=user_id, status="invited").first()
        if user is None or fingerprint(user.login_blob_ct) != mark:
            return None
        record = blob.LoginRecord(user.id, agency_id, passwords.hash_password(password))
        user.login_blob_ct = blob.seal_login(record, user.email)
        user.save(update_fields=["login_blob_ct"])
    return Verified(user_id, agency_id)
