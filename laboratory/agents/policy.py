from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiffPolicy:
    max_lines_changed: int = 120
    max_functions_changed: int = 8
    max_file_bytes: int = 200_000


class DiffViolation(ValueError):
    pass


def inspect_candidate(parent: Path, candidate: Path, policy: DiffPolicy | None = None) -> dict:
    policy = policy or DiffPolicy()
    parent_text, candidate_text = parent.read_text(encoding="utf-8"), candidate.read_text(encoding="utf-8")
    if len(candidate_text.encode()) > policy.max_file_bytes:
        raise DiffViolation("candidate exceeds file-size budget")
    try:
        parent_tree, candidate_tree = ast.parse(parent_text), ast.parse(candidate_text)
    except SyntaxError as exc:
        raise DiffViolation(f"candidate syntax error: {exc}") from exc
    diff = list(difflib.unified_diff(parent_text.splitlines(), candidate_text.splitlines(), lineterm=""))
    changed_lines = sum(line.startswith(("+", "-")) and not line.startswith(("+++", "---")) for line in diff)
    parent_functions = {node.name for node in ast.walk(parent_tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    candidate_functions = {node.name for node in ast.walk(candidate_tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    changed_functions = parent_functions.symmetric_difference(candidate_functions)
    if changed_lines > policy.max_lines_changed:
        raise DiffViolation(f"candidate changes {changed_lines} lines, limit is {policy.max_lines_changed}")
    if len(changed_functions) > policy.max_functions_changed:
        raise DiffViolation(f"candidate changes {len(changed_functions)} functions, limit is {policy.max_functions_changed}")
    return {"changed_lines": changed_lines, "changed_functions": sorted(changed_functions), "candidate_bytes": len(candidate_text.encode())}
