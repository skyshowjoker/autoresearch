from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import default_cache_root


@dataclass(frozen=True)
class DatasetSnapshot:
    root: Path
    manifest: dict

    @classmethod
    def open(cls, dataset_id: str) -> "DatasetSnapshot":
        if not re.fullmatch(r"[A-Za-z0-9_-]+", dataset_id):
            raise ValueError("invalid dataset ID")
        root = default_cache_root() / "datasets" / dataset_id
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"dataset {dataset_id!r} not prepared; run autoquant prepare")
        snapshot = cls(root, json.loads(manifest_path.read_text(encoding="utf-8")))
        snapshot.verify()
        return snapshot

    @property
    def dataset_id(self) -> str:
        return str(self.manifest["dataset_id"])

    @property
    def splits(self) -> list[dict]:
        return list(self.manifest["splits"])

    def symbols(self) -> list[str]:
        return sorted(self.manifest["files"])

    def load(self, symbol: str) -> pd.DataFrame:
        relative = self.manifest["files"].get(symbol)
        if relative is None:
            raise KeyError(f"symbol {symbol!r} not in dataset")
        frame = pd.read_parquet(self.root / relative)
        frame.index = pd.to_datetime(frame.index)
        return frame.sort_index()

    def verify(self) -> None:
        if not self.manifest.get("files") or set(self.manifest["files"].values()) != set(self.manifest["checksums"]):
            raise ValueError("manifest files/checksums mismatch")
        for relative, expected in self.manifest["checksums"].items():
            path = self.root / relative
            if self.root.resolve() not in path.resolve().parents:
                raise ValueError("snapshot path escapes dataset directory")
            if not path.exists():
                raise FileNotFoundError(f"snapshot file missing: {path}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"snapshot checksum mismatch: {relative}")
