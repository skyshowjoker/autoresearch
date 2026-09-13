import json
import sys
from pathlib import Path

import pytest

from laboratory.agents.brief import BriefError, ResearchBrief
from laboratory.agents.gateway import AgentGateway
from laboratory.agents.policy import DiffPolicy, DiffViolation, inspect_candidate


def valid_brief(**changes):
    value = dict(objective="test objective", mode="generate", market="demo",
                 universe=["ORCL"], frequency="1d", validation_profile="dev")
    value.update(changes)
    return ResearchBrief.from_dict(value)


def test_brief_rejects_final_and_invalid_budget():
    with pytest.raises(BriefError, match="final"):
        valid_brief(validation_profile="final")
    with pytest.raises(BriefError, match="complexity"):
        valid_brief(complexity_budget={"max_lines_changed": 0})
    assert json.loads(valid_brief().prompt_context())["objective"] == "test objective"


def test_diff_policy_rejects_large_candidate(tmp_path):
    parent = tmp_path / "parent.py"
    candidate = tmp_path / "candidate.py"
    parent.write_text("def get_strategy_spec():\n    return {}\n")
    candidate.write_text("\n".join(["# changed"] * 20))
    with pytest.raises(DiffViolation, match="changes"):
        inspect_candidate(parent, candidate, DiffPolicy(max_lines_changed=2))


def test_gateway_requires_both_placeholders(tmp_path):
    gateway = AgentGateway()
    with pytest.raises(ValueError, match="placeholders"):
        gateway.run([sys.executable, "provider.py", "{candidate}"], brief=valid_brief(),
                    parent=tmp_path / "parent.py", candidate=tmp_path / "candidate.py", run_dir=tmp_path / "run")


def test_gateway_records_structured_run(tmp_path):
    provider = tmp_path / "provider.py"
    provider.write_text(
        "import pathlib, json, sys\n"
        "candidate = pathlib.Path(sys.argv[sys.argv.index('--candidate') + 1])\n"
        "candidate.write_text(candidate.read_text())\n"
    )
    candidate = tmp_path / "candidate.py"
    candidate.write_text("x = 1\n")
    result = AgentGateway().run(
        [sys.executable, str(provider), "--candidate", "{candidate}", "--brief", "{brief}"],
        brief=valid_brief(), parent=tmp_path / "parent.py", candidate=candidate, run_dir=tmp_path / "run")
    assert result.status == "success"
    assert (tmp_path / "run" / "brief.json").exists()
    assert (tmp_path / "run" / "agent.log").exists()
