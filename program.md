# AutoQuant autonomous research protocol

Only edit the candidate `train.py` supplied by the controller. Keep `get_strategy_spec()`.
Do not edit autoquant/, configs/, dataset snapshots, the Backtrader repository, or evaluation artifacts.

1. Read context.json for the development champion and previous experiments.
2. Propose one falsifiable hypothesis; save hypothesis.json beside the candidate.
3. Change one main feature in candidate train.py. Prefer simpler strategies.
4. Exit. The controller evaluates the candidate in a new process and owns promotion.

Use current/past data only, long-only market orders, no trading during warmup.
Do not access files, network, processes, future bars, broker settings or evaluation internals.
Never inspect or evaluate the final holdout in the experiment loop.
Never fabricate metrics or trade records. An invalid/crashed run is not a successful result.
Fixed development intervals are chronological out-of-sample evaluation segments, not automatic parameter fitting.
Repeated development optimization can overfit; report number of trials and preserve final holdout.

The generator is an explicitly configured trusted external command, not an embedded LLM service.
The framework does not launch paid services or send code/data to external models on its own.
Run bounded batches with --iterations. Resume using the same --session.
No automatic commits, resets or workspace train.py replacement. Champion lives in the session directory.
