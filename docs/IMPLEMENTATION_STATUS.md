# Implementation status

Last updated: 2026-09-19

## Completed

### P0/P1 — protocol and research core

- Fixed strategy contract and offline dataset snapshot.
- Manifest/checksum validation for data and artifacts.
- Backtrader subprocess evaluation with timeout cleanup.
- Walk-forward development folds and cost stress runs.
- Protocol identity including framework, config, runtime and local engine source.
- Domain models and experiment state machine.
- SQLite lineage projection for strategy versions, experiments and decisions.

### P2 — strategy generation

- `ResearchBrief` with objective, mode, universe, features, risk limits and complexity budget.
- `AgentGateway` with explicit `{candidate}` and `{brief}` inputs.
- Structured `hypothesis.json` requirement.
- Candidate diff, file-size and function-change gates.
- Agent runtime artifact and generator logs.

### P3 — strategy optimization

- Explicit optimization action types: parameter, signal, risk, exit, feature, structure and simplification.
- Required optimization fields: hypothesis, expected effect, failure condition and changed components.
- Parent/candidate summary and fold-level comparison reports.
- Promotion gate includes score improvement, worst-fold Sharpe and drawdown stability.
- Experiment budgets: maximum trials, runtime, consecutive no-improvement and consecutive failure limits.
- Durable session counters and automatic stop reasons.
- Paired development-fold significance gate with deterministic sign permutation.
- Session-local Git keep/discard ledger; the user workspace remains unchanged.
- Staged research themes: baseline, robustness, signal, risk and paper.

## Verification

- `uv run pytest`: 24 passed.
- Real ORCL demo baseline: 3 development folds × 2 cost scenarios.
- Brief → Gateway → candidate diff → optimization contract → walk-forward → decision: passed.
- Candidate artifacts include `agent_run.json`, `hypothesis.json`, `diff.json`, `comparison` and lineage records.

## Next

### P4 — data and execution realism (in progress)

- Added optional `tradable`, `limit_up`, `limit_down` and `can_sell` snapshot columns.
- Added per-symbol quality reports and strict OHLC/duplicate/missing-value validation.
- Added configurable participation cap, tradability checks, limit checks and T+1 checks.
- Added execution rule fixtures and summary exposure of `execution_model`/`data_quality`.
- Certified target-market snapshots and full point-in-time corporate-action semantics remain pending.

### P5 — visual console (first slice complete)

- Added dependency-free local HTTP console at `laboratory/console_server.py`.
- Added static dashboard at `console/index.html`.
- Added task create/list APIs, experiment list/detail APIs, artifact listing, equity series and final approval endpoint.
- Added approval persistence in SQLite; research state remains independent from BackQuant UI globals.
- Full lineage graph, live SSE/WebSocket progress, authentication/RBAC and richer charts remain pending.

### P6 — release validation

- Added final-only approval gate, paper registration and auditable release package export.
- Added CLI/API release export with release manifest and explicit paper-only warning.
- Real final evaluation, live market paper feed, broker reconciliation and pre-live checklist remain pending.

### Delivery route verification

- Stage 1 gate passed on 2026-09-19: two identical development baselines produced the same protocol, score, strategy hash and orders.
- Stage 2 tests cover walk-forward folds, multi-cost evaluation, future-index rejection, artifacts and subprocess timeout isolation.
- Stage 3 end-to-end demo recorded theme context, paired significance evidence and `git-events.jsonl` in a session.
- Stage 4 now includes a BackQuant SQLite adapter (`autoquant_strategies`) and an append-only chronological paper replay ledger. Live market feed and broker reconciliation remain future work.
