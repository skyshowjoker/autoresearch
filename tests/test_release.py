import json

import pytest

from laboratory.artifacts import publish_manifest
from laboratory.paper import register_from_artifact
from laboratory.release import ReleaseError, export_release


def final_artifact(tmp_path):
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "strategy.py").write_text("x = 1\n")
    (artifact / "summary.json").write_text(json.dumps({"status": "success", "strategy_sha256": "abc", "dataset": "d1", "execution_model": "basic"}))
    (artifact / "request.json").write_text(json.dumps({"profile": "final", "dataset": "d1"}))
    (artifact / "provenance.json").write_text("{}")
    (artifact / "folds.json").write_text("[]")
    publish_manifest(artifact)
    return artifact


def test_paper_requires_final_success(tmp_path):
    artifact = final_artifact(tmp_path)
    registration = register_from_artifact("e1", artifact)
    assert registration.mode == "paper_pending_market_data"
    (artifact / "request.json").write_text(json.dumps({"profile": "dev"}))
    with pytest.raises(ValueError, match="final"):
        register_from_artifact("e1", artifact)


def test_release_requires_approval_and_is_auditable(tmp_path):
    artifact = final_artifact(tmp_path)
    with pytest.raises(ReleaseError, match="approval"):
        export_release("e1", artifact, [], tmp_path / "releases")
    release = export_release("e1", artifact, [{"action": "approve-final", "actor": "tester"}], tmp_path / "releases")
    assert (release / "release.json").exists()
    assert (release / "paper_registration.json").exists()
    with pytest.raises(ReleaseError, match="already"):
        export_release("e1", artifact, [{"action": "approve-final", "actor": "tester"}], tmp_path / "releases")
