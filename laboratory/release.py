from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from .artifacts import publish_manifest, verify_manifest
from .paper import register_from_artifact


class ReleaseError(ValueError):
    pass


def export_release(experiment_id: str, artifact_dir: Path, approvals: list[dict], output_root: Path) -> Path:
    artifact_dir = Path(artifact_dir).resolve()
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    request = json.loads((artifact_dir / "request.json").read_text()) if (artifact_dir / "request.json").exists() else {}
    summary = json.loads((artifact_dir / "summary.json").read_text()) if (artifact_dir / "summary.json").exists() else {}
    approved = any(item.get("action") == "approve-final" for item in approvals)
    if not approved:
        raise ReleaseError("final approval is required")
    if request.get("profile") != "final" or summary.get("status") != "success":
        raise ReleaseError("only a successful final experiment can be released")
    paper = register_from_artifact(experiment_id, artifact_dir)
    release_dir = output_root / experiment_id
    if release_dir.exists():
        raise ReleaseError("release already exists; choose a new experiment or archive the old release")
    staging = Path(tempfile.mkdtemp(prefix=f".{experiment_id}-", dir=output_root))
    try:
        for name in ("strategy.py", "summary.json", "request.json", "provenance.json", "folds.json", "artifact_manifest.json"):
            source = artifact_dir / name
            if source.exists():
                shutil.copy2(source, staging / name)
        (staging / "paper_registration.json").write_text(json.dumps(paper.__dict__, indent=2))
        (staging / "release.json").write_text(json.dumps({"experiment_id": experiment_id, "release_schema": 1,
                                                           "approval": approvals, "warning": "paper registration only; no live trading"}, indent=2, default=str))
        publish_manifest(staging, {"experiment_id": experiment_id, "release_schema": 1})
        staging.rename(release_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    verify_manifest(release_dir)
    return release_dir
