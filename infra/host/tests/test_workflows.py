"""The GitHub workflows (spec §8.4 H3 steps 2 and 8, T25, Q42; plan §3 M1h).

No YAML parser is a dependency, so this reads the workflow files with a small line parser for the
subset they use (block mappings, two-space indents, `jobs` last) and fails on anything else: tabs,
anchors or aliases, flow-style or `write-all` permissions, a key at an unexpected indent. Claims:
the only secret any workflow references is STAGING_DEPLOY_KEY, in deploy-staging; no workflow names
the production host, its env file or a production key; only `publish` can write packages; every
action is pinned by a full commit SHA with a version comment; the digest artifact is uploaded only
in `publish`, as plan §3 M1h says; deploy-staging runs only after publish and only when the owner
has turned it on, and pins staging's host key from staging.env. (`scripts/` holding only
`deploy-prod` is test_layout.py.)
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*"))
CI = REPO / ".github" / "workflows" / "ci.yml"
ENV = REPO / "infra" / "host" / "env"
USES = re.compile(
    r"(?:- )?uses: ([A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@([0-9a-f]{40}) # v[0-9]+(?:\.[0-9]+){2}"
)
UPLOAD = "actions/upload-artifact"
Block = list[str]


def mapping(lines: Block, indent: int) -> dict[str, tuple[str, Block]]:
    """The keys at exactly `indent` spaces, each with its inline value and the deeper lines."""
    found: dict[str, tuple[str, Block]] = {}
    current = ""
    for line in lines:
        if not line.strip() or line.strip().startswith("#"):
            continue
        depth = len(line) - len(line.lstrip(" "))
        if depth < indent:
            raise AssertionError(f"line above the block's indent: {line!r}")
        if depth == indent:
            key, sep, value = line.strip().partition(":")
            assert sep and re.fullmatch(r"[A-Za-z0-9_-]+", key), f"not a key: {line!r}"
            assert key not in found, f"key {key} given twice"
            current = key
            found[key] = (value.split(" #")[0].strip(), [])
        else:
            assert current, f"a deeper line before any key: {line!r}"
            found[current][1].append(line)
    return found


def parse(
    path: Path,
) -> tuple[dict[str, tuple[str, Block]], dict[str, dict[str, tuple[str, Block]]]]:
    """Top-level keys and, per job, its keys. Fails on YAML this parser does not read."""
    text = path.read_text(encoding="utf-8")
    assert "\t" not in text and not re.search(r"(^|\s)[&*][A-Za-z]|<<:", text, re.M), path
    lines = text.splitlines()
    assert lines.count("jobs:") == 1, f"{path}: not one block `jobs:`"
    start = lines.index("jobs:")
    assert all(x.startswith(" ") or not x.strip() for x in lines[start + 1 :]), "jobs is not last"
    found = mapping(lines[start + 1 :], 2)
    assert all(value == "" for value, _ in found.values()), "a job that is not a block mapping"
    return mapping(lines[:start], 0), {name: mapping(body, 4) for name, (_, body) in found.items()}


def permissions(entry: tuple[str, Block] | None) -> dict[str, str]:
    if entry is None:
        return {}
    value, body = entry
    assert value == "", f"permissions must be a block mapping, not {value!r}"
    return {k: v for k, (v, rest) in mapping(body, min_indent(body)).items() if not rest}


def min_indent(body: Block) -> int:
    return min(len(x) - len(x.lstrip(" ")) for x in body if x.strip())


def expressions(text: str) -> list[str]:
    """Every `${{ }}` expression and every `if:` condition (which may omit the braces)."""
    found = re.findall(r"\$\{\{(.*?)\}\}", text, re.S)
    return found + re.findall(r"^\s*(?:- )?if:(.*)$", text, re.M)


def job_text(job: dict[str, tuple[str, Block]]) -> str:
    return "\n".join(f"{v}\n" + "\n".join(b) for v, b in job.values())


def steps(job: dict[str, tuple[str, Block]]) -> list[dict[str, tuple[str, Block]]]:
    """Each `      - key: ...` step as a mapping at indent 8."""
    out: list[Block] = []
    for line in job["steps"][1]:
        if line.startswith("      - "):
            out.append([f"        {line[8:]}"])
        elif out:
            out[-1].append(line)
        else:
            assert not line.strip() or line.strip().startswith("#"), f"not a step: {line!r}"
    return [mapping(step, 8) for step in out]


@pytest.fixture(scope="module")
def ci() -> dict[str, dict[str, tuple[str, Block]]]:
    return parse(CI)[1]


def test_only_known_workflow_files() -> None:
    assert [p.name for p in WORKFLOWS] == ["ci.yml"]


def test_the_parser_refuses_what_it_does_not_read(tmp_path: Path) -> None:
    for bad in (
        "on: push\njobs:\n  a:\n    permissions: write-all\n    runs-on: x\n",
        "on: push\njobs:\n  a: &x\n    runs-on: x\n",
        "on: push\njobs:\n\ta:\n",
        "on: push\njobs:\n  a:\n   runs-on: x\n",
        "jobs:\n  a:\n    runs-on: x\npermissions: write-all\n",
    ):
        path = tmp_path / "w.yml"
        path.write_text(bad)
        with pytest.raises(AssertionError):
            _, jobs = parse(path)
            for job in jobs.values():
                permissions(job.get("permissions"))


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_the_only_secret_is_the_staging_deploy_key(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for expression in expressions(text):
        for found in re.finditer(r"\bsecrets\b(.{0,40})", expression):
            assert re.match(r"\.STAGING_DEPLOY_KEY\b", found[1]), expression
    _, jobs = parse(path)
    readers = [n for n, job in jobs.items() if "secrets" in "".join(expressions(job_text(job)))]
    assert readers in ([], ["deploy-staging"])
    assert text.count("secrets.STAGING_DEPLOY_KEY") <= 1
    assert "GITHUB_TOKEN" not in text  # the job token is `github.token`, in publish only
    users = [n for n, job in jobs.items() if "github.token" in job_text(job)]
    assert users in ([], ["publish"])


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_workflow_names_production(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    code = [x for x in text.splitlines() if not x.strip().startswith("#")]
    assert not [x for x in code if re.search(r"prod", x, re.I)]
    values = dict(
        line.partition("=")[::2]
        for line in (ENV / "production.env").read_text().splitlines()
        if line and not line.startswith("#")
    )
    for key in ("SKIW_HOSTNAME", "SKIW_DEPLOY_KEY_FINGERPRINT"):
        assert not values[key] or values[key] not in text


def test_permissions(ci: dict[str, dict[str, tuple[str, Block]]]) -> None:
    top, _ = parse(CI)
    assert permissions(top.get("permissions")) == {"contents": "read"}
    found = {name: permissions(job.get("permissions")) for name, job in ci.items()}
    assert found.pop("publish") == {"contents": "read", "packages": "write"}
    assert found.pop("deploy-staging") == {"contents": "read"}
    assert all(v == {} for v in found.values()), "another job sets its own permissions"
    assert "write-all" not in CI.read_text() and "id-token" not in CI.read_text()


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_by_commit_sha(path: Path) -> None:
    uses = [x.strip() for x in path.read_text().splitlines() if re.match(r"\s*(- )?uses:", x)]
    assert uses
    assert [x for x in uses if not USES.fullmatch(x)] == []


def test_digest_artifacts_are_uploaded_only_in_publish(
    ci: dict[str, dict[str, tuple[str, Block]]],
) -> None:
    uploads = {
        n: [s for s in steps(j) if UPLOAD in s.get("uses", ("", []))[0]] for n, j in ci.items()
    }
    assert {n for n, s in uploads.items() if s} == {"publish"}
    assert CI.read_text().count(f"{UPLOAD}@") == 2
    named = {}
    for step in uploads["publish"]:
        assert re.fullmatch(rf"{UPLOAD}@[0-9a-f]{{40}}", step["uses"][0])
        options = {k: v for k, (v, _) in mapping(step["with"][1], 10).items()}
        assert "overwrite" not in options
        assert options["if-no-files-found"] == "error"
        assert options["retention-days"] == "30"
        assert options["path"].endswith("/digest.txt")
        named[options["name"]] = step.get("if", ("", []))[0]
    assert named == {
        "image-digest": "",  # always, and never conditional
        "predeploy-digest": "env.PUBLISH_PREDEPLOY == 'true'",
    }


def test_publish_runs_after_every_gate_on_a_push_to_main(
    ci: dict[str, dict[str, tuple[str, Block]]],
) -> None:
    publish = ci["publish"]
    assert publish["if"][0] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    gates = set(ci) - {"publish", "deploy-staging"}
    assert gates == {"checks", "security", "image", "host"}
    assert set(re.findall(r"[a-z-]+", publish["needs"][0])) == gates
    text = job_text(publish)
    assert text.count("aquasecurity/trivy-action@") == 2  # app image, and the dump image
    assert 'exit-code: "1"' in text and "severity: HIGH,CRITICAL" in text


def test_deploy_staging_is_gated_and_pins_the_staging_host_key(
    ci: dict[str, dict[str, tuple[str, Block]]],
) -> None:
    job = ci["deploy-staging"]
    assert job["needs"][0] == "publish"
    assert job["if"][0] == "vars.SKIW_STAGING_DEPLOY == 'enabled'"
    text = job_text(job)
    for option in ("StrictHostKeyChecking=yes", "BatchMode=yes", "GlobalKnownHostsFile=/dev/null"):
        assert option in text
    assert "-F /dev/null" in text and "IdentitiesOnly=yes" in text
    assert not re.search(r"StrictHostKeyChecking=(no|accept-new)|ssh-keyscan", text)
    assert re.findall(r"infra/host/env/[a-z]+\.env", text) == ["infra/host/env/staging.env"] * 2
    assert 'deploy "$DIGEST" "$GITHUB_RUN_ID"' in text


def test_staging_address_and_host_key_are_empty_or_valid_and_agree() -> None:
    def values(name: str) -> dict[str, str]:
        lines = (ENV / name).read_text().splitlines()
        return dict(x.partition("=")[::2] for x in lines if x and not x.startswith("#"))

    staging, production = values("staging.env"), values("production.env")
    address = r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}:[1-9][0-9]{0,4}"
    for key, shape in (
        ("SKIW_STAGING_SSH", address),
        ("SKIW_STAGING_HOST_KEY", r"ssh-ed25519 [A-Za-z0-9+/]{68}"),
    ):
        assert staging[key] == "" or re.fullmatch(shape, staging[key])
        assert not (staging[key] and production[key]) or staging[key] == production[key]
