# Validation record — 2026-09-07

Environment: macOS Apple M1, project Python 3.10 virtual environment, local `/Users/mac/PycharmProjects/backtrader` imported read-only. CUDA/Torch dependencies removed; `uv sync --extra dev` succeeded after retrying a download timeout.

Commands verified:

```bash
uv run prepare.py
uv run autoquant evaluate --strategy train.py
uv run pytest
uv run python -m compileall -q autoquant train.py prepare.py
git diff --check
```

Test result: **13 passed**. Coverage includes data integrity, split overlap, forward indexing, prohibited imports, fee units/minimum/tax, initial loss drawdown, real engine determinism/next-open execution, empty-trading rejection, holdout flag, promotion risk checks, subprocess evaluation, generator integration, resume/crash behavior, and timeout artifacts. Notebook code cells compile successfully.

Baseline: three development folds, each evaluated under base and doubled costs. `status=success`, `score=-0.25938297545750094`, median Sharpe `0.0238266923629221`, worst Sharpe `-0.03156415512897046`, maximum drawdown `0.1845549135951049`, base-fold fills `20`.

End-to-end autonomous demonstration at `artifacts/verified-local-demo`:

| Candidate | Change | Score | Decision |
|---|---|---:|---|
| 1 | fast SMA 20 → 10 | -0.4009749450760531 | discard |
| 2 | fast SMA 20 → 15 | -0.27517169895256727 | discard |

The session retains the baseline champion. Source train.py is untouched by the loop. Final 2013 holdout was not evaluated. This demonstrates controller correctness, not investable strategy quality. The baseline is not claimed to beat its benchmark.

Artifacts are ignored by Git; keep or export them separately if long-term audit retention is required. Unit/integration tests also produce evaluation records, with distinct protocol hashes from their temporary snapshots. Do not pool those with a research session.

Remaining production boundaries are documented in ARCHITECTURE.md: no certified China ETF dataset, no production China-market execution model, no OS sandbox, no bundled LLM account, no UI or live trading integration.
