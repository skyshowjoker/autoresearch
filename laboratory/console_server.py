from __future__ import annotations

import json
import mimetypes
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from autoquant.config import ROOT
from .storage import LineageStore
from .domain.models import ResearchTask
from .release import export_release, ReleaseError
from .paper import register_from_artifact


CONSOLE_DIR = ROOT / "console"
DB_PATH = ROOT / ".cache" / "laboratory.db"


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")


class ConsoleHandler(BaseHTTPRequestHandler):
    server_version = "AutoQuantConsole/0.1"

    @property
    def store(self):
        return self.server.store

    def _send_json(self, value, status=HTTPStatus.OK):
        payload = _json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, path: Path):
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        if path == CONSOLE_DIR / "index.html":
            self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/":
            return self._send_file(CONSOLE_DIR / "index.html")
        if path == "/api/health":
            return self._send_json({"status": "ok", "service": "autoquant-console"})
        if path == "/api/experiments":
            return self._send_json({"items": self.store.list_experiments(limit=200)})
        if path == "/api/research/tasks":
            return self._send_json({"items": self.store.list_tasks(limit=200)})
        if path.startswith("/api/experiments/"):
            parts = path.split("/")
            if len(parts) < 4:
                return self._send_json({"error": "experiment id required"}, HTTPStatus.BAD_REQUEST)
            experiment_id = parts[3]
            record = self.store.get_experiment(experiment_id)
            if record is None:
                return self._send_json({"error": "experiment not found"}, HTTPStatus.NOT_FOUND)
            if len(parts) == 4:
                record["approvals"] = self.store.list_approvals(experiment_id)
                return self._send_json(record)
            artifact = Path(record.get("artifact_dir", "")).resolve()
            if artifact != artifact.parent and ROOT not in artifact.parents:
                return self._send_json({"error": "artifact outside project"}, HTTPStatus.FORBIDDEN)
            if parts[4] == "equity":
                files = sorted(artifact.glob("*equity.parquet"))
                if not files:
                    return self._send_json({"items": []})
                import pandas as pd
                frame = pd.read_parquet(files[0])
                return self._send_json({"items": [{"date": str(index), "equity": float(row.equity)} for index, row in frame.iterrows()]})
            if parts[4] == "artifacts":
                if len(parts) == 5:
                    return self._send_json({"items": sorted(str(path.relative_to(artifact)) for path in artifact.rglob("*") if path.is_file())})
                relative = unquote("/".join(parts[5:])).lstrip("/")
                target = (artifact / relative).resolve()
                if artifact not in target.parents or not target.is_file():
                    return self._send_json({"error": "artifact not found"}, HTTPStatus.NOT_FOUND)
                size = target.stat().st_size
                suffix = target.suffix.lower()
                if suffix in {".json", ".jsonl", ".txt", ".md", ".py", ".yaml", ".yml", ".csv"}:
                    if size > 1_000_000:
                        return self._send_json({"error": "text preview exceeds 1MB"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    text = target.read_text(encoding="utf-8", errors="replace")
                    return self._send_json({"path": relative, "kind": "text", "content": text, "size": size})
                return self._send_json({"path": relative, "kind": "binary", "size": size,
                                        "download_url": f"/api/experiments/{experiment_id}/artifacts/{relative}"})
            if parts[4] == "paper":
                try:
                    return self._send_json(register_from_artifact(experiment_id, artifact).__dict__)
                except ValueError as exc:
                    return self._send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
        return self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        if path == "/api/research/tasks":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                task = ResearchTask(task_id=body.get("task_id") or uuid.uuid4().hex,
                                    title=str(body.get("title", "Untitled research")),
                                    prompt=str(body.get("prompt", "")), mode=str(body.get("mode", "generate")),
                                    dataset_id=str(body.get("dataset_id", "demo_daily_v1")),
                                    base_strategy_version_id=body.get("base_strategy_version_id"),
                                    dev_profile=str(body.get("dev_profile", "dev")),
                                    max_trials=int(body.get("max_trials", 10)),
                                    max_runtime_seconds=int(body.get("max_runtime_seconds", 3600)))
                if not task.prompt.strip():
                    raise ValueError("prompt is required")
                if task.mode not in {"generate", "optimize", "compare", "validate"}:
                    raise ValueError("invalid mode")
                if task.max_trials < 1 or task.max_runtime_seconds < 1:
                    raise ValueError("budgets must be positive")
                self.store.save_task(task)
                return self._send_json(task.__dict__, HTTPStatus.CREATED)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                return self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if path.startswith("/api/experiments/") and path.endswith("/export"):
            experiment_id = path.split("/")[3]
            record = self.store.get_experiment(experiment_id)
            if record is None:
                return self._send_json({"error": "experiment not found"}, HTTPStatus.NOT_FOUND)
            try:
                release_dir = export_release(experiment_id, Path(record["artifact_dir"]),
                                              self.store.list_approvals(experiment_id), ROOT / "releases")
                return self._send_json({"status": "released", "path": str(release_dir)}, HTTPStatus.CREATED)
            except ReleaseError as exc:
                return self._send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
        if not path.startswith("/api/experiments/") or not path.endswith("/approve-final"):
            return self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        experiment_id = path.split("/")[3]
        record = self.store.get_experiment(experiment_id)
        if record is None:
            return self._send_json({"error": "experiment not found"}, HTTPStatus.NOT_FOUND)
        if record.get("status") != "success":
            return self._send_json({"error": "only successful experiments can request final approval"}, HTTPStatus.CONFLICT)
        artifact = Path(record.get("artifact_dir", "")).resolve()
        request_path = artifact / "request.json"
        if not request_path.exists() or json.loads(request_path.read_text()).get("profile") != "final":
            return self._send_json({"error": "final approval requires a final-profile experiment"}, HTTPStatus.CONFLICT)
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        actor = str(body.get("actor", "local-reviewer"))
        if not actor.strip():
            return self._send_json({"error": "actor is required"}, HTTPStatus.BAD_REQUEST)
        self.store.save_approval(experiment_id, "approve-final", actor, {"note": body.get("note", "")})
        return self._send_json({"status": "approved", "experiment_id": experiment_id, "actor": actor}, HTTPStatus.CREATED)

    def log_message(self, *_args):
        return


def serve(host="127.0.0.1", port=8765, db_path=DB_PATH):
    server = ThreadingHTTPServer((host, port), ConsoleHandler)
    server.store = LineageStore(Path(db_path))
    print(f"AutoQuant console: http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def serve_in_thread(host="127.0.0.1", port=0, db_path=DB_PATH):
    server = ThreadingHTTPServer((host, port), ConsoleHandler)
    server.store = LineageStore(Path(db_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
