from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="AutoQuant fixed evaluation and autonomous experiments")
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--dataset", default="demo_daily_v1")
    prep.add_argument("--source", type=Path)
    prep.add_argument("--splits", type=Path)
    prep.add_argument("--benchmark")
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("--strategy", type=Path, default=Path("train.py"))
    evaluation.add_argument("--dataset")
    evaluation.add_argument("--profile", choices=["dev", "final"], default="dev")
    evaluation.add_argument("--allow-final", action="store_true")
    loop = commands.add_parser("experiment")
    loop.add_argument("--session", type=Path, required=True)
    loop.add_argument("--iterations", type=int, default=1)
    loop.add_argument("--strategy", type=Path, default=Path("train.py"))
    loop.add_argument("--dataset")
    loop.add_argument("--brief", type=Path, help="Research Brief JSON; required for gateway mode")
    loop.add_argument("--task-id", help="existing research task to attach to every experiment")
    loop.add_argument("--theme", choices=["baseline", "robustness", "signal", "risk", "paper"],
                      help="staged research theme included in generator context")
    providers = loop.add_mutually_exclusive_group(required=True)
    providers.add_argument("--generator", help="trusted argv command with {candidate} and {context} placeholders; no shell")
    providers.add_argument("--candidates", type=Path)
    worker_parser = commands.add_parser("_worker", help="internal evaluation worker")
    worker_parser.add_argument("run_dir", type=Path)
    console = commands.add_parser("console", help="serve the local research console")
    console.add_argument("--host", default="127.0.0.1")
    console.add_argument("--port", type=int, default=8765)
    console.add_argument("--db", type=Path)
    release = commands.add_parser("release", help="export an approved final experiment")
    release.add_argument("--experiment-id", required=True)
    release.add_argument("--artifact-dir", type=Path, required=True)
    release.add_argument("--db", type=Path)
    release.add_argument("--output", type=Path, default=Path("releases"))
    register = commands.add_parser("backquant-register", help="register an approved champion in BackQuant SQLite")
    register.add_argument("--experiment-id", required=True)
    register.add_argument("--artifact-dir", type=Path, required=True)
    register.add_argument("--strategy", type=Path)
    register.add_argument("--db", type=Path, help="BackQuant SQLite path")
    register.add_argument("--lineage-db", type=Path)
    register.add_argument("--name")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            from .prepare import prepare
            result = prepare(args.dataset, args.source, args.splits, args.benchmark)
            print(f"dataset: {result.dataset_id}\npath: {result.root}")
            return 0
        if args.command == "evaluate":
            from .evaluate import evaluate
            result = evaluate(args.strategy, args.dataset, args.profile, args.allow_final)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["status"] == "success" else 1
        if args.command == "experiment":
            from .experiment import run_experiments
            brief = json.loads(args.brief.read_text()) if args.brief else None
            state = run_experiments(args.session, args.iterations, args.strategy, args.generator, args.candidates,
                                    args.dataset, brief, args.task_id, args.theme)
            return 0 if state["best"]["status"] == "success" and state["events"][-1]["decision"] in {"keep", "discard"} else 1
        if args.command == "console":
            from laboratory.console_server import DB_PATH, serve
            serve(args.host, args.port, args.db or DB_PATH)
            return 0
        if args.command == "release":
            from laboratory.console_server import DB_PATH
            from laboratory.release import export_release
            from laboratory.storage import LineageStore
            store = LineageStore(args.db or DB_PATH)
            result = export_release(args.experiment_id, args.artifact_dir,
                                    store.list_approvals(args.experiment_id), args.output)
            print(json.dumps({"status": "released", "path": str(result)}, ensure_ascii=False))
            return 0
        if args.command == "backquant-register":
            from laboratory.backquant import register_champion
            from laboratory.console_server import DB_PATH
            from laboratory.storage import LineageStore
            store = LineageStore(args.lineage_db or DB_PATH)
            if not any(item.get("action") == "approve-final" for item in store.list_approvals(args.experiment_id)):
                raise ValueError("final approval is required before BackQuant registration")
            strategy_path = args.strategy or (args.artifact_dir / "strategy.py")
            result = register_champion(experiment_id=args.experiment_id, strategy_path=strategy_path,
                                       artifact_dir=args.artifact_dir, display_name=args.name, db_path=args.db)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        from .evaluate import worker
        return worker(args.run_dir)
    except Exception as exc:
        print(json.dumps(dict(status="error", message=str(exc)), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
