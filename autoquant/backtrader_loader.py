from __future__ import annotations

import importlib
import sys
from pathlib import Path

from .config import default_backtrader_root


def load_backtrader():
    root = default_backtrader_root().resolve()
    package = root / "backtrader" / "__init__.py"
    if not package.exists():
        raise RuntimeError(
            f"Backtrader source not found at {root}. Set BACKTRADER_ROOT to its repository root."
        )
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    bt = importlib.import_module("backtrader")
    loaded = Path(bt.__file__).resolve()
    if root not in loaded.parents:
        raise RuntimeError(f"wrong Backtrader imported from {loaded}; expected below {root}")
    return bt
