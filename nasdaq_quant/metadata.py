from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import DATA_SOURCE, DATA_STATUS_PATH, METADATA_DIR, SYMBOLS


def build_data_status(data_by_key: dict[str, pd.DataFrame]) -> dict[str, Any]:
    latest_dates = [pd.Timestamp(df.index.max()) for df in data_by_key.values() if df is not None and not df.empty]
    status: dict[str, Any] = {
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": DATA_SOURCE,
        "last_trading_day": max(latest_dates).date().isoformat() if latest_dates else None,
    }
    for symbol in SYMBOLS:
        df = data_by_key.get(symbol.key)
        prefix = symbol.key.lower()
        status[f"{prefix}_records"] = int(len(df)) if df is not None else 0
        status[f"{prefix}_last_trading_day"] = (
            pd.Timestamp(df.index.max()).date().isoformat()
            if df is not None and not df.empty
            else None
        )
    return status


def read_data_status(path: Path = DATA_STATUS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_data_status(status: dict[str, Any], path: Path = DATA_STATUS_PATH) -> Path:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
