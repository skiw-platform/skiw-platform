# The `backup` service image for the pre-migration dump (spec §8.4 H3 step 4, H6; plan §3 M1g).
# Pinned inputs only (UNI-14), every base by digest, all on Alpine 3.24 (DECISIONS 2026-10-23,
# "Dump image passes the Trivy gate"): pg_dump/pg_restore 17.11 from the postgres alpine image (gosu
# removed), the Python interpreter and standard library from the python alpine image (musl and the
# same libssl3/libcrypto3 as the postgres base; pip removed), and age v1.3.2 built from its source
# archive, checked by SHA-256, with the pinned Go. CI scans it on every PR and publishes it by digest
# (M1h); hosts name that digest in SKIW_BACKUP_IMAGE. Never built on a host.
FROM golang:1.27.3-alpine3.24@sha256:b8c9b82affbbb82a020bbcf998dad2ba9516944ac7e883524642a481a9505e9c AS age
ADD --checksum=sha256:b07c28c6c4bdafa272073a310b75bc22c49da8904585a89c30e5ca4233e63843 \
    https://github.com/FiloSottile/age/archive/refs/tags/v1.3.2.tar.gz /src/age.tar.gz
# Modules come from the default proxy and are checked against the archive's go.sum (and GOSUMDB).
ENV CGO_ENABLED=0 GOFLAGS=-mod=readonly GOTOOLCHAIN=local
RUN tar -xzf /src/age.tar.gz -C /src \
    && cd /src/age-1.3.2 \
    && go build -trimpath -ldflags "-X main.Version=v1.3.2" -o /out/age ./cmd/age

FROM python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d AS python
RUN mkdir -p /out/usr/local/bin /out/usr/local/lib \
    && cp -a /usr/local/bin/python3 /usr/local/bin/python3.12 /out/usr/local/bin/ \
    && cp -a /usr/local/lib/libpython3.12.so.1.0 /usr/local/lib/python3.12 /out/usr/local/lib/ \
    && rm -rf /out/usr/local/lib/python3.12/site-packages/pip* \
        /out/usr/local/lib/python3.12/ensurepip

FROM postgres:17.11-alpine3.24@sha256:eee6c6e1b0894fa4fe0075eb054af9fd1cf39a35321c2d4110626cfe506411fb
# REMOVE-WHEN-UPSTREAM-REBUILDS (DECISIONS 2026-11-11, "base images krb5-libs"): the postgres base
# ships krb5-libs 1.22.2-r1 and libxslt 1.1.43-r3, both with fixed HIGH CVEs, and Docker Hub has no
# rebuild yet. These are the only apk packages allowed here (test_predeploy.py); `>=` is deliberate.
RUN apk add --no-cache "krb5-libs>=1.22.3-r0" "libxslt>=1.1.43-r4"
COPY --from=python /out/ /
COPY --from=age /out/age /usr/local/bin/age
RUN rm /usr/local/bin/gosu \
    && python3 -I -c "import hashlib, ssl, subprocess, tempfile" \
    && test "$(pg_dump --version)" = "pg_dump (PostgreSQL) 17.11" \
    && test "$(pg_restore --version)" = "pg_restore (PostgreSQL) 17.11" \
    && test "$(age --version)" = "v1.3.2"
COPY predeploy.py /usr/local/lib/skiw/predeploy.py
USER 10003:10003
ENTRYPOINT ["python3", "-I", "/usr/local/lib/skiw/predeploy.py"]
