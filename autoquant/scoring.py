import numpy as np


def should_promote(candidate, champion, config, significance=None):
    if candidate["status"] != "success":
        return False
    if champion["status"] != "success":
        return True
    return ((significance is None or significance.get("passed", False))
            and candidate["score"] >= champion["score"] + config["min_improvement"]
            and candidate["worst_sharpe"] >= champion["worst_sharpe"] - config["max_worst_sharpe_degradation"]
            and candidate["max_drawdown"] <= champion["max_drawdown"] + config["max_drawdown_degradation"])


def fold_score(metrics):
    return float(0.35 * np.clip(metrics["sharpe"], -3, 3)
                 + 0.25 * np.clip(metrics["calmar"], -3, 3)
                 + 0.20 * np.clip(metrics["information_ratio"], -3, 3)
                 + 0.20 * np.clip(metrics["annual_excess"], -1, 1)
                 - 0.01 * metrics["turnover"])


def aggregate(runs, config):
    base = [run for run in runs if run["cost_multiplier"] == 1]
    invalid = []
    for run in runs:
        metrics = run["metrics"]
        if not all(np.isfinite(value) for value in metrics.values()):
            invalid.append(f'{run["fold"]}: nonfinite metrics')
        if metrics["days"] < config["validation"]["min_days"] or metrics["fills"] < config["validation"]["min_fills"]:
            invalid.append(f'{run["fold"]}: insufficient days or fills')
        if metrics["max_drawdown"] > config["validation"]["max_drawdown"]:
            invalid.append(f'{run["fold"]}: drawdown gate')
    if not base:
        raise ValueError("no base folds")
    scores = [fold_score(run["metrics"]) for run in base]
    median = float(np.median(scores))
    score = median - config["scoring"]["dispersion_penalty"] * float(np.std(scores))
    score -= config["scoring"]["worst_penalty"] * (median - min(scores))
    stressed = [fold_score(run["metrics"]) for run in runs if run["cost_multiplier"] > 1]
    if stressed:
        score -= config["scoring"]["cost_penalty"] * max(0, median - float(np.median(stressed)))
    return dict(status="invalid" if invalid else "success", score=None if invalid else float(score),
                reasons=invalid, median_sharpe=float(np.median([run["metrics"]["sharpe"] for run in base])),
                worst_sharpe=min(run["metrics"]["sharpe"] for run in base),
                max_drawdown=max(run["metrics"]["max_drawdown"] for run in runs),
                num_folds=len(base), num_fills=sum(run["metrics"]["fills"] for run in base))
