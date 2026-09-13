import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from autoquant.backtrader_loader import load_backtrader
from autoquant.config import ROOT, load_config
from autoquant.contract import ContractError, load_strategy_spec, validate_source
from autoquant.engine import commission_info, run_fold
from autoquant.metrics import calculate
from autoquant.prepare import prepare, validate_splits
from autoquant.scoring import aggregate


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOQUANT_CACHE_DIR", str(tmp_path))
    return prepare()


def test_overlap_rejected():
    with pytest.raises(ValueError):
        validate_splits([dict(name="one", profile="dev", start="2020-01-01", end="2020-12-31"),
                         dict(name="two", profile="final", start="2020-12-31", end="2021-12-31")])


def test_future_index_rejected(tmp_path):
    candidate = tmp_path / "train.py"
    candidate.write_text("value = self.data.close[1]")
    with pytest.raises(ContractError):
        validate_source(candidate)


def test_forbidden_import(tmp_path):
    candidate = tmp_path / "train.py"
    candidate.write_text("import subprocess")
    with pytest.raises(ContractError):
        validate_source(candidate)


def test_snapshot_tampering(snapshot):
    path = snapshot.root / "ORCL.parquet"
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="checksum"):
        snapshot.verify()


def test_commission_units():
    config = dict(commission=0.001, minimum_commission=5, sell_tax=0.002)
    costs = commission_info(load_backtrader(), config, 1)
    assert costs.getcommission(1000, 10) == 10
    assert costs.getcommission(-1000, 10) == 30
    assert costs.getcommission(1, 10) == 5


def test_initial_loss_in_drawdown():
    index = pd.bdate_range("2020-01-01", periods=4)
    metrics = calculate(pd.Series([100, 90, 90, 90], index=index), pd.Series([100]*4, index=index))
    assert metrics["max_drawdown"] == pytest.approx(0.1)


def test_fold_determinism_and_next_open(snapshot):
    config = load_config()
    spec = load_strategy_spec(ROOT / "train.py", load_backtrader())
    first = run_fold(spec, snapshot, snapshot.splits[0], config)
    second = run_fold(spec, snapshot, snapshot.splits[0], config)
    assert first[0] == second[0]
    pd.testing.assert_frame_equal(first[1], second[1])
    assert first[1].index.min() >= pd.Timestamp(snapshot.splits[0]["start"])
    completed = [order for order in first[2] if order["status"] == "Completed"]
    assert completed
    assert completed[0]["date"] > str(first[1].index[0].date())
    assert all(np.isfinite(list(first[0]["metrics"].values())))


def test_gate_rejects_no_fills(snapshot):
    config = load_config()
    spec = load_strategy_spec(ROOT / "train.py", load_backtrader())
    result = run_fold(spec, snapshot, snapshot.splits[0], config)[0]
    result["metrics"]["fills"] = 0
    assert aggregate([result], config)["status"] == "invalid"


def test_final_requires_explicit_flag():
    from autoquant.evaluate import evaluate

    with pytest.raises(ValueError, match="allow-final"):
        evaluate(ROOT / "train.py", profile="final")


def test_promotion_requires_risk_stability():
    from autoquant.scoring import should_promote

    config = load_config()["scoring"]
    champion = dict(status="success", score=1, worst_sharpe=0.5, max_drawdown=0.2)
    assert should_promote(dict(champion, score=1.1), champion, config)
    assert not should_promote(dict(champion, score=1.01), champion, config)
    assert not should_promote(dict(champion, score=2, max_drawdown=0.3), champion, config)
    assert not should_promote(dict(champion, status="invalid", score=None), champion, config)
