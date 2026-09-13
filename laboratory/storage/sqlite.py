from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from laboratory.domain.models import Experiment, ResearchTask, StrategyVersion, to_record


class LineageStore:
    """Small durable metadata store; large time series remain in artifacts."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS research_tasks (
                task_id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategy_versions (
                version_id TEXT PRIMARY KEY, strategy_id TEXT NOT NULL, source_sha256 TEXT NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY, task_id TEXT, strategy_version_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL, protocol_id TEXT NOT NULL, status TEXT NOT NULL,
                decision TEXT, score REAL, artifact_dir TEXT, parent_experiment_id TEXT,
                payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decision_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT NOT NULL,
                decision TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                approval_id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT NOT NULL,
                action TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_experiment_task ON experiments(task_id);
            CREATE INDEX IF NOT EXISTS idx_experiment_protocol ON experiments(protocol_id);
            """)

    def save_task(self, task: ResearchTask) -> None:
        record = to_record(task)
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO research_tasks VALUES (?, ?, ?)",
                       (task.task_id, json.dumps(record, ensure_ascii=False), task.created_at))

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM research_tasks WHERE task_id = ?", (task_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def update_task_status(self, task_id: str, status: str) -> None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM research_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                return
            payload = json.loads(row["payload"])
            payload["status"] = status
            db.execute("UPDATE research_tasks SET payload = ? WHERE task_id = ?",
                       (json.dumps(payload, ensure_ascii=False), task_id))

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM research_tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def save_strategy_version(self, version: StrategyVersion) -> None:
        record = to_record(version)
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO strategy_versions VALUES (?, ?, ?, ?, ?)",
                       (version.version_id, version.strategy_id, version.source_sha256,
                        json.dumps(record, ensure_ascii=False), version.created_at))

    def save_experiment(self, experiment: Experiment) -> None:
        record = to_record(experiment)
        with self._connect() as db:
            db.execute("""INSERT OR REPLACE INTO experiments
                (experiment_id, task_id, strategy_version_id, dataset_id, protocol_id, status,
                 decision, score, artifact_dir, parent_experiment_id, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (experiment.experiment_id, experiment.task_id, experiment.strategy_version_id,
                 experiment.dataset_id, experiment.protocol_id, experiment.status.value,
                 experiment.decision.value if experiment.decision else None, experiment.score,
                 experiment.artifact_dir, experiment.parent_experiment_id,
                 json.dumps(record, ensure_ascii=False), experiment.created_at))

    def record_decision(self, experiment_id: str, decision: str, payload: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO decision_events (experiment_id, decision, payload, created_at) VALUES (?, ?, ?, datetime('now'))",
                       (experiment_id, decision, json.dumps(payload, ensure_ascii=False, default=str)))

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM experiments WHERE experiment_id = ?", (experiment_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_experiments(self, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = "SELECT payload FROM experiments"
        args: list[Any] = []
        if task_id:
            query += " WHERE task_id = ?"
            args.append(task_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self._connect() as db:
            rows = db.execute(query, args).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def save_approval(self, experiment_id: str, action: str, actor: str, payload: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO approvals (experiment_id, action, actor, payload) VALUES (?, ?, ?, ?)",
                       (experiment_id, action, actor, json.dumps(payload, ensure_ascii=False, default=str)))

    def list_approvals(self, experiment_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM approvals WHERE experiment_id=? ORDER BY approval_id", (experiment_id,)).fetchall()
        return [dict(row, payload=json.loads(row["payload"])) for row in rows]
