from __future__ import annotations

import fcntl
import json
import os
import shlex
import signal
import subprocess
import time
from pathlib import Path

from .config import ROOT, load_config
from .data import DatasetSnapshot
from .evaluate import evaluate, protocol_identity, record_lineage, write_json
from .prepare import digest
from .scoring import should_promote
from laboratory.agents.brief import ResearchBrief
from laboratory.agents.gateway import AgentGateway
from laboratory.agents.policy import DiffPolicy, inspect_candidate
from laboratory.agents.optimization import OptimizationPlan
from laboratory.budget import ExperimentBudget
from laboratory.compare import compare_summaries
from laboratory.git_cycle import SessionGitCycle
from laboratory.research_themes import get_theme
from laboratory.significance import paired_fold_significance
from laboratory.storage import LineageStore


def run_experiments(session, iterations, strategy, generator=None, candidates=None, dataset=None, brief=None, task_id=None, theme=None):
    if iterations < 1:
        raise ValueError("iterations must be positive")
    session = Path(session).resolve()
    session.mkdir(parents=True, exist_ok=True)
    with (session / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(session, iterations, strategy, generator, candidates, dataset, brief, task_id, theme)


def _run(session, iterations, strategy, generator, candidates, dataset, brief=None, task_id=None, theme=None):
    config = load_config()
    lineage = LineageStore(ROOT / ".cache" / "laboratory.db") if task_id else None
    if lineage:
        lineage.update_task_status(task_id, "running")
    budget = ExperimentBudget(**config.get("budget", {})).validate()
    dataset = dataset or config["dataset"]
    if brief is not None and not isinstance(brief, ResearchBrief):
        brief = ResearchBrief.from_dict(brief)
    research_theme = get_theme(theme) if theme else None
    protocol, _ = protocol_identity(DatasetSnapshot.open(dataset), config)
    state_path = session / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state["protocol_id"] != protocol:
            raise ValueError("protocol changed; start a new session")
        champion = Path(state["best"]["artifact_dir"]) / "strategy.py"
        if digest(champion) != state["best"].get("strategy_sha256", digest(champion)):
            raise ValueError("champion artifact modified; cannot safely resume")
        (session / "champion.py").write_bytes(champion.read_bytes())
    else:
        baseline = evaluate(strategy, dataset, task_id=task_id)
        state = dict(protocol_id=protocol, best=baseline, completed=0, events=[])
        champion = Path(baseline["artifact_dir"]) / "strategy.py"
        (session / "champion.py").write_bytes(champion.read_bytes())
        write_json(state_path, state)
    git_cycle = SessionGitCycle(session, Path(state["best"]["artifact_dir"]) / "strategy.py")
    session_started = time.monotonic()
    no_improvement = int(state.get("no_improvement", 0))
    consecutive_failures = int(state.get("consecutive_failures", 0))
    for _ in range(iterations):
        allowed, stop_reason = budget.can_continue(started_at=session_started, completed=state["completed"],
                                                   no_improvement=no_improvement, consecutive_failures=consecutive_failures)
        if not allowed:
            state["stop_reason"] = stop_reason
            write_json(state_path, state)
            break
        number = state["completed"] + 1
        candidate_dir = session / f"candidate-{number:05d}"
        candidate_dir.mkdir(exist_ok=True)
        candidate = candidate_dir / "train.py"
        candidate.write_bytes((session / "champion.py").read_bytes())
        best = state["best"]
        context = dict(iteration=number, best=state["best"], recent=state["events"][-10:],
                       instruction="Edit only candidate train.py; provide hypothesis.json. Never use final holdout.")
        if research_theme:
            context["research_theme"] = research_theme.__dict__
        write_json(candidate_dir / "context.json", context)
        started = time.monotonic()
        try:
            if generator and brief is not None:
                agent_result = AgentGateway(config["validation"]["timeout_seconds"]).run(
                    generator, brief=brief, parent=session / "champion.py", candidate=candidate, run_dir=candidate_dir)
                write_json(candidate_dir / "agent_run.json", agent_result.__dict__)
                if agent_result.status != "success":
                    raise RuntimeError(agent_result.error or "agent provider failed")
                hypothesis = candidate_dir / "hypothesis.json"
                if not hypothesis.exists() or not isinstance(json.loads(hypothesis.read_text()).get("hypothesis"), str):
                    raise ValueError("gateway provider must write hypothesis.json with a hypothesis string")
            elif generator:
                command = [token.replace("{candidate}", str(candidate)).replace("{context}", str(candidate_dir / "context.json"))
                           for token in shlex.split(generator)]
                with (candidate_dir / "generator.log").open("w") as log:
                    process = subprocess.Popen(command, cwd=candidate_dir, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    try:
                        result = process.wait(timeout=config["validation"]["timeout_seconds"])
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise TimeoutError("generator timeout")
                    except BaseException:
                        if process.poll() is None:
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise
                if result:
                    raise RuntimeError(f"generator failed with exit {result}")
                hypothesis = candidate_dir / "hypothesis.json"
                if not hypothesis.exists() or not isinstance(json.loads(hypothesis.read_text()).get("hypothesis"), str):
                    raise ValueError("generator must write hypothesis.json with a hypothesis string")
            elif candidates:
                paths = sorted(Path(candidates).resolve().glob("*.py"))
                if number > len(paths):
                    raise ValueError("candidate queue exhausted")
                candidate.write_bytes(paths[number - 1].read_bytes())
            else:
                raise ValueError("provide --generator or --candidates for autonomous experiments")
            current_protocol, _ = protocol_identity(DatasetSnapshot.open(dataset), load_config())
            if current_protocol != protocol:
                raise ValueError("generator changed fixed protocol")
            policy = DiffPolicy(**{key: value for key, value in (brief.complexity_budget if brief else {}).items()
                                   if key in {"max_lines_changed", "max_functions_changed", "max_file_bytes"}})
            diff_report = inspect_candidate(session / "champion.py", candidate, policy)
            write_json(candidate_dir / "diff.json", diff_report)
            summary = evaluate(candidate, dataset, task_id=task_id,
                               parent_experiment_id=Path(best.get("artifact_dir", "")).name or None)
            if summary["protocol_id"] != protocol:
                raise ValueError("evaluation protocol mismatch")
            significance = paired_fold_significance(
                best.get("artifact_dir"), summary.get("artifact_dir"),
                alpha=config["scoring"].get("significance_alpha", 0.2),
                min_positive_fraction=config["scoring"].get("min_positive_fold_fraction", 0.5))
            keep = should_promote(summary, best, config["scoring"], significance)
            decision = "keep" if keep else "discard" if summary["status"] == "success" else summary["status"]
            if keep:
                state["best"] = summary
            hypothesis_path = candidate_dir / "hypothesis.json"
            hypothesis = json.loads(hypothesis_path.read_text()) if hypothesis_path.exists() else {"hypothesis": "prebuilt candidate queue"}
            if brief and brief.mode == "optimize":
                plan = OptimizationPlan.from_dict(hypothesis)
                hypothesis = plan.__dict__
            event = dict(iteration=number, decision=decision, result=summary, hypothesis=hypothesis,
                         diff=diff_report, significance=significance)
            event["comparison"] = compare_summaries(best, summary)
            record_lineage(Path(summary["artifact_dir"]).name, candidate, summary, decision,
                           Path(best.get("artifact_dir", "")).name or None, task_id)
        except Exception as exc:
            event = dict(iteration=number, decision="crash", reason=str(exc))
        event["git"] = git_cycle.record(candidate, event["decision"], number,
                                         {"theme": research_theme.name if research_theme else None})
        if event["decision"] == "keep":
            no_improvement = 0
            consecutive_failures = 0
        elif event["decision"] == "discard":
            no_improvement += 1
            consecutive_failures = 0
        else:
            consecutive_failures += 1
        event["runtime_seconds"] = time.monotonic() - started
        state["events"].append(event)
        state["completed"] = number
        state["no_improvement"] = no_improvement
        state["consecutive_failures"] = consecutive_failures
        write_json(candidate_dir / "decision.json", event)
        write_json(state_path, state)
        champion = Path(state["best"]["artifact_dir"]) / "strategy.py"
        (session / "champion.py").write_bytes(champion.read_bytes())
        print(json.dumps(event, ensure_ascii=False), flush=True)
        current_protocol, _ = protocol_identity(DatasetSnapshot.open(dataset), load_config())
        if current_protocol != protocol:
            raise ValueError("fixed protocol changed; session stopped")
    if lineage:
        lineage.update_task_status(task_id, "completed")
    return state
