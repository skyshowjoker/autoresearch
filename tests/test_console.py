import json
import threading
import urllib.request
import urllib.error
import pytest
from pathlib import Path

from laboratory.console_server import serve_in_thread
from laboratory.domain.models import Experiment, ExperimentStatus, StrategyVersion
from laboratory.storage import LineageStore


def get_json(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        return response.status, json.loads(response.read())


def test_console_queries_and_final_approval(tmp_path):
    db_path = tmp_path / "console.db"
    store = LineageStore(db_path)
    store.save_strategy_version(StrategyVersion("v1", "s1", "abc", "/tmp/train.py"))
    store.save_experiment(Experiment("e1", None, "v1", "d1", "p1", ExperimentStatus.SUCCESS, score=1.2, artifact_dir=str(tmp_path)))
    server, thread = serve_in_thread(port=0, db_path=db_path)
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, health = get_json(base + "/api/health")
        assert status == 200 and health["status"] == "ok"
        status, experiments = get_json(base + "/api/experiments")
        assert status == 200 and experiments["items"][0]["experiment_id"] == "e1"
        request = urllib.request.Request(base + "/api/experiments/e1/approve-final", data=json.dumps({"actor": "tester"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=3)
        assert error.value.code == 409
        (tmp_path / "request.json").write_text(json.dumps({"profile": "final"}))
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
