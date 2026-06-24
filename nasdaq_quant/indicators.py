from __future__ import annotations

import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    close = result["Close"]

    result["MA20"] = close.rolling(window=20, min_periods=20).mean()
    result["MA50"] = close.rolling(window=50, min_periods=50).mean()
    result["MA200"] = close.rolling(window=200, min_periods=200).mean()
    result["EMA20"] = close.ewm(span=20, adjust=False).mean()
    result["EMA50"] = close.ewm(span=50, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    result["RSI14"] = 100 - (100 / (1 + rs))
    result.loc[avg_loss == 0, "RSI14"] = 100

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    result["MACD"] = ema12 - ema26
    result["MACD_signal"] = result["MACD"].ewm(span=9, adjust=False).mean()
    result["MACD_hist"] = result["MACD"] - result["MACD_signal"]

    bb_mid = result["MA20"]
    bb_std = close.rolling(window=20, min_periods=20).std()
    result["BB_mid"] = bb_mid
    result["BB_upper"] = bb_mid + (2 * bb_std)
    result["BB_lower"] = bb_mid - (2 * bb_std)

    result["Daily_Return"] = close.pct_change()
    return result
