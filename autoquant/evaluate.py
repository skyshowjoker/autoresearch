from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import signal
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow

from . import __version__
from .backtrader_loader import load_backtrader
from .config import ROOT, default_backtrader_root, load_config
from .contract import load_strategy_spec, validate_source
from .data import DatasetSnapshot
from .engine import run_fold
from .prepare import digest, validate_splits
from .scoring import aggregate
from laboratory.artifacts import publish_manifest, verify_manifest
from laboratory.protocol import build_protocol_payload, file_sha256, protocol_id
from laboratory.storage import LineageStore
from laboratory.domain.models import Experiment, ExperimentStatus, StrategyVersion, Decision


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False, default=str))
    temporary.replace(path)


def protocol_identity(snapshot, config):
    framework_paths = sorted((ROOT / "autoquant").rglob("*.py")) + sorted((ROOT / "laboratory").rglob("*.py"))
    framework_paths += [ROOT / "configs/research.json", ROOT / "pyproject.toml"]
    framework = {str(path.relative_to(ROOT)): file_sha256(path) for path in framework_paths if path.exists()}
    engine_root = default_backtrader_root()
    engine = {str(path.relative_to(engine_root)): file_sha256(path) for path in sorted((engine_root / "backtrader").rglob("*.py"))}
    payload = build_protocol_payload(manifest=snapshot.manifest, config=config, framework_files=framework,
                                     engine_files=engine, project_root=ROOT, engine_root=engine_root)
    return protocol_id(payload), payload


def worker(run_dir):
    started = time.monotonic()
    request = json.loads((run_dir / "request.json").read_text())
    try:
        np.random.seed(42)
        random.seed(42)
        bt = load_backtrader()
        snapshot = DatasetSnapshot.open(request["dataset"])
        validate_splits(snapshot.splits)
        config = request["config"]
        identity, _ = protocol_identity(snapshot, config)
        if identity != request["protocol_id"]:
            raise ValueError("protocol changed before worker launch")
        spec = load_strategy_spec(run_dir / "strategy.py", bt)
        folds = [fold for fold in snapshot.splits if fold["profile"] == request["profile"]]
        if not folds:
            raise ValueError("profile has no folds")
        runs = []
        for fold in folds:
            for multiplier in config["validation"]["cost_multipliers"]:
                result, equity, orders, trades = run_fold(spec, snapshot, fold, config, multiplier)
                prefix = f'{fold["name"]}-cost{multiplier}'
                equity.to_parquet(run_dir / f"{prefix}-equity.parquet")
                write_json(run_dir / f"{prefix}-orders.json", orders)
                write_json(run_dir / f"{prefix}-trades.json", trades)
                runs.append(result)
        write_json(run_dir / "folds.json", runs)
        summary = aggregate(runs, config)
        identity_after, _ = protocol_identity(DatasetSnapshot.open(request["dataset"]), load_config())
        snapshot.verify()
        if identity_after != identity:
            raise ValueError("protocol changed during evaluation")
    except Exception as exc:
        summary = dict(status="crash", score=None, reasons=[str(exc)])
        write_json(run_dir / "error.json", dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))
        traceback.print_exc()
    summary.update(runtime_seconds=time.monotonic() - started, framework_version=__version__,
                   dataset=request["dataset"], profile=request["profile"], protocol_id=request["protocol_id"],
                   strategy_sha256=digest(run_dir / "strategy.py"),
                   execution_model=request["config"]["execution"].get("model", "unknown"),
                   data_quality=snapshot.manifest.get("quality_reports", {}))
    write_json(run_dir / "summary.json", summary)
    publish_manifest(run_dir, {"status": summary["status"], "protocol_id": summary.get("protocol_id")})
    return 0 if summary["status"] == "success" else 1


def evaluate(strategy, dataset=None, profile="dev", allow_final=False, output_root=None, task_id=None, parent_experiment_id=None):
    if profile == "final" and not allow_final:
        raise ValueError("final evaluation requires explicit --allow-final; never use it for automatic selection")
    config = load_config()
    dataset = dataset or config["dataset"]
    snapshot = DatasetSnapshot.open(dataset)
    protocol_id, provenance = protocol_identity(snapshot, config)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = (Path(output_root) if output_root else ROOT / "artifacts") / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "strategy.py").write_bytes(Path(strategy).read_bytes())
    request = dict(dataset=dataset, profile=profile, config=config, protocol_id=protocol_id)
    write_json(run_dir / "request.json", request)
    write_json(run_dir / "provenance.json", provenance)
    started = time.monotonic()
    try:
        validate_source(run_dir / "strategy.py")
        with (run_dir / "run.log").open("w") as log:
            env = dict(os.environ, PYTHONHASHSEED="42")
            process = subprocess.Popen([sys.executable, "-m", "autoquant.cli", "_worker", str(run_dir)],
                                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
            try:
                process.wait(timeout=config["validation"]["timeout_seconds"])
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise TimeoutError("evaluation exceeded fixed timeout")
            except BaseException:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        if not (run_dir / "summary.json").exists():
            raise RuntimeError(f"worker exited {process.returncode} without summary; inspect run.log")
        summary = json.loads((run_dir / "summary.json").read_text())
        verify_manifest(run_dir)
    except Exception as exc:
        summary = dict(status="timeout" if isinstance(exc, TimeoutError) else "crash", score=None,
                       reasons=[str(exc)], runtime_seconds=time.monotonic()-started,
                       protocol_id=protocol_id, profile=profile, dataset=dataset)
        write_json(run_dir / "summary.json", summary)
        write_json(run_dir / "error.json", dict(message=str(exc), traceback=traceback.format_exc()))
    summary["artifact_dir"] = str(run_dir)
    write_json(run_dir / "summary.json", summary)
    publish_manifest(run_dir, {"status": summary.get("status"), "protocol_id": summary.get("protocol_id")})
    append_result(run_id, summary)
    record_lineage(run_id, strategy, summary, task_id=task_id, parent_experiment_id=parent_experiment_id)
    return summary


def record_lineage(run_id: str, strategy: Path, summary: dict, decision: str = "baseline",
                   parent_experiment_id: str | None = None, task_id: str | None = None) -> None:
    """Best-effort metadata projection; artifacts remain the source of truth."""
    try:
        store = LineageStore(ROOT / ".cache" / "laboratory.db")
        source_hash = digest(strategy)
        version = StrategyVersion(version_id=source_hash[:16], strategy_id="local-candidate",
                                  source_sha256=source_hash, source_path=str(strategy),
                                  metadata={"profile": summary.get("profile")})
        store.save_strategy_version(version)
        experiment = Experiment(experiment_id=run_id, task_id=task_id, strategy_version_id=version.version_id,
                                dataset_id=summary.get("dataset", ""), protocol_id=summary.get("protocol_id", ""),
                                status=ExperimentStatus(summary.get("status", "crash")),
                                decision=Decision(decision), score=summary.get("score"),
                                artifact_dir=summary.get("artifact_dir"), parent_experiment_id=parent_experiment_id)
        store.save_experiment(experiment)
        store.record_decision(run_id, experiment.decision.value, {"summary": summary})
    except Exception:
        # Metadata projection must never turn a valid backtest into a failed one.
        return


def append_result(run_id, summary):
    import fcntl

    with (ROOT / "results.tsv").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0, 2)
        writer = csv.writer(handle, delimiter="\t")
        if handle.tell() == 0:
            writer.writerow(["experiment", "status", "score", "profile", "protocol", "artifacts"])
        writer.writerow([run_id, summary["status"], summary["score"], summary["profile"], summary["protocol_id"], summary["artifact_dir"]])
