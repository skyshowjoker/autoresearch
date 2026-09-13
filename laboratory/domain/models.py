from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ExperimentStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    INVALID = "invalid"
    CRASH = "crash"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Decision(str, Enum):
    BASELINE = "baseline"
    KEEP = "keep"
    DISCARD = "discard"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"


@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    title: str
    prompt: str
    mode: str
    dataset_id: str
    base_strategy_version_id: str | None = None
    dev_profile: str = "dev"
    max_trials: int = 10
    max_runtime_seconds: int = 3600
    status: str = "draft"
    owner: str = "local"
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class StrategyVersion:
    version_id: str
    strategy_id: str
    source_sha256: str
    source_path: str
    parent_version_id: str | None = None
    commit_sha: str | None = None
    contract_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    created_by: str = "system"
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class Experiment:
    experiment_id: str
    task_id: str | None
    strategy_version_id: str
    dataset_id: str
    protocol_id: str
    status: ExperimentStatus = ExperimentStatus.QUEUED
    decision: Decision | None = None
    score: float | None = None
    artifact_dir: str | None = None
    parent_experiment_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    finished_at: str | None = None


def to_record(value: Any) -> dict[str, Any]:
    record = asdict(value)
    for key, item in list(record.items()):
        if isinstance(item, Enum):
            record[key] = item.value
    return record
