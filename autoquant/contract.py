from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


FORBIDDEN_IMPORTS = {
    "http", "requests", "socket", "subprocess", "urllib", "ftplib",
    "paramiko", "shutil",
    "os", "sys", "pathlib", "importlib", "builtins", "autoquant", "pickle", "ctypes",
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "open"}


@dataclass(frozen=True)
class StrategySpec:
    strategy_class: type
    params: dict[str, Any]
    meta: dict[str, Any]


class ContractError(ValueError):
    pass


def validate_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise ContractError(f"strategy syntax error: {exc}") from exc
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                if name.split(".")[0] in FORBIDDEN_IMPORTS:
                    errors.append(f"forbidden import: {name}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            errors.append(f"forbidden call: {node.func.id}()")
        if isinstance(node, ast.Attribute) and node.attr in {"setcash", "setcommission", "set_coc", "set_coo", "set_slippage_perc", "add_cash", "setbroker", "array"}:
            errors.append(f"forbidden internal access: {node.attr}")
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
            if node.value.attr in {"open", "high", "low", "close", "volume", "datetime"}:
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, (int, float)) and node.slice.value > 0:
                    errors.append("future bar indexing is forbidden")
    if errors:
        raise ContractError("; ".join(errors[:5]))


def _load_module(path: Path) -> ModuleType:
    module_name = f"candidate_{path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ContractError(f"cannot import strategy: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_strategy_spec(path: Path, bt: ModuleType) -> StrategySpec:
    validate_source(path)
    module = _load_module(path)
    factory = getattr(module, "get_strategy_spec", None)
    if not callable(factory):
        raise ContractError("train.py must define get_strategy_spec()")
    raw = factory()
    if not isinstance(raw, dict):
        raise ContractError("get_strategy_spec() must return a dict")
    cls = raw.get("strategy_class")
    if not isinstance(cls, type) or not issubclass(cls, bt.Strategy):
        raise ContractError("strategy_class must be a backtrader.Strategy subclass")
    params = raw.get("params", {})
    meta = raw.get("meta", {})
    if not isinstance(params, dict) or not isinstance(meta, dict):
        raise ContractError("params and meta must be dictionaries")
    required = {"name", "version", "universe", "frequency", "warmup_bars"}
    missing = sorted(required - meta.keys())
    if missing:
        raise ContractError(f"strategy metadata missing: {', '.join(missing)}")
    if not isinstance(meta["universe"], list) or not meta["universe"]:
        raise ContractError("meta.universe must be a non-empty list")
    if not all(isinstance(symbol, str) for symbol in meta["universe"]) or len(set(meta["universe"])) != len(meta["universe"]):
        raise ContractError("meta.universe must contain unique strings")
    if not isinstance(meta["warmup_bars"], int) or meta["warmup_bars"] < 1:
        raise ContractError("warmup_bars must be a positive integer")
    return StrategySpec(cls, params, meta)
