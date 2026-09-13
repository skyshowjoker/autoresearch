from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PaperTradingRegistration:
    experiment_id: str
    strategy_sha256: str
    dataset_id: str
    execution_model: str
    status: str = "registered"
    mode: str = "paper_pending_market_data"


def register_from_artifact(experiment_id: str, artifact_dir: Path) -> PaperTradingRegistration:
    artifact_dir = Path(artifact_dir).resolve()
    summary_path, request_path = artifact_dir / "summary.json", artifact_dir / "request.json"
    if not summary_path.exists() or not request_path.exists():
        raise ValueError("experiment artifact is incomplete")
    summary, request = json.loads(summary_path.read_text()), json.loads(request_path.read_text())
    if summary.get("status") != "success" or request.get("profile") != "final":
        raise ValueError("paper trading requires a successful final evaluation")
    return PaperTradingRegistration(experiment_id=experiment_id,
                                    strategy_sha256=summary["strategy_sha256"],
                                    dataset_id=summary["dataset"],
                                    execution_model=summary.get("execution_model", "unknown"))
