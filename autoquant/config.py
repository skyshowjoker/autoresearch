from __future__ import annotations

import os
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def default_cache_root() -> Path:
    return Path(os.environ.get("AUTOQUANT_CACHE_DIR", Path.home() / ".cache" / "autoquant"))


def default_backtrader_root() -> Path:
    return Path(os.environ.get("BACKTRADER_ROOT", "/Users/mac/PycharmProjects/backtrader"))


def load_config() -> dict[str, Any]:
    config = json.loads((ROOT / "configs" / "research.json").read_text())
    execution = config["execution"]
    for key in ("initial_cash", "commission", "minimum_commission", "sell_tax", "slippage", "lot_size", "warmup_bars", "max_participation"):
        value = execution[key]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid execution parameter: {key}")
    if execution["initial_cash"] <= 0 or execution["lot_size"] < 1 or execution["warmup_bars"] < 1:
        raise ValueError("cash, lot size and warmup must be positive")
    if execution["max_participation"] <= 0 or execution["max_participation"] > 1:
        raise ValueError("max_participation must be in (0, 1]")
    multipliers = config["validation"]["cost_multipliers"]
    if 1 not in multipliers or any(not math.isfinite(value) or value < 1 for value in multipliers):
        raise ValueError("cost multipliers must include baseline 1 and be finite >= 1")
    return config


@dataclass(frozen=True)
class Paths:
    root: Path = ROOT

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def results(self) -> Path:
        return self.root / "results.tsv"
