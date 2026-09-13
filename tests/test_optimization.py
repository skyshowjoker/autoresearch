import json
import sys
import time
from pathlib import Path

import pytest

from autoquant.config import ROOT
from autoquant.experiment import run_experiments
from autoquant.prepare import prepare
from laboratory.agents.optimization import OptimizationPlan
from laboratory.budget import ExperimentBudget
from laboratory.compare import compare_summaries


def test_optimization_plan_contract():
    plan = OptimizationPlan.from_dict({
        "action_type": "risk", "hypothesis": "less risk", "expected_effect": "lower drawdown",
        "failure_condition": "score falls", "changed_components": ["allocation"],
    })
    assert plan.action_type == "risk"
    with pytest.raises(ValueError, match="action"):
        OptimizationPlan.from_dict({"action_type": "random", "hypothesis": "x", "expected_effect": "y", "failure_condition": "z", "changed_components": ["x"]})


def test_budget_stops_on_no_improvement():
    budget = ExperimentBudget(max_trials=10, max_runtime_seconds=100, max_no_improvement=2, max_consecutive_failures=3)
    started_at = time.monotonic()
    assert budget.can_continue(started_at=started_at, completed=1, no_improvement=1, consecutive_failures=0)[0]
    assert budget.can_continue(started_at=started_at, completed=1, no_improvement=2, consecutive_failures=0) == (False, "max_no_improvement")
    assert budget.can_continue(started_at=started_at, completed=10, no_improvement=0, consecutive_failures=0) == (False, "max_trials")


def test_compare_reports_deltas(tmp_path):
    for name, score in (("parent", 1.0), ("candidate", 1.5)):
        path = tmp_path / name
        path.mkdir()
        (path / "folds.json").write_text(json.dumps([{"fold": "f1", "cost_multiplier": 1, "metrics": {"score": score, "sharpe": score, "max_drawdown": 0.2}}]))
    result = compare_summaries({"score": 1, "artifact_dir": str(tmp_path / "parent")}, {"score": 1.5, "artifact_dir": str(tmp_path / "candidate")})
    assert result["delta"]["score"] == 0.5
    assert result["fold_delta"][0]["sharpe_delta"] == 0.5


def test_optimize_brief_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOQUANT_CACHE_DIR", str(tmp_path / "cache"))
    prepare()
    session = tmp_path / "session"
    provider = ROOT / "examples" / "local_generator.py"
    command = f"{sys.executable} {provider} --candidate {{candidate}} --brief {{brief}}"
    state = run_experiments(session, 1, ROOT / "train.py", generator=command,
                            brief=json.loads((ROOT / "examples" / "research_brief.json").read_text()))
    event = state["events"][-1]
    assert event["decision"] == "discard"
    assert event["hypothesis"]["action_type"] == "parameter"
    assert "comparison" in event
    assert (session / "candidate-00001" / "agent_run.json").exists()
