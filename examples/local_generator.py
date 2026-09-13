"""Offline provider example; deterministic parameter changes, not an AI model."""

import argparse
import ast
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--brief", type=Path)
    args = parser.parse_args()
    if not args.context and not args.brief:
        parser.error("one of --context or --brief is required")
    context = json.loads(args.context.read_text()) if args.context else {"iteration": 1}
    periods = [10, 15, 25, 30]
    period = periods[(context["iteration"] - 1) % len(periods)]
    tree = ast.parse(args.candidate.read_text())
    changed = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            key, value = node.elts
            if isinstance(key, ast.Constant) and key.value == "fast" and isinstance(value, ast.Constant):
                value.value = period
                changed = True
    if not changed:
        raise ValueError("demo generator expects a fast parameter in the baseline")
    args.candidate.write_text(ast.unparse(tree) + "\n")
    hypothesis = dict(hypothesis=f"Changing fast moving average to {period} may improve responsiveness, at the cost of turnover.",
                      action_type="parameter", expected_effect="improve responsiveness", failure_condition="cost-adjusted score falls",
                      changed_components=["fast_period"],
                      provider="offline_demo", parameter="fast", value=period)
    (args.candidate.parent / "hypothesis.json").write_text(json.dumps(hypothesis, indent=2))


if __name__ == "__main__":
    main()
