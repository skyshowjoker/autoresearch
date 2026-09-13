from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .config import default_backtrader_root, default_cache_root
from .data import DatasetSnapshot
from laboratory.market import quality_report, validate_quality


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(dataset_id="demo_daily_v1", source=None, splits_path=None, benchmark=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", dataset_id):
        raise ValueError("dataset ID must contain only letters, digits, underscore or hyphen")
    target = default_cache_root() / "datasets" / dataset_id
    if target.exists():
        return DatasetSnapshot.open(dataset_id)
    demo = source is None
    if demo:
        sources = {"ORCL": default_backtrader_root() / "datas/orcl-1995-2014.txt"}
        splits = [dict(name=f"dev_{year}", profile="dev", start=f"{year}-01-01", end=f"{year}-12-31") for year in range(2010, 2013)]
        splits.append(dict(name="final_2013", profile="final", start="2013-01-01", end="2013-12-31"))
        benchmark = "ORCL"
    else:
        if not splits_path or not benchmark:
            raise ValueError("custom data requires --splits and --benchmark")
        sources = {path.stem: path for path in Path(source).glob("*.csv")}
        splits = json.loads(Path(splits_path).read_text())
    if not sources or benchmark not in sources:
        raise ValueError("empty universe or benchmark missing")
    validate_splits(splits)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{dataset_id}-", dir=target.parent))
    files, checksums, source_hashes, quality_reports = {}, {}, {}, {}
    for symbol, path in sorted(sources.items()):
        frame = pd.read_csv(path)
        frame.columns = [column.strip().lower().replace(" ", "_") for column in frame.columns]
        frame.index = pd.to_datetime(frame.pop("date"), errors="raise")
        optional = [column for column in ("tradable", "limit_up", "limit_down", "can_sell") if column in frame.columns]
        frame = frame[["open", "high", "low", "close", "volume", *optional]].sort_index()
        for column in frame.columns:
            frame[column] = frame[column].astype(bool) if column in {"tradable", "can_sell"} else frame[column].astype(float)
        report = quality_report(frame)
        quality_reports[symbol] = report
        if frame.index.has_duplicates or frame.empty or not np.isfinite(frame.select_dtypes(include=["number"]).to_numpy()).all():
            raise ValueError(f"invalid or duplicate data: {symbol}")
        validate_quality(report)
        if (frame[["open", "high", "low", "close"]] <= 0).any().any() or (frame.volume < 0).any():
            raise ValueError(f"nonpositive prices or negative volume: {symbol}")
        if (frame.high < frame[["open", "close", "low"]].max(axis=1)).any() or (frame.low > frame[["open", "close", "high"]].min(axis=1)).any():
            raise ValueError(f"inconsistent OHLC: {symbol}")
        relative = f"{symbol}.parquet"
        frame.to_parquet(staging / relative)
        files[symbol] = relative
        checksums[relative] = digest(staging / relative)
        source_hashes[symbol] = digest(path)
    manifest = dict(dataset_id=dataset_id, created_at=datetime.now(timezone.utc).isoformat(),
                    demo=demo, benchmark=benchmark, frequency="1d", files=files, checksums=checksums,
                    source_hashes=source_hashes, splits=splits, adjustment="as_supplied",
                    missing_policy="reject_unaligned", quality_reports=quality_reports,
                    warning="Demo/raw input: corporate actions and survivorship are NOT certified")
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2))
    staging.rename(target)
    return DatasetSnapshot.open(dataset_id)


def validate_splits(splits):
    if not splits or len({split["name"] for split in splits}) != len(splits):
        raise ValueError("splits must be nonempty with unique names")
    previous = None
    final_seen = False
    for split in sorted(splits, key=lambda item: item["start"]):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", split["name"]):
            raise ValueError("invalid split name")
        start, end = pd.Timestamp(split["start"]), pd.Timestamp(split["end"])
        if start > end or (previous is not None and start <= previous):
            raise ValueError("invalid or overlapping validation intervals")
        if split["profile"] not in {"dev", "final"} or (final_seen and split["profile"] == "dev"):
            raise ValueError("final holdout must follow development folds")
        final_seen |= split["profile"] == "final"
        previous = end
