from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class BriefError(ValueError):
    pass


@dataclass(frozen=True)
class ResearchBrief:
    objective: str
    mode: str = "generate"
    market: str = "unknown"
    universe: list[str] = field(default_factory=list)
    frequency: str = "1d"
    allowed_features: list[str] = field(default_factory=list)
    risk_limits: dict[str, float] = field(default_factory=dict)
    complexity_budget: dict[str, int] = field(default_factory=lambda: {"max_lines_changed": 120, "max_indicators": 5})
    validation_profile: str = "dev"
    task_id: str | None = None

    def validate(self) -> "ResearchBrief":
        if not self.objective.strip():
            raise BriefError("objective must not be empty")
        if self.mode not in {"generate", "optimize", "compare", "validate"}:
            raise BriefError("mode must be generate, optimize, compare or validate")
        if self.frequency not in {"1d", "1h", "15m", "5m"}:
            raise BriefError("unsupported frequency")
        if self.validation_profile not in {"dev", "final"}:
            raise BriefError("validation_profile must be dev or final")
        if self.validation_profile == "final":
            raise BriefError("final profile cannot be used by a generation brief")
        if len(set(self.universe)) != len(self.universe) or not all(self.universe):
            raise BriefError("universe must contain unique nonempty symbols")
        for key, value in self.complexity_budget.items():
            if not isinstance(value, int) or value < 1:
                raise BriefError(f"complexity budget {key} must be positive")
        for key, value in self.risk_limits.items():
            if not isinstance(value, (int, float)) or value < 0:
                raise BriefError(f"risk limit {key} must be nonnegative")
        return self

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ResearchBrief":
        if not isinstance(raw, dict):
            raise BriefError("brief must be an object")
        return cls(**{key: raw[key] for key in cls.__dataclass_fields__ if key in raw}).validate()

    @classmethod
    def from_json(cls, text: str) -> "ResearchBrief":
        try:
            return cls.from_dict(json.loads(text))
        except json.JSONDecodeError as exc:
            raise BriefError(f"invalid brief JSON: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__}

    def prompt_context(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
