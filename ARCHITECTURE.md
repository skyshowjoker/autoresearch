# Implementation map

The trusted controller imports fixed framework code, snapshots the candidate, hashes data/config/framework/local engine/runtime, then launches a fresh worker with a deadline. The worker imports the snapshot, runs independent chronological development folds with fixed cost scenarios, audits NAV and orders, and emits a summary. The controller appends a locked TSV index.

`experiment.py` adds a persistent session over this evaluator. It supports a trusted command generator or an ordered candidate directory, evaluates the baseline first, promotes only valid and materially improved risk-stable results, and records each decision. Resuming checks protocol identity and reconstructs champion.py from the recorded immutable run artifact. It never resets Git or overwrites source train.py.

| Component | Responsibility |
|---|---|
| prepare.py / autoquant.prepare | Offline import, basic OHLC validation, immutable dataset publication |
| data.py | Checksum verification and snapshot reads |
| contract.py | Strategy factory validation and limited AST misuse detection |
| backtrader_loader.py | Explicit local source import, no UI dependencies |
| engine.py | Fixed broker, warmup trading gate, next-open market execution, audit |
| metrics.py / scoring.py | Daily returns, initial-loss-inclusive drawdown, robust score and gates |
| evaluate.py | Subprocess deadline, provenance, errors, artifacts and result index |
| experiment.py | Candidate provider, promotion, durable state, resume |
| cli.py | Prepare/evaluate/experiment commands |

## Deliberate boundaries

- Sample data is historical ORCL, not the target China ETF universe. Custom offline snapshots are supported, but point-in-time corporate actions and universe certification remain a data-provider responsibility.
- Fixed strategies are reset per OOS fold. There is no ML fitting API and no learned parameters carried between folds.
- Final evaluation requires an explicit flag and is excluded from automatic comparison. Same-user filesystem access is not a secrecy boundary.
- The runner is process-isolated, not an OS security sandbox. Only trusted generators/candidates may run. AST detection is incomplete by design.
- The basic broker does not simulate China T+1, limit queues, market impact or historical fee changes. Do not claim production execution fidelity.
- No LLM credentials/provider account is bundled. An external generator is the integration point, and requires hypothesis.json with a hypothesis string.
- No automatic live trading, UI publishing, Git mutation, or perpetual background scheduling.

## Reproducibility and selection

One trial includes every selected development fold at every fixed cost multiplier. It either completes in full or fails; timeout does not reward incomplete evaluations. Equity is marked to market at the end (no forced close). Turnover is gross fill notional divided by average NAV over the fold. Sharpe uses arithmetic daily mean and sample volatility with 252 sessions/year and zero risk-free rate. CAGR uses trading-day count. The benchmark is close-to-close price return, not certified total return. All assumptions are versioned in protocol provenance.

Score and hard gates are engineering defaults, not statistically calibrated evidence of alpha. Report all trial counts; repeated development selection still overfits. Holdout should be consumed sparingly, followed by paper trading and independent execution validation before considering deployment.
