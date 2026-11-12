"""`scripts/deploy-prod` (spec §8.4 H3 step 8, Q42; agents/PROJECT.md §11; plan §3 M1h).

Fake `gh` and `ssh` executables stand first and alone on PATH, so the real tools never run. They
follow the real tools' rules (gh 2.94, probed 2026-10-23 against this repository): `gh run view
--json` prints only the fields asked for; an unknown run, a `gh api` HTTP error (which still prints
the JSON error body on stdout) or no artifact of that name exit 1; the artifacts endpoint answers
`{"total_count": n, "artifacts": [...]}`; `gh run download -n` takes only the first of several
artifacts with one name, skips expired ones and unpacks into the -D directory; compare
`<base>...<head>` reports `ahead` when head has commits base lacks. Each fake can also hang (bound
tests) or print garbage. Every fake prints a marker that must never reach the wrapper's output.
"""

import importlib.machinery
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path
from types import ModuleType
from typing import Any  # the fakes' JSON scenarios (UNI-01)

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "deploy-prod"
DIGEST = "sha256:" + "ab" * 32
OTHER = "sha256:" + "cd" * 32
RUN = "39910194425"
HEAD = "c5647a4c04ee4e19dda59cc02fbdc0528ae5ad56"
HOST_KEY = "ssh-ed25519 " + "A" * 68  # shape only, not a key
MARKER = "FAKE-TOOL-OUTPUT-MARKER"

FAKE = """#!{python}
import json, os, sys, time
from pathlib import Path

tool, args = Path(sys.argv[0]).name, sys.argv[1:]
s = json.loads(Path(os.environ["FAKE_SCENARIO"]).read_text())
with open(os.environ["FAKE_LOG"], "a") as log:
    env = {{k: os.environ.get(k) for k in ("GH_HOST", "GH_PROMPT_DISABLED", "GH_REPO")}}
    log.write(json.dumps({{"tool": tool, "args": args, "env": env}}) + "\\n")
if tool == "gh":
    print("{marker}", file=sys.stderr)  # gh's stderr is captured, never shown

def out(text, code=0):
    sys.stdout.write(text)
    sys.exit(code)

def hang(what):
    if s.get("hang") == what:
        time.sleep(30)

if tool == "ssh":
    hang("ssh")
    print("skiw-deploy: deploy result line", file=sys.stderr)
    sys.exit(s.get("ssh_exit", 0))
repo_ok = "--repo" in args and args[args.index("--repo") + 1] == "skiw-dev1/skiw-platform"
if args[:2] == ["run", "view"]:
    hang("view")
    if "view_raw" in s:
        out(s["view_raw"])
    run = s["runs"].get(args[2])
    if run is None or not repo_ok:
        print("failed to get run: HTTP 404: Not Found", file=sys.stderr)
        sys.exit(1)
    fields = args[args.index("--json") + 1].split(",")
    out(json.dumps({{f: run[f] for f in fields if f in run}}) + "\\n")
if args[:1] == ["api"]:
    path = args[-1]
    if "/compare/" in path:
        hang("compare")
        body = s.get("compare")
    else:
        hang("artifacts")
        items = s.get("artifacts", [])
        body = {{"total_count": len(items), "artifacts": [a["meta"] for a in items]}}
        body = s.get("artifacts_body", body)
    if "api_raw" in s:
        out(s["api_raw"])
    if body is None:
        out(json.dumps({{"message": "Not Found", "status": "404"}}), 1)
    out(json.dumps(body))
if args[:2] == ["run", "download"]:
    hang("download")
    name, dest = args[args.index("-n") + 1], Path(args[args.index("-D") + 1])
    for a in s.get("artifacts", []):
        if a["meta"]["name"] == name and not a["meta"]["expired"] and repo_ok:
            for rel, content in a["files"].items():
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                (dest / rel).write_text(content)
            sys.exit(0)  # only the first artifact of that name
    print("no valid artifacts found to download", file=sys.stderr)
    sys.exit(1)
print("unknown command", file=sys.stderr)
sys.exit(1)
"""


def load() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("deploy_prod", str(SCRIPT))
    spec = importlib.util.spec_from_loader("deploy_prod", loader)
    assert spec
    module = importlib.util.module_from_spec(spec)
    before, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ in scripts/
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


deploy_prod = load()


def artifact(content: str = DIGEST, name: str = "image-digest", **meta: Any) -> dict[str, Any]:
    info = {"name": name, "expired": False, "workflow_run": {"id": int(RUN), "head_sha": HEAD}}
    return {"meta": info | meta, "files": {"digest.txt": content}}


def scenario() -> dict[str, Any]:
    run = {"conclusion": "success", "event": "push", "headBranch": "main", "headSha": HEAD}
    run |= {"workflowName": "ci", "status": "completed"}
    compare = {"status": "ahead", "ahead_by": 3, "behind_by": 0, "base_commit": {"sha": HEAD}}
    return {"runs": {RUN: run}, "compare": compare, "artifacts": [artifact()]}


class Fakes:
    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.bin, self.log, self.file = root / "bin", root / "calls.jsonl", root / "scenario.json"
        self.bin.mkdir()
        for tool in ("gh", "ssh"):
            path = self.bin / tool
            path.write_text(FAKE.format(python=sys.executable, marker=MARKER))
            path.chmod(0o755)
        self.key = root / "id_prod"
        self.key.write_text("not a key\n")
        self.key.chmod(0o600)
        self.config = root / "deploy-prod.env"
        self.write_config()
        self.scenario = scenario()
        monkeypatch.setenv("PATH", str(self.bin))
        monkeypatch.setenv("FAKE_LOG", str(self.log))
        monkeypatch.setenv("FAKE_SCENARIO", str(self.file))
        monkeypatch.setenv("GH_REPO", "someone/else")
        monkeypatch.setattr(deploy_prod, "GH_S", 5)
        monkeypatch.setattr(deploy_prod, "DOWNLOAD_S", 5)
        monkeypatch.setattr(deploy_prod, "DEPLOY_S", 5)

    def write_config(self, **change: str) -> None:
        values = {"SKIW_PROD_SSH": "prod.skiw.test:2222", "SKIW_PROD_HOST_KEY": HOST_KEY}
        values |= {"SKIW_PROD_DEPLOY_KEY": str(self.key)} | change
        lines = "".join(f"{k}={v}\n" for k, v in values.items())
        self.config.write_text(f"# owner config\n\n{lines}")
        self.config.chmod(0o600)

    def run(self, digest: str = DIGEST, run_id: str = RUN) -> int:
        self.file.write_text(json.dumps(self.scenario))
        code: int = deploy_prod.main([digest, run_id, "--config", str(self.config)])
        return code

    def calls(self, tool: str | None = None) -> list[dict[str, Any]]:
        if not self.log.exists():
            return []
        found = [json.loads(x) for x in self.log.read_text().splitlines()]
        return [c for c in found if tool is None or c["tool"] == tool]


@pytest.fixture
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fakes:
    return Fakes(tmp_path, monkeypatch)


def test_a_green_main_run_with_the_matching_artifact_deploys(
    fakes: Fakes, capfd: pytest.CaptureFixture[str]
) -> None:
    assert fakes.run() == 0
    gh = fakes.calls("gh")
    steps = [["run", "view"], ["api", "--hostname"], ["api", "--hostname"], ["run", "download"]]
    assert [c["args"][:2] for c in gh] == steps
    assert gh[1]["args"][-1] == f"repos/skiw-dev1/skiw-platform/compare/{HEAD}...main"
    pinned = {"GH_HOST": "github.com", "GH_PROMPT_DISABLED": "1", "GH_REPO": None}
    assert all(c["env"] == pinned for c in gh)
    (ssh,) = fakes.calls("ssh")
    args = ssh["args"]
    assert args[:6] == ["-F", "/dev/null", "-i", str(fakes.key), "-p", "2222"]
    assert args[-4:] == ["skiw-deploy@prod.skiw.test", "deploy", DIGEST, RUN]
    options = [args[i + 1] for i, a in enumerate(args) if a == "-o"]
    assert {"StrictHostKeyChecking=yes", "GlobalKnownHostsFile=/dev/null"} <= set(options)
    assert {"IdentitiesOnly=yes", "HostKeyAlias=skiw-production"} <= set(options)
    assert not [o for o in options if o.startswith("BatchMode")]  # the passphrase prompt
    known = next(o for o in options if o.startswith("UserKnownHostsFile="))
    assert not Path(known.partition("=")[2]).exists()  # removed after the call
    out, err = capfd.readouterr()
    assert MARKER not in out + err  # ssh's stderr (the host's line) passes; gh's output never
    assert "deploy result line" in err and f"deployed {DIGEST}" in err


def test_a_trailing_newline_in_the_digest_file_is_accepted(fakes: Fakes) -> None:
    fakes.scenario["artifacts"] = [artifact(f"{DIGEST}\n")]
    assert fakes.run() == 0


def mutate(s: dict[str, Any], path: str, value: Any) -> None:
    *keys, last = path.split(".")
    node: Any = s
    for key in keys:
        node = node[int(key)] if isinstance(node, list) else node[key]
    if value is DROP:
        del node[last]
    else:
        node[last] = value


DROP = object()
REFUSED = {
    "failed run": ("runs.39910194425.conclusion", "failure"),
    "run in progress": ("runs.39910194425.conclusion", ""),
    "pull request run": ("runs.39910194425.event", "pull_request"),
    "dispatched run": ("runs.39910194425.event", "workflow_dispatch"),
    "branch run": ("runs.39910194425.headBranch", "feat/x"),
    "other workflow": ("runs.39910194425.workflowName", "release"),
    "short head sha": ("runs.39910194425.headSha", "c5647a4"),
    "missing field": ("runs.39910194425.workflowName", DROP),
    "unknown run": ("runs.39910194425", DROP),
    "sha not on main (behind)": ("compare.status", "behind"),
    "sha not on main (diverged)": ("compare.status", "diverged"),
    "compare says behind_by 1": ("compare.behind_by", 1),
    "compare behind_by is a bool": ("compare.behind_by", False),
    "compare without behind_by": ("compare.behind_by", DROP),
    "compare about another commit": ("compare.base_commit", {"sha": "f" * 40}),
    "compare 404": ("compare", None),
    "no artifact": ("artifacts", []),
    "duplicate artifact": ("artifacts", [artifact(), artifact()]),
    "duplicate, second mismatching": ("artifacts", [artifact(), artifact(OTHER)]),
    "expired artifact": ("artifacts", [artifact(expired=True)]),
    "artifact of another run": ("artifacts.0.meta.workflow_run.id", 1),
    "artifact of another name": ("artifacts.0.meta.name", "image-digest-2"),
    "artifact at another sha": ("artifacts.0.meta.workflow_run.head_sha", "f" * 40),
    "empty digest.txt": ("artifacts", [artifact("")]),
    "multi-line digest.txt": ("artifacts", [artifact(f"{DIGEST}\n{DIGEST}\n")]),
    "two newlines": ("artifacts", [artifact(f"{DIGEST}\n\n")]),
    "digest then a word": ("artifacts", [artifact(f"{DIGEST}\nx\n")]),
    "crlf": ("artifacts", [artifact(f"{DIGEST}\r\n")]),
    "leading space": ("artifacts", [artifact(f" {DIGEST}")]),
    "uppercase hex": ("artifacts", [artifact(DIGEST.upper().replace("SHA256", "sha256"))]),
    "mismatching digest": ("artifacts", [artifact(OTHER)]),
    "bare hex": ("artifacts", [artifact(DIGEST.removeprefix("sha256:"))]),
}


# The check that must refuse, where a later check would refuse too (each guard is tested alone).
REASONS = {
    "short head sha": "headSha is not a 40-hex commit",
    "expired artifact": "is expired or not that artifact",
    "two newlines": "is not exactly one sha256 digest",
    "crlf": "is not exactly one sha256 digest",
    "leading space": "is not exactly one sha256 digest",
    "digest then a word": "is not exactly one sha256 digest",
    "duplicate artifact": "exactly one `image-digest` artifact",
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_refused_before_ssh(fakes: Fakes, case: str, capfd: pytest.CaptureFixture[str]) -> None:
    mutate(fakes.scenario, *REFUSED[case])
    assert fakes.run() == 2
    assert fakes.calls("ssh") == []
    out, err = capfd.readouterr()
    assert MARKER not in out + err and "refused" in err
    assert REASONS.get(case, "") in err


@pytest.mark.parametrize(
    "body",
    [
        {"total_count": 2, "artifacts": [artifact()["meta"]]},  # a second page exists
        {"total_count": 1, "artifacts": [artifact()["meta"]] * 2},
        {"total_count": 1, "artifacts": {}},
    ],
)
def test_an_artifact_list_that_is_not_exactly_one_is_refused(
    fakes: Fakes, body: dict[str, Any], capfd: pytest.CaptureFixture[str]
) -> None:
    fakes.scenario["artifacts_body"] = body
    assert fakes.run() == 2
    assert fakes.calls("ssh") == []
    assert "exactly one `image-digest` artifact" in capfd.readouterr().err


@pytest.mark.parametrize(
    "files",
    [{"digest.txt": DIGEST, "other.txt": "x"}, {"sub/digest.txt": DIGEST}, {"other.txt": DIGEST}],
)
def test_an_artifact_with_other_files_is_refused(fakes: Fakes, files: dict[str, str]) -> None:
    fakes.scenario["artifacts"] = [artifact() | {"files": files}]
    assert fakes.run() == 2
    assert fakes.calls("ssh") == []


GARBAGE = ["", f"not json {MARKER}", f'{{"conclusion": "{MARKER}"', "[]", f'"{MARKER}"']


@pytest.mark.parametrize("raw", GARBAGE)
def test_garbage_from_gh_is_refused_and_never_shown(
    fakes: Fakes, raw: str, capfd: pytest.CaptureFixture[str]
) -> None:
    fakes.scenario["view_raw"] = raw
    assert fakes.run() == 2
    fakes.scenario.pop("view_raw")
    fakes.scenario["api_raw"] = raw
    assert fakes.run() == 2
    assert fakes.calls("ssh") == []
    out, err = capfd.readouterr()
    assert MARKER not in out + err


def test_extra_fields_from_run_view_are_refused(fakes: Fakes) -> None:
    run = fakes.scenario["runs"][RUN]
    fakes.scenario["view_raw"] = json.dumps(run | {"extra": 1})
    assert fakes.run() == 2


@pytest.mark.parametrize("step", ["view", "compare", "artifacts", "download"])
def test_a_hanging_gh_is_bounded_and_refused(
    fakes: Fakes, step: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deploy_prod, "GH_S", 1)
    monkeypatch.setattr(deploy_prod, "DOWNLOAD_S", 1)
    fakes.scenario["hang"] = step
    assert fakes.run() == 2
    assert fakes.calls("ssh") == []


@pytest.mark.parametrize(
    "args", [("sha256:abc", RUN), (DIGEST, "0"), (DIGEST, "12a"), (OTHER.upper(), RUN)]
)
def test_bad_arguments_are_refused_before_any_tool(fakes: Fakes, args: tuple[str, str]) -> None:
    assert fakes.run(*args) == 2
    assert fakes.calls() == []


@pytest.mark.parametrize(
    "change",
    [
        {"SKIW_PROD_SSH": "prod.skiw.test"},
        {"SKIW_PROD_SSH": "prod.skiw.test:99999"},
        {"SKIW_PROD_SSH": "-oProxyCommand=x:22"},
        {"SKIW_PROD_HOST_KEY": "ssh-rsa " + "A" * 68},
        {"SKIW_PROD_DEPLOY_KEY": "id_prod"},
        {"SKIW_PROD_DEPLOY_KEY": "/nonexistent/key"},
        {"SKIW_PROD_EXTRA": "1"},
    ],
)
def test_a_bad_config_is_refused_before_any_tool(fakes: Fakes, change: dict[str, str]) -> None:
    fakes.write_config(**change)
    assert fakes.run() == 2
    assert fakes.calls() == []


def test_config_and_key_permissions_are_checked(fakes: Fakes) -> None:
    fakes.config.chmod(0o620)
    assert fakes.run() == 2
    fakes.config.chmod(0o600)
    fakes.key.chmod(0o640)
    assert fakes.run() == 2
    fakes.key.chmod(0o600)
    fakes.config.write_text(fakes.config.read_text() + "SKIW_PROD_SSH=other.skiw.test:22\n")
    assert fakes.run() == 2
    missing = fakes.config.with_name("missing.env")
    assert deploy_prod.main([DIGEST, RUN, "--config", str(missing)]) == 2
    assert fakes.calls() == []


def test_gh_missing_from_path_is_refused(fakes: Fakes) -> None:
    (fakes.bin / "gh").unlink()
    assert fakes.run() == 2
    assert fakes.calls() == []


@pytest.mark.parametrize(("host", "ours"), [(1, 1), (2, 2), (3, 1), (255, 1)])
def test_the_host_exit_code_decides(fakes: Fakes, host: int, ours: int) -> None:
    fakes.scenario["ssh_exit"] = host
    assert fakes.run() == ours
    assert len(fakes.calls("ssh")) == 1


def test_a_hanging_ssh_is_bounded(fakes: Fakes, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deploy_prod, "DEPLOY_S", 1)
    fakes.scenario["hang"] = "ssh"
    assert fakes.run() == 1


def test_the_script_is_executable_and_stdlib_only() -> None:
    assert SCRIPT.stat().st_mode & stat.S_IXUSR
    assert SCRIPT.read_text().startswith("#!/usr/bin/env python3\n")
    imports = {
        line.split()[1].split(".")[0]
        for line in SCRIPT.read_text().splitlines()
        if line.startswith(("import ", "from "))
    }
    assert imports <= set(sys.stdlib_module_names)
    assert os.access(SCRIPT, os.X_OK)
