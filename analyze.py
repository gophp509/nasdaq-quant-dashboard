from __future__ import annotations

import argparse
import json
from pathlib import Path

from nasdaq_quant.config import DEFAULT_OUTPUT_PATH, HISTORY_DIR
from nasdaq_quant.dashboard import DASHBOARD_OUTPUT_PATH, build_dashboard
from nasdaq_quant.market_health import build_history_snapshot
from nasdaq_quant.summary import build_summary, write_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze local Nasdaq CSV data and render outputs.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path for summary.json")
    parser.add_argument("--dashboard-output", default=str(DASHBOARD_OUTPUT_PATH), help="Path for dashboard.html")
    parser.add_argument("--symbols", default="IXIC,NDX", help="Comma-separated symbols: IXIC,NDX")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected_symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    output_path = Path(args.output)

    summary = build_summary(selected_symbols=selected_symbols)
    write_summary(summary, output_path)
    dashboard_path = build_dashboard(summary, output_path=Path(args.dashboard_output), selected_symbols=selected_symbols)
    snapshot_path = _write_history_snapshot(summary)

    print(output_path)
    print(dashboard_path)
    if snapshot_path:
        print(snapshot_path)


def _write_history_snapshot(summary: dict) -> Path | None:
    data_end = summary.get("data_end")
    if not data_end:
        return None
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    target = HISTORY_DIR / f"summary_{data_end}.json"
    snapshot = build_history_snapshot(summary)
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if {"date", "trend_score", "risk_score", "mc_up_probability", "ai_cycle_score"}.issubset(existing):
                return None
        except Exception:
            pass
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    main()
