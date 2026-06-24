from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import HISTORY_DIR


def build_market_health(summary: dict[str, Any], history_dir: Path = HISTORY_DIR) -> dict[str, Any]:
    symbols = summary.get("symbols", {})
    if not symbols:
        return {}
    trend_strength = _avg([_trend_to_10(item["trend"]["trend_score"]) for item in symbols.values()])
    risk_level = _avg([_risk_to_10(item["risk"]["risk_score"]) for item in symbols.values()])
    mc_up_probability = _avg([float(item["monte_carlo"]["probability_up"]) for item in symbols.values()])
    ai_cycle_scores = {key: build_ai_cycle_score(item) for key, item in symbols.items()}
    ai_cycle_score = _avg([score["score"] for score in ai_cycle_scores.values()])
    history = read_health_history(history_dir)
    current_snapshot = {"date": str(summary.get("data_end") or ""), "trend_score": round(trend_strength, 2), "risk_score": round(risk_level, 2), "mc_up_probability": round(mc_up_probability, 4), "ai_cycle_score": round(ai_cycle_score, 2)}
    history_with_current = _merge_current(history, current_snapshot)
    return {
        "current": current_snapshot,
        "changes_30d": {"trend_score": _change(history, current_snapshot, "trend_score", 30), "risk_score": _change(history, current_snapshot, "risk_score", 30), "mc_up_probability": _change(history, current_snapshot, "mc_up_probability", 30), "ai_cycle_score": _change(history, current_snapshot, "ai_cycle_score", 30)},
        "statuses": {"trend_strength": _trend_status(_change(history, current_snapshot, "trend_score", 30)), "risk_level": _risk_status(_change(history, current_snapshot, "risk_score", 30)), "mc_up_probability": _mc_status(_change(history, current_snapshot, "mc_up_probability", 30)), "ai_cycle": ai_cycle_stage(ai_cycle_score)},
        "ai_cycle": {"score": round(ai_cycle_score, 2), "stage": ai_cycle_stage(ai_cycle_score), "symbols": ai_cycle_scores},
        "alert": build_market_alert(history_with_current),
        "history_90d": history_with_current[-90:],
        "reason": "computed during analyze.py from summary aggregates; dashboard only displays these values",
    }


def build_history_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    health = summary.get("market_health") or build_market_health(summary)
    current = health.get("current", {})
    return {"date": current.get("date") or summary.get("data_end"), "trend_score": _round(current.get("trend_score")), "risk_score": _round(current.get("risk_score")), "mc_up_probability": _round(current.get("mc_up_probability"), 4), "ai_cycle_score": _round(current.get("ai_cycle_score"))}


def read_health_history(history_dir: Path = HISTORY_DIR) -> list[dict[str, Any]]:
    if not history_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(history_dir.glob("summary_*.json")):
        try:
            snapshot = _normalize_snapshot(json.loads(path.read_text(encoding="utf-8")))
            if snapshot:
                rows.append(snapshot)
        except Exception:
            continue
    deduped = {str(row["date"]): row for row in rows}
    return [deduped[key] for key in sorted(deduped)]


def build_market_alert(history: list[dict[str, Any]]) -> dict[str, Any]:
    streak = _deterioration_streak(history)
    if streak >= 60:
        level, label = "red", "高风险"
    elif streak >= 30:
        level, label = "orange", "风险增加"
    elif streak >= 3:
        level, label = "yellow", "注意"
    else:
        level, label = "green", "正常"
    return {"level": level, "label": label, "deterioration_days": streak, "reason": "trend down + risk up + MC up probability down" if streak else "no persistent multi-factor deterioration"}


def build_ai_cycle_score(item: dict[str, Any]) -> dict[str, Any]:
    latest = float(item.get("latest_close") or 0.0)
    ma200 = float((item.get("latest_indicators") or {}).get("MA200") or latest or 1.0)
    price_vs_ma200 = float((item.get("trend") or {}).get("price_vs_ma200_pct") or 0.0)
    vol = float((item.get("risk") or {}).get("annualized_volatility") or 0.0)
    max_drawdown = abs(float((item.get("risk") or {}).get("max_drawdown") or 0.0))
    mc_up = float((item.get("monte_carlo") or {}).get("probability_up") or 0.0)
    ma200_component = _clamp(price_vs_ma200 / 0.35 * 30, 0, 30)
    mc_component = _clamp(mc_up * 25, 0, 25)
    vol_component = _clamp(vol / 0.35 * 20, 0, 20)
    drawdown_component = _clamp((1 - min(max_drawdown, 0.45) / 0.45) * 15, 0, 15)
    extension_component = _clamp((latest / ma200 - 1) / 0.45 * 10, 0, 10) if ma200 else 0
    score = _clamp(ma200_component + mc_component + vol_component + drawdown_component + extension_component, 0, 100)
    return {"score": round(score, 2), "stage": ai_cycle_stage(score), "components": {"ma200_deviation": round(ma200_component, 2), "monte_carlo": round(mc_component, 2), "volatility": round(vol_component, 2), "drawdown_risk": round(drawdown_component, 2), "price_extension": round(extension_component, 2)}}


def ai_cycle_stage(score: float) -> str:
    if score < 25:
        return "早期"
    if score < 50:
        return "中期"
    if score < 75:
        return "中后期"
    return "泡沫期"


def _normalize_snapshot(data: dict[str, Any]) -> dict[str, Any] | None:
    if {"date", "trend_score", "risk_score", "mc_up_probability", "ai_cycle_score"}.issubset(data):
        return {"date": str(data["date"]), "trend_score": float(data["trend_score"]), "risk_score": float(data["risk_score"]), "mc_up_probability": float(data["mc_up_probability"]), "ai_cycle_score": float(data["ai_cycle_score"])}
    current = (data.get("market_health") or {}).get("current") or {}
    if current:
        return {"date": str(current.get("date") or data.get("data_end")), "trend_score": float(current.get("trend_score", 0)), "risk_score": float(current.get("risk_score", 0)), "mc_up_probability": float(current.get("mc_up_probability", 0)), "ai_cycle_score": float(current.get("ai_cycle_score", 0))}
    return None


def _merge_current(history: list[dict[str, Any]], current: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in history if row.get("date") != current.get("date")]
    rows.append(current)
    return sorted(rows, key=lambda row: str(row.get("date")))


def _deterioration_streak(history: list[dict[str, Any]]) -> int:
    if len(history) < 2:
        return 0
    streak = 0
    for prev, curr in zip(reversed(history[:-1]), reversed(history[1:])):
        if float(curr["trend_score"]) < float(prev["trend_score"]) and float(curr["risk_score"]) > float(prev["risk_score"]) and float(curr["mc_up_probability"]) < float(prev["mc_up_probability"]):
            streak += 1
        else:
            break
    return streak


def _change(history: list[dict[str, Any]], current: dict[str, Any], field: str, days: int) -> float:
    if not history:
        return 0.0
    baseline = history[-days] if len(history) >= days else history[0]
    return round(float(current[field]) - float(baseline[field]), 4)


def _trend_status(change: float) -> str:
    return "改善中" if change > 0.5 else "减弱中" if change < -0.5 else "稳定"


def _risk_status(change: float) -> str:
    return "上升" if change > 0.5 else "下降" if change < -0.5 else "稳定"


def _mc_status(change: float) -> str:
    return "增强" if change > 0.03 else "减弱" if change < -0.03 else "稳定"


def _trend_to_10(score: float) -> float:
    return _clamp(float(score) + 5, 0, 10)


def _risk_to_10(score: float) -> float:
    return _clamp((float(score) - 1) / 4 * 10, 0, 10)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _round(value: Any, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))
