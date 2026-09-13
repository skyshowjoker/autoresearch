from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ACTION_TYPES = {
    "parameter", "signal", "risk", "exit", "feature", "structure", "simplification",
}


@dataclass(frozen=True)
class OptimizationPlan:
    action_type: str
    hypothesis: str
    expected_effect: str
    failure_condition: str
    changed_components: tuple[str, ...] = ()

    def validate(self) -> "OptimizationPlan":
        if self.action_type not in ACTION_TYPES:
            raise ValueError(f"unsupported optimization action: {self.action_type}")
        if not self.hypothesis.strip() or not self.expected_effect.strip() or not self.failure_condition.strip():
            raise ValueError("optimization plan requires hypothesis, expected_effect and failure_condition")
        if not self.changed_components:
            raise ValueError("optimization plan must name changed_components")
        return self

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OptimizationPlan":
        plan = cls(action_type=value.get("action_type", ""), hypothesis=value.get("hypothesis", ""),
                   expected_effect=value.get("expected_effect", ""), failure_condition=value.get("failure_condition", ""),
                   changed_components=tuple(value.get("changed_components", ())))
        return plan.validate()
