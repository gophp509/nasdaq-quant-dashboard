from __future__ import annotations

import math

import pandas as pd


def _clip_score(score: int) -> int:
    return max(-5, min(5, score))


def analyze_trend(df: pd.DataFrame) -> dict[str, object]:
    latest = df.dropna(subset=["Close", "MA20", "MA50", "MA200", "RSI14", "MACD_hist"]).iloc[-1]
    close = float(latest["Close"])
    ma20 = float(latest["MA20"])
    ma50 = float(latest["MA50"])
    ma200 = float(latest["MA200"])
    rsi = float(latest["RSI14"])
    macd_hist = float(latest["MACD_hist"])

    score = 0

    if close > ma200:
        long_term_trend = "bullish"
        score += 2
    else:
        long_term_trend = "bearish"
        score -= 2

    if ma20 > ma50:
        mid_term_trend = "bullish"
        score += 1
    elif ma20 < ma50:
        mid_term_trend = "bearish"
        score -= 1
    else:
        mid_term_trend = "neutral"

    returns_20d = df["Close"].pct_change(20).iloc[-1]
    if math.isnan(float(returns_20d)):
        returns_20d = 0.0

    if returns_20d > 0.03 and macd_hist > 0:
        short_term_momentum = "strong_positive"
        score += 2
    elif returns_20d > 0 and macd_hist > 0:
        short_term_momentum = "positive"
        score += 1
    elif returns_20d < -0.03 and macd_hist < 0:
        short_term_momentum = "strong_negative"
        score -= 2
    elif returns_20d < 0 and macd_hist < 0:
        short_term_momentum = "negative"
        score -= 1
    else:
        short_term_momentum = "neutral"

    if rsi >= 70:
        score -= 1
    elif rsi <= 30:
        score += 1

    return {
        "long_term_trend": long_term_trend,
        "mid_term_trend": mid_term_trend,
        "short_term_momentum": short_term_momentum,
        "trend_score": _clip_score(score),
        "price_vs_ma200_pct": (close / ma200) - 1,
        "ma20_vs_ma50_pct": (ma20 / ma50) - 1,
        "return_20d": float(returns_20d),
        "reason": (
            f"close {'above' if close > ma200 else 'below'} MA200; "
            f"MA20 {'above' if ma20 > ma50 else 'below' if ma20 < ma50 else 'near'} MA50; "
            f"20d return {float(returns_20d):.2%}; RSI {rsi:.1f}"
        ),
    }
