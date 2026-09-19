import json
import shutil
import threading
import urllib.request
import urllib.error
import pytest
from pathlib import Path
from uuid import uuid4

from autoquant.config import ROOT
from laboratory.console_server import serve_in_thread
from laboratory.domain.models import Experiment, ExperimentStatus, StrategyVersion
from laboratory.storage import LineageStore


def get_json(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        return response.status, json.loads(response.read())


def test_console_queries_and_final_approval(tmp_path):
    db_path = tmp_path / "console.db"
    artifact_dir = ROOT / ".cache" / f"console-test-{uuid4().hex}"
    artifact_dir.mkdir(parents=True)
    store = LineageStore(db_path)
    store.save_strategy_version(StrategyVersion("v1", "s1", "abc", "/tmp/train.py"))
    store.save_experiment(Experiment("e1", None, "v1", "d1", "p1", ExperimentStatus.SUCCESS, score=1.2, artifact_dir=str(artifact_dir)))
    server, thread = serve_in_thread(port=0, db_path=db_path)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, health = get_json(base + "/api/health")
        assert status == 200 and health["status"] == "ok"
        status, experiments = get_json(base + "/api/experiments")
        assert status == 200 and experiments["items"][0]["experiment_id"] == "e1"
        (artifact_dir / "summary.json").write_text('{"score": 1.2}', encoding="utf-8")
        status, artifacts = get_json(base + "/api/experiments/e1/artifacts")
        assert status == 200 and "summary.json" in artifacts["items"]
        status, preview = get_json(base + "/api/experiments/e1/artifacts/summary.json")
        assert status == 200 and preview["kind"] == "text" and preview["content"] == '{"score": 1.2}'
        request = urllib.request.Request(base + "/api/experiments/e1/approve-final", data=json.dumps({"actor": "tester"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=3)
        assert error.value.code == 409
        (artifact_dir / "request.json").write_text(json.dumps({"profile": "final"}))
        with urllib.request.urlopen(request, timeout=3) as response:
            assert response.status == 201
        assert store.list_approvals("e1")[0]["actor"] == "tester"
        task_request = urllib.request.Request(base + "/api/research/tasks", data=json.dumps({"title": "test", "prompt": "find robust trend", "mode": "generate"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(task_request, timeout=3) as response:
            assert response.status == 201
        status, tasks = get_json(base + "/api/research/tasks")
        assert status == 200 and tasks["items"][0]["title"] == "test"
    finally:
        server.shutdown()
        thread.join(timeout=3)
        shutil.rmtree(artifact_dir, ignore_errors=True)
