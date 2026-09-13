import json
from pathlib import Path

import pytest

from autoquant.config import ROOT
from autoquant.evaluate import evaluate
from autoquant.experiment import run_experiments
from autoquant.prepare import prepare


def test_subprocess_evaluation_and_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOQUANT_CACHE_DIR", str(tmp_path / "cache"))
    prepare()
    queue = tmp_path / "queue"
    queue.mkdir()
    source = (ROOT / "train.py").read_bytes()
    (queue / "01_same.py").write_bytes(source)
    (queue / "02_crash.py").write_text("raise RuntimeError('intentional candidate failure')")
    session = tmp_path / "session"
    state = run_experiments(session, 1, ROOT / "train.py", candidates=queue)
    assert state["completed"] == 1
    assert state["events"][-1]["decision"] == "discard"
    assert state["best"]["status"] == "success"
    state = run_experiments(session, 1, ROOT / "train.py", candidates=queue)
    assert state["completed"] == 2
    assert state["events"][-1]["decision"] == "crash"
    assert (session / "champion.py").read_bytes() == source
    assert (ROOT / "train.py").read_bytes() == source
    request = json.loads((Path(state["best"]["artifact_dir"]) / "request.json").read_text())
    assert request["profile"] == "dev"


def test_generator_command(tmp_path, monkeypatch):
    import sys

    monkeypatch.setenv("AUTOQUANT_CACHE_DIR", str(tmp_path / "cache"))
    prepare()
    provider = tmp_path / "provider.py"
    provider.write_text("import pathlib\npathlib.Path('hypothesis.json').write_text('{\"hypothesis\":\"unchanged control\"}')\n")
    state = run_experiments(tmp_path / "session", 1, ROOT / "train.py", generator=f"{sys.executable} {provider}")
    assert state["events"][-1]["decision"] == "discard"


def test_worker_timeout_is_failure(tmp_path, monkeypatch):
    import autoquant.evaluate as evaluator
    from autoquant.config import load_config

    monkeypatch.setenv("AUTOQUANT_CACHE_DIR", str(tmp_path / "cache"))
    prepare()
    config = load_config()
    config["validation"]["timeout_seconds"] = 0.001
    monkeypatch.setattr(evaluator, "load_config", lambda: config)
    summary = evaluator.evaluate(ROOT / "train.py", output_root=tmp_path / "runs")
    assert summary["status"] == "timeout"
    assert summary["score"] is None
    assert (Path(summary["artifact_dir"]) / "error.json").exists()
