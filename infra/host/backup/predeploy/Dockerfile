# The `backup` service image for the pre-migration dump (spec §8.4 H3 step 4, H6; plan §3 M1g).
# Pinned inputs only (UNI-14): pg_dump/pg_restore from the same postgres digest as `db`, the Python
# runtime from a pinned slim image of the same Debian release, and age v1.3.2 checked against the
# SHA-256 recorded in docs/DECISIONS.md (2026-10-14, M1d-1). CI publishes it by digest (M1h); hosts
# name that digest in SKIW_BACKUP_IMAGE. Never built on a host.
FROM python:3.12.15-slim-trixie@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2 AS python

FROM postgres:17.11@sha256:d74eeac9a635390a49bc21bd49fccd973de707e2a53a76ac49b552b8712ec46f
COPY --from=python /usr/local /usr/local
ADD --checksum=sha256:cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10 \
    https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz /tmp/age.tar.gz
RUN ldconfig \
    && tar -xzf /tmp/age.tar.gz -C /tmp \
    && install -m 0755 /tmp/age/age /usr/local/bin/age \
    && rm -rf /tmp/age /tmp/age.tar.gz \
    && python3 -c "import hashlib, subprocess" && age --version
COPY predeploy.py /usr/local/lib/skiw/predeploy.py
USER 10003:10003
ENTRYPOINT ["python3", "-I", "/usr/local/lib/skiw/predeploy.py"]
