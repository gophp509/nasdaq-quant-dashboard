from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MONTE_CARLO_DAYS, MONTE_CARLO_PATHS, MONTE_CARLO_SEED


def _regime_series(close: pd.Series) -> pd.Series:
    ma200 = close.rolling(window=200, min_periods=200).mean()
    regime = pd.Series("bear", index=close.index)
    regime[close >= ma200] = "bull"
    return regime[ma200.notna()]


def _regime_stats(returns: pd.Series, regimes: pd.Series) -> dict[str, tuple[float, float]]:
    aligned = pd.DataFrame({"returns": returns, "regime": regimes}).dropna()
    fallback = (float(returns.mean()), float(returns.std(ddof=1)))
    stats: dict[str, tuple[float, float]] = {}
    for regime in ("bull", "bear"):
        values = aligned.loc[aligned["regime"] == regime, "returns"]
        stats[regime] = (float(values.mean()), float(values.std(ddof=1))) if len(values) >= 30 else fallback
    return stats


def _transition_probabilities(regimes: pd.Series) -> dict[str, dict[str, float]]:
    transitions = pd.DataFrame({"current": regimes.shift(1), "next": regimes}).dropna()
    defaults = {"bull": {"bull": 0.95, "bear": 0.05}, "bear": {"bull": 0.05, "bear": 0.95}}
    if transitions.empty:
        return defaults
    matrix: dict[str, dict[str, float]] = {}
    for regime in ("bull", "bear"):
        rows = transitions[transitions["current"] == regime]
        if rows.empty:
            matrix[regime] = defaults[regime]
            continue
        counts = rows["next"].value_counts(normalize=True)
        matrix[regime] = {"bull": float(counts.get("bull", 0.0)), "bear": float(counts.get("bear", 0.0))}
    return matrix


def run_monte_carlo(df: pd.DataFrame, days: int = MONTE_CARLO_DAYS, paths: int = MONTE_CARLO_PATHS, seed: int = MONTE_CARLO_SEED) -> dict[str, float | int]:
    simulation = simulate_monte_carlo_paths(df, days=days, paths=paths, seed=seed)
    terminal_prices = simulation["terminal_prices"]
    last_close = simulation["last_close"]
    p10, p50, p90 = np.percentile(terminal_prices, [10, 50, 90])
    terminal_returns = (terminal_prices / last_close) - 1
    stats = simulation["stats"]
    transitions = simulation["transitions"]
    current_regime = simulation["current_regime"]
    return {
        "days": days,
        "paths": paths,
        "p10": float(p10),
        "p50": float(p50),
        "p90": float(p90),
        "expected_return_low": float((p10 / last_close) - 1),
        "expected_return_mid": float((p50 / last_close) - 1),
        "expected_return_high": float((p90 / last_close) - 1),
        "probability_up": float((terminal_prices > last_close).mean()),
        "probability_table": _probability_table(terminal_returns, days),
        "current_regime": current_regime,
        "bull_daily_mean": stats["bull"][0],
        "bear_daily_mean": stats["bear"][0],
        "bull_to_bull_prob": transitions["bull"]["bull"],
        "bear_to_bear_prob": transitions["bear"]["bear"],
        "reason": f"regime starts {current_regime}; MA200 split with bull stay {transitions['bull']['bull']:.1%}, bear stay {transitions['bear']['bear']:.1%}",
    }


def _probability_table(returns: np.ndarray, days: int) -> list[dict[str, float | str]]:
    horizon = f"未来{days}天"
    buckets = (
        ("上涨 > 10%", returns > 0.10),
        ("上涨 0~10%", (returns > 0.0) & (returns <= 0.10)),
        ("下跌 0~5%", (returns <= 0.0) & (returns > -0.05)),
        ("下跌 5~10%", (returns <= -0.05) & (returns > -0.10)),
        ("下跌 > 10%", returns <= -0.10),
    )
    return [{"horizon": horizon, "scenario": label, "probability": float(mask.mean())} for label, mask in buckets]


def simulate_monte_carlo_paths(df: pd.DataFrame, days: int = MONTE_CARLO_DAYS, paths: int = MONTE_CARLO_PATHS, seed: int = MONTE_CARLO_SEED) -> dict[str, object]:
    close = df["Close"].dropna()
    returns = close.pct_change().dropna()
    if returns.empty:
        raise ValueError("Not enough data to run Monte Carlo simulation.")
    last_close = float(close.iloc[-1])
    regimes = _regime_series(close)
    if regimes.empty:
        raise ValueError("Not enough data to classify bull/bear regimes.")
    stats = _regime_stats(returns, regimes)
    transitions = _transition_probabilities(regimes)
    current_regime = str(regimes.iloc[-1])
    rng = np.random.default_rng(seed)
    simulated_returns = np.empty((paths, days), dtype=float)
    simulated_regimes = np.full(paths, current_regime, dtype=object)
    for day in range(days):
        for regime in ("bull", "bear"):
            mask = simulated_regimes == regime
            count = int(mask.sum())
            if count == 0:
                continue
            mu, sigma = stats[regime]
            simulated_returns[mask, day] = rng.normal(loc=mu, scale=sigma, size=count)
            switch_draws = rng.random(count)
            simulated_regimes[mask] = np.where(switch_draws < transitions[regime]["bull"], "bull", "bear")
    price_paths = last_close * np.cumprod(1 + simulated_returns, axis=1)
    return {
        "last_close": last_close,
        "price_paths": price_paths,
        "terminal_prices": price_paths[:, -1],
        "p10_series": np.percentile(price_paths, 10, axis=0),
        "p50_series": np.percentile(price_paths, 50, axis=0),
        "p90_series": np.percentile(price_paths, 90, axis=0),
        "current_regime": current_regime,
        "stats": stats,
        "transitions": transitions,
    }
