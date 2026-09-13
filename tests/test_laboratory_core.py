import json

import pytest

from autoquant.config import ROOT
from laboratory.artifacts import ArtifactError, publish_manifest, verify_manifest
from laboratory.domain.models import Experiment, ExperimentStatus, StrategyVersion
from laboratory.domain.state_machine import InvalidTransition, transition
from laboratory.protocol import canonical_json, protocol_id
from laboratory.storage import LineageStore


def test_protocol_canonical_and_state_machine():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert protocol_id({"a": 1}) == protocol_id({"a": 1})
    experiment = Experiment("e1", None, "v1", "d1", "p1")
    running = transition(experiment, ExperimentStatus.RUNNING)
    assert running.status == ExperimentStatus.RUNNING
    finished = transition(running, ExperimentStatus.SUCCESS, score=1.0)
    assert finished.score == 1.0
    with pytest.raises(InvalidTransition):
        transition(finished, ExperimentStatus.RUNNING)


def test_artifact_manifest_detects_mutation(tmp_path):
    payload = tmp_path / "summary.json"
    payload.write_text('{"score": 1}')
    publish_manifest(tmp_path, {"kind": "test"})
    verify_manifest(tmp_path)
    payload.write_text('{"score": 2}')
    with pytest.raises(ArtifactError, match="checksum"):
        verify_manifest(tmp_path)


def test_lineage_store_round_trip(tmp_path):
    store = LineageStore(tmp_path / "lineage.db")
    version = StrategyVersion("v1", "s1", "abc", "/tmp/train.py")
    store.save_strategy_version(version)
    experiment = Experiment("e1", "t1", "v1", "d1", "p1", ExperimentStatus.SUCCESS, score=1.2)
    store.save_experiment(experiment)
    store.record_decision("e1", "keep", {"reason": "test"})
    assert store.get_experiment("e1")["score"] == 1.2
    assert store.list_experiments("t1")[0]["experiment_id"] == "e1"
