import json
import os
import re
import subprocess
import sys
from pathlib import Path

INFRA = Path(__file__).resolve().parent.parent


def synth(outdir: Path) -> None:
    context = json.loads((INFRA / "cdk.json").read_text())["context"]
    env = {**os.environ, "CDK_OUTDIR": str(outdir), "CDK_CONTEXT_JSON": json.dumps(context)}
    subprocess.run([sys.executable, "app.py"], cwd=INFRA, env=env, check=True)


def test_synth_makes_an_empty_stack_in_the_malaysia_region(tmp_path: Path) -> None:
    synth(tmp_path)
    template = json.loads((tmp_path / "SkiwPlaceholder.template.json").read_text())
    assert "Resources" not in template
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    environment = manifest["artifacts"]["SkiwPlaceholder"]["environment"]
    assert environment == "aws://unknown-account/ap-southeast-5"


def test_synth_output_names_no_account(tmp_path: Path) -> None:
    synth(tmp_path)
    for path in tmp_path.rglob("*.json"):
        assert not re.search(r"\b\d{12}\b", path.read_text()), path.name
