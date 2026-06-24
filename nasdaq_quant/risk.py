from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TRADING_DAYS


def analyze_risk(df: pd.DataFrame) -> dict[str, float]:
    close = df["Close"].dropna()
    returns = close.pct_change().dropna()
    if returns.empty:
        raise ValueError("Not enough data to calculate risk metrics.")

    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = cumulative / running_max - 1

    return {
        "annualized_volatility": float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        "max_drawdown": float(drawdown.min()),
        "var_95": float(returns.quantile(0.05)),
        "var_99": float(returns.quantile(0.01)),
    }
