# Fixture for `semgrep --test semgrep/` (rules files-volume-only-storage, documents-storage-no-db).
import os
import shutil
from pathlib import Path

# ruleid: documents-storage-no-db
import django.db.transaction

# ruleid: documents-storage-no-db
from django import db

# ok: documents-storage-no-db
from django.conf import settings

# ruleid: documents-storage-no-db
from django.db import connection

# ruleid: documents-storage-no-db
from django.db.models import Q

from documents import storage


def banned(agency_id, upload):
    # ruleid: files-volume-only-storage
    root = Path(settings.FILES_ROOT)
    # ruleid: files-volume-only-storage
    with open(os.path.join(getattr(settings, "FILES_ROOT", ""), "clean", agency_id), "rb"):
        pass
    # ruleid: files-volume-only-storage
    shutil.copy(upload, os.environ["SKIW_FILES_ROOT"])
    # ruleid: files-volume-only-storage
    Path("/srv/files/quarantine").unlink()
    # ruleid: files-volume-only-storage
    os.listdir("/srv/files")
    return root, connection, db, Q, django.db.transaction


def allowed(agency_id, upload, max_bytes):
    # ok: files-volume-only-storage
    stored = storage.write_quarantine(agency_id, upload, max_bytes)
    # ok: files-volume-only-storage
    Path("/srv/filesystem-notes.txt").read_text()
    return stored
