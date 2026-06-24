from __future__ import annotations

import pandas as pd


def compare_indices(enriched: dict[str, pd.DataFrame]) -> dict[str, object]:
    if "IXIC" not in enriched or "NDX" not in enriched:
        return {}

    closes = pd.DataFrame(
        {
            "IXIC": enriched["IXIC"]["Close"],
            "NDX": enriched["NDX"]["Close"],
        }
    ).dropna()
    returns = closes.pct_change().dropna()
    if returns.empty:
        return {}

    def period_return(symbol: str, days: int) -> float | None:
        if len(closes) <= days:
            return None
        return float(closes[symbol].iloc[-1] / closes[symbol].iloc[-days - 1] - 1)

    ndx_60d = period_return("NDX", 60)
    ixic_60d = period_return("IXIC", 60)
    relative_60d = None if ndx_60d is None or ixic_60d is None else ndx_60d - ixic_60d

    recent_returns = returns.tail(60)
    correlation_60d = float(recent_returns["NDX"].corr(recent_returns["IXIC"]))
    variance = float(recent_returns["IXIC"].var())
    beta = None if variance == 0 else float(recent_returns["NDX"].cov(recent_returns["IXIC"]) / variance)

    if relative_60d is None:
        leadership = "unknown"
    elif relative_60d > 0.01:
        leadership = "NDX_outperforming"
    elif relative_60d < -0.01:
        leadership = "IXIC_outperforming"
    else:
        leadership = "similar"

    return {
        "ndx_vs_ixic_return_20d": _relative_return(closes, 20),
        "ndx_vs_ixic_return_60d": relative_60d,
        "ndx_vs_ixic_return_252d": _relative_return(closes, 252),
        "correlation_60d": correlation_60d,
        "ndx_beta_to_ixic_60d": beta,
        "leadership": leadership,
        "reason": _comparison_reason(leadership, relative_60d, correlation_60d),
    }


def _relative_return(closes: pd.DataFrame, days: int) -> float | None:
    if len(closes) <= days:
        return None
    ndx = closes["NDX"].iloc[-1] / closes["NDX"].iloc[-days - 1] - 1
    ixic = closes["IXIC"].iloc[-1] / closes["IXIC"].iloc[-days - 1] - 1
    return float(ndx - ixic)


def _comparison_reason(leadership: str, relative_60d: float | None, correlation_60d: float) -> str:
    if relative_60d is None:
        return "insufficient aligned history for 60d comparison"
    spread = f"{relative_60d:.2%}"
    corr = f"{correlation_60d:.2f}"
    if leadership == "NDX_outperforming":
        return f"NDX leads IXIC by {spread} over 60d; corr={corr}"
    if leadership == "IXIC_outperforming":
        return f"IXIC leads NDX by {-relative_60d:.2%} over 60d; corr={corr}"
    return f"NDX and IXIC performance is close over 60d; spread={spread}, corr={corr}"
