from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .charts import create_chart
from .compare import compare_indices
from .config import DEFAULT_OUTPUT_PATH, OUTPUT_DIR, START_DATE, SYMBOLS
from .data import load_price_data
from .indicators import add_indicators
from .market_health import build_ai_cycle_score, build_market_health
from .metadata import read_data_status
from .monte_carlo import run_monte_carlo
from .risk import analyze_risk
from .trend import analyze_trend

INDICATOR_FIELDS = ("MA20", "MA50", "MA200", "EMA20", "EMA50", "RSI14", "MACD", "MACD_signal", "MACD_hist", "BB_mid", "BB_upper", "BB_lower")


def _json_value(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round_float(value: Any, digits: int = 6) -> Any:
    value = _json_value(value)
    return round(value, digits) if isinstance(value, float) else value


def _latest_indicators(df: pd.DataFrame) -> dict[str, float | None]:
    latest = df.dropna(subset=["Close"]).iloc[-1]
    return {field: _round_float(latest.get(field)) for field in INDICATOR_FIELDS}


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _risk_reason(risk: dict[str, float]) -> str:
    return f"annual vol {risk['annualized_volatility']:.2%}; max drawdown {risk['max_drawdown']:.2%}; daily VaR95 {risk['var_95']:.2%}"


def _risk_score(risk: dict[str, float]) -> int:
    score = 1
    if risk["annualized_volatility"] > 0.18:
        score += 1
    if risk["annualized_volatility"] > 0.28:
        score += 1
    if risk["max_drawdown"] < -0.25:
        score += 1
    if risk["var_95"] < -0.025:
        score += 1
    return max(1, min(5, score))


def _symbol_reason(trend: dict[str, Any], risk: dict[str, float], monte_carlo: dict[str, Any]) -> str:
    return f"trend_score {trend['trend_score']} from MA/RSI/MACD; risk: {_risk_reason(risk)}; MC uses {monte_carlo['current_regime']} regime"


def _select_symbols(selected_symbols: list[str] | None) -> tuple[Any, ...]:
    if not selected_symbols:
        return SYMBOLS
    allowed = {symbol.key: symbol for symbol in SYMBOLS}
    unknown = [symbol for symbol in selected_symbols if symbol not in allowed]
    if unknown:
        raise ValueError(f"Unknown symbols: {unknown}. Allowed: {sorted(allowed)}")
    return tuple(allowed[symbol] for symbol in selected_symbols)


def _cache_age_days(latest: pd.Timestamp) -> int:
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    return int((today - latest.tz_localize(None)).days)


def build_summary(selected_symbols: list[str] | None = None) -> dict[str, Any]:
    symbols: dict[str, Any] = {}
    enriched_by_key: dict[str, pd.DataFrame] = {}
    latest_dates: list[pd.Timestamp] = []
    active_symbols = _select_symbols(selected_symbols)

    for symbol in active_symbols:
        raw = load_price_data(symbol)
        enriched = add_indicators(raw)
        enriched_by_key[symbol.key] = enriched
        chart_path = create_chart(enriched, symbol.key)
        latest = enriched.dropna(subset=["Close"]).iloc[-1]
        first_date = pd.Timestamp(enriched.index.min())
        latest_date = pd.Timestamp(latest.name)
        latest_dates.append(latest_date)
        trend = analyze_trend(enriched)
        raw_risk = analyze_risk(enriched)
        risk = {**{k: _round_float(v) for k, v in raw_risk.items()}, "risk_score": _risk_score(raw_risk), "reason": _risk_reason(raw_risk)}
        monte_carlo = run_monte_carlo(enriched)
        latest_indicators = _latest_indicators(enriched)
        ai_cycle = build_ai_cycle_score({"latest_close": _round_float(latest["Close"]), "latest_indicators": latest_indicators, "trend": trend, "risk": risk, "monte_carlo": monte_carlo})
        symbols[symbol.key] = {
            "ticker": symbol.ticker,
            "data_source": raw.attrs.get("data_source", "unknown"),
            "download_status": raw.attrs.get("download_status", "unknown"),
            "cache_path": _relative_path(Path(raw.attrs.get("cache_path", ""))),
            "cache_start": first_date.date().isoformat(),
            "latest_date": latest_date.date().isoformat(),
            "cache_age_days": _cache_age_days(latest_date),
            "latest_close": _round_float(latest["Close"]),
            "latest_indicators": latest_indicators,
            "trend": {k: _round_float(v) for k, v in trend.items()},
            "risk": risk,
            "monte_carlo": {k: _round_float(v) for k, v in monte_carlo.items()},
            "ai_cycle": ai_cycle,
            "chart_path": _relative_path(chart_path),
            "reason": _symbol_reason(trend, raw_risk, monte_carlo),
        }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_start": START_DATE,
        "data_end": max(latest_dates).date().isoformat() if latest_dates else None,
        "selected_symbols": [symbol.key for symbol in active_symbols],
        "data_status": read_data_status(),
        "comparison": {k: _round_float(v) for k, v in compare_indices(enriched_by_key).items()},
        "reason": "local CSV analysis; update_data.py owns external data refresh; JSON excludes raw OHLCV series",
        "symbols": symbols,
    }
    summary["ndx_tooltip"] = _build_ndx_tooltip(symbols)
    summary["market_health"] = build_market_health(summary)
    return summary


def _build_ndx_tooltip(symbols: dict[str, Any]) -> dict[str, Any]:
    ndx = symbols.get("NDX")
    if not ndx:
        return {}
    indicators = ndx.get("latest_indicators") or {}
    monte_carlo = ndx.get("monte_carlo") or {}
    ma200 = float(indicators.get("MA200") or 0.0)
    current_price = float(ndx.get("latest_close") or 0.0)
    distribution = {"up_gt_10": 0.0, "up_0_10": 0.0, "down_0_5": 0.0, "down_5_10": 0.0, "down_gt_10": 0.0}
    scenario_map = {"上涨 > 10%": "up_gt_10", "上涨 0~10%": "up_0_10", "下跌 0~5%": "down_0_5", "下跌 5~10%": "down_5_10", "下跌 > 10%": "down_gt_10"}
    for row in monte_carlo.get("probability_table") or []:
        key = scenario_map.get(str(row.get("scenario")))
        if key:
            distribution[key] = round(float(row.get("probability") or 0.0) * 100, 2)
    return {"ma200": round(ma200, 2), "current_price": round(current_price, 2), "ma200_deviation_pct": round(((current_price - ma200) / ma200 * 100) if ma200 else 0.0, 2), "mc_paths": int(monte_carlo.get("paths") or 0), "mc_days": int(monte_carlo.get("days") or 60), "mc_distribution": distribution, "reason": "NDX is used as AI-cycle proxy because Nasdaq 100 better represents AI leaders than broad IXIC."}


def write_summary(summary: dict[str, Any], output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_value), encoding="utf-8")
    return output_path
