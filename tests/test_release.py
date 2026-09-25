import json

import pytest

from laboratory.artifacts import publish_manifest
from laboratory.paper import register_from_artifact
from laboratory.backquant import register_champion, list_registered
from laboratory.paper_trading import PaperTradingError, PaperTradingLedger
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


def test_backquant_registration_is_sqlite_auditable(tmp_path):
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    strategy = artifact / "strategy.py"
    strategy.write_text("class Strategy: pass\n")
    database = tmp_path / "backquant.db"
    record = register_champion(experiment_id="e1", strategy_path=strategy, artifact_dir=artifact, db_path=database)
    assert record["source_sha256"]
    assert list_registered(database)[0]["experiment_id"] == "e1"


def test_paper_ledger_replay_is_chronological(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "paper.db")
    result = ledger.replay([{"date": "2026-01-01", "close": 10}, {"date": "2026-01-02", "close": 11}],
                           lambda bar: {"side": "buy"} if bar["close"] > 10 else None)
    assert result == {"events": 3, "signals": 1, "last_timestamp": "2026-01-02"}
    with pytest.raises(PaperTradingError, match="chronological"):
        ledger.append("2025-12-31", "quote", {"close": 9})
