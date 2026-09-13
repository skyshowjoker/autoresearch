from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision(path: Path) -> dict[str, str | None]:
    try:
        commit = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.run(["git", "-C", str(path), "diff", "--quiet"], check=False).returncode != 0
        return {"commit": commit, "dirty": str(dirty).lower()}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def build_protocol_payload(*, manifest: dict, config: dict, framework_files: dict[str, str],
                           engine_files: dict[str, str], project_root: Path | None = None,
                           engine_root: Path | None = None) -> dict:
    return {
        "schema_version": 1,
        "manifest": manifest,
        "config": config,
        "framework_files": framework_files,
        "engine_files": engine_files,
        "framework_revision": git_revision(project_root) if project_root else None,
        "engine_revision": git_revision(engine_root) if engine_root else None,
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
    }


def protocol_id(payload: dict) -> str:
    return sha256_bytes(canonical_json(payload).encode("utf-8"))
