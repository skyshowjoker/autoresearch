import numpy as np
import pandas as pd


def calculate(equity, benchmark):
    returns = equity.pct_change().iloc[1:]
    if len(returns) < 2 or not np.isfinite(returns).all() or (equity <= 0).any():
        raise ValueError("invalid equity series")
    years = len(returns) / 252
    annual = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)
    vol = float(returns.std(ddof=1) * np.sqrt(252))
    sharpe = float(returns.mean() * 252 / vol) if vol > 1e-12 else 0.0
    drawdown = float(-(equity / equity.cummax() - 1).min())
    benchmark_returns = benchmark.pct_change().reindex(returns.index)
    if benchmark_returns.isna().any():
        raise ValueError("benchmark does not cover equity dates")
    active = returns - benchmark_returns
    tracking = float(active.std(ddof=1) * np.sqrt(252))
    bench_annual = float((1 + benchmark_returns).prod() ** (1 / years) - 1)
    return dict(days=len(returns), annual_return=annual, volatility=vol, sharpe=sharpe,
                max_drawdown=drawdown, calmar=annual / max(drawdown, 0.01),
                annual_excess=annual - bench_annual,
                information_ratio=float(active.mean() * 252 / tracking) if tracking > 1e-12 else 0.0)
