from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


class MarketRuleError(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionRules:
    lot_size: int = 1
    max_participation: float = 1.0
    enforce_tradable: bool = True
    enforce_limits: bool = False
    enforce_t1: bool = False

    def validate(self):
        if self.lot_size < 1 or self.max_participation <= 0 or self.max_participation > 1:
            raise MarketRuleError("lot_size must be >= 1 and participation must be in (0, 1]")
        return self


def quality_report(frame: pd.DataFrame) -> dict[str, Any]:
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise MarketRuleError("market data index must be DatetimeIndex")
    required = {"open", "high", "low", "close", "volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise MarketRuleError(f"missing market columns: {', '.join(missing)}")
    ohlc = frame[["open", "high", "low", "close"]]
    return {
        "rows": int(len(frame)), "start": str(frame.index.min().date()) if len(frame) else None,
        "end": str(frame.index.max().date()) if len(frame) else None,
        "duplicate_dates": int(frame.index.duplicated().sum()),
        "missing_values": int(frame[sorted(required)].isna().sum().sum()),
        "zero_volume_rows": int((frame["volume"] <= 0).sum()),
        "nonpositive_price_rows": int((ohlc <= 0).any(axis=1).sum()),
        "ohlc_inconsistency_rows": int((frame.high < ohlc.max(axis=1)).sum() + (frame.low > ohlc.min(axis=1)).sum()),
        "optional_columns": sorted(set(frame.columns) - required),
    }


def validate_quality(report: dict[str, Any]) -> None:
    if report["rows"] == 0 or report["duplicate_dates"] or report["missing_values"] or report["nonpositive_price_rows"] or report["ohlc_inconsistency_rows"]:
        raise MarketRuleError(f"market quality failed: {report}")


def tradable_on(frame: pd.DataFrame, timestamp) -> bool:
    if "tradable" in frame.columns:
        return bool(frame.loc[timestamp, "tradable"])
    return bool(frame.loc[timestamp, "volume"] > 0)


def executable_size(frame: pd.DataFrame, timestamp, requested: float, rules: ExecutionRules) -> int:
    if requested == 0 or not tradable_on(frame, timestamp):
        return 0
    if abs(requested) % rules.lot_size:
        raise MarketRuleError("requested size violates lot_size")
    volume = float(frame.loc[timestamp, "volume"])
    return int(min(abs(requested), volume * rules.max_participation) // rules.lot_size * rules.lot_size) * (1 if requested > 0 else -1)


def check_limit(frame: pd.DataFrame, timestamp, price: float, side: int) -> bool:
    if "limit_up" not in frame.columns or "limit_down" not in frame.columns:
        return True
    upper, lower = frame.loc[timestamp, "limit_up"], frame.loc[timestamp, "limit_down"]
    if pd.isna(upper) or pd.isna(lower):
        return True
    return price < upper if side > 0 else price > lower
