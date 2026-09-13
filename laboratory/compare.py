from __future__ import annotations

from typing import Any


def compare_summaries(parent: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    numeric = ("score", "median_sharpe", "worst_sharpe", "max_drawdown", "num_fills", "runtime_seconds")
    delta = {}
    for key in numeric:
        old, new = parent.get(key), candidate.get(key)
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            delta[key] = new - old
    fold_delta = _fold_delta(parent.get("artifact_dir"), candidate.get("artifact_dir"))
    return {
        "parent_status": parent.get("status"), "candidate_status": candidate.get("status"),
        "parent_artifact": parent.get("artifact_dir"), "candidate_artifact": candidate.get("artifact_dir"),
        "delta": delta, "fold_delta": fold_delta,
        "candidate_better_score": candidate.get("score") is not None and parent.get("score") is not None
                                  and candidate["score"] > parent["score"],
    }


def _fold_delta(parent_dir: str | None, candidate_dir: str | None) -> list[dict[str, Any]]:
    import json
    from pathlib import Path
    if not parent_dir or not candidate_dir:
        return []
    parent_path, candidate_path = Path(parent_dir) / "folds.json", Path(candidate_dir) / "folds.json"
    if not parent_path.exists() or not candidate_path.exists():
        return []
    parent = {(item.get("fold"), item.get("cost_multiplier")): item for item in json.loads(parent_path.read_text())}
    candidate = {(item.get("fold"), item.get("cost_multiplier")): item for item in json.loads(candidate_path.read_text())}
    output = []
    for key in sorted(parent.keys() & candidate.keys(), key=str):
        old, new = parent[key].get("metrics", {}), candidate[key].get("metrics", {})
        output.append({"fold": key[0], "cost_multiplier": key[1], "score_delta": _difference(old, new, "score"),
                       "sharpe_delta": _difference(old, new, "sharpe"),
                       "drawdown_delta": _difference(old, new, "max_drawdown")})
    return output


def _difference(old: dict, new: dict, key: str):
    if isinstance(old.get(key), (int, float)) and isinstance(new.get(key), (int, float)):
        return new[key] - old[key]
    return None
