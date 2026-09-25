# AutoQuant autonomous research protocol

Only edit the candidate `train.py` supplied by the controller. Keep `get_strategy_spec()`. The controller owns evaluation, promotion, artifact publishing and the session-local Git ledger. Never edit `autoquant/`, `configs/`, dataset snapshots, the Backtrader repository or an evaluation artifact.

## Research discipline

1. Read `context.json`, including the current theme, champion and previous events.
2. Propose one falsifiable hypothesis and save `hypothesis.json` beside the candidate.
3. Change one main feature in candidate `train.py`; prefer simpler strategies.
4. Use only current or past bars, long-only market orders and no trading during warmup.
5. Exit. The controller evaluates the candidate in a new process and owns promotion.

Do not access the network, future bars, broker internals, evaluation internals or the final holdout. Do not fabricate metrics, trades or orders. Fixed development intervals are chronological out-of-sample evaluation segments, not automatic parameter fitting. Repeated development optimization can overfit; report the trial count and preserve the final holdout.

## Staged themes

- `baseline`: prove the strategy contract and repeatability.
- `robustness`: compare folds, assets and cost stress scenarios.
- `signal`: test one falsifiable signal hypothesis.
- `risk`: reduce drawdown or turnover while preserving score.
- `paper`: work only from a successful final approval and prepare paper validation.

The controller writes the selected theme into `context.json`. A candidate must stay within the theme's objective and the brief's complexity budget.

## Promotion and evidence

Candidates must pass source and complexity checks, fixed-protocol evaluation, practical score improvement, worst-fold risk gates and the paired fold significance gate. A candidate that fails any gate is recorded as `discard`, `invalid`, `crash` or `timeout` and never becomes champion.

Every iteration is recorded in `decision.json`, `comparison`, `hypothesis.json`, `diff.json` and `git-events.jsonl`. The Git history is isolated under the session directory; keep commits update the session champion, discard commits remain available for audit and restore the previous active copy. The user's workspace `train.py` is never replaced by the loop.

Run bounded batches with `--iterations` and resume using the same `--session`. The configured generator is a trusted external command; the framework does not launch paid services or send code or data to external models on its own.
