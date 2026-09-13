from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .protocol import file_sha256


class ArtifactError(ValueError):
    pass


def write_atomic_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str))
    temporary.replace(path)


def build_manifest(root: Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json" and not path.name.endswith(".tmp"):
            files[str(path.relative_to(root))] = file_sha256(path)
    return {"schema_version": 1, "files": files, "metadata": metadata or {}}


def publish_manifest(root: Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = build_manifest(root, metadata)
    write_atomic_json(Path(root) / "artifact_manifest.json", manifest)
    return manifest


def verify_manifest(root: Path) -> None:
    root = Path(root).resolve()
    manifest_path = root / "artifact_manifest.json"
    if not manifest_path.exists():
        raise ArtifactError(f"artifact manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    actual = build_manifest(root, manifest.get("metadata"))
    if actual["files"] != manifest.get("files", {}):
        raise ArtifactError("artifact checksum mismatch")
