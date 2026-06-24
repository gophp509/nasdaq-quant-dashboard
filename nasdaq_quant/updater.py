from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .config import DATA_SOURCE, RAW_DATA_DIR, START_DATE, SYMBOLS, SymbolConfig
from .data import cache_path, clean_price_data, read_price_csv
from .metadata import build_data_status, write_data_status


ERROR_LOG_PATH = Path("work") / "update_data_errors.log"


NASDAQ_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}


def migrate_legacy_csvs() -> dict[str, pd.DataFrame]:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    migrated: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        target = cache_path(symbol)
        source = target.parent.parent / symbol.cache_name
        if target.exists():
            data = read_price_csv(target, symbol.key)
        elif source.exists():
            data = read_price_csv(source, symbol.key)
            data.to_csv(target, index=True)
        else:
            data = bootstrap_symbol(symbol)
        migrated[symbol.key] = data
    return migrated


def bootstrap_symbol(symbol: SymbolConfig) -> pd.DataFrame:
    start = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    data = fetch_nasdaq_history(symbol, start, date.today())
    if data.empty:
        raise FileNotFoundError(f"Unable to bootstrap CSV for {symbol.key} from Nasdaq Official")
    target = cache_path(symbol)
    target.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(target, index=True)
    return data


def update_all() -> dict[str, Any]:
    data_by_key = migrate_legacy_csvs()
    errors: list[str] = []

    for symbol in SYMBOLS:
        current = data_by_key[symbol.key]
        try:
            merged = update_symbol(symbol, current)
            data_by_key[symbol.key] = merged
        except Exception as exc:
            errors.append(f"{symbol.key}: {type(exc).__name__}: {exc}")

    if errors:
        _write_error_log(errors)
    elif ERROR_LOG_PATH.exists():
        ERROR_LOG_PATH.unlink()

    status = build_data_status(data_by_key)
    status["source"] = DATA_SOURCE
    status["errors"] = errors
    write_data_status(status)
    return status


def update_symbol(symbol: SymbolConfig, current: pd.DataFrame) -> pd.DataFrame:
    latest = pd.Timestamp(current.index.max()).date()
    start = latest + timedelta(days=1)
    today = date.today()
    if start > today:
        return current

    incremental = fetch_nasdaq_history(symbol, start, today)
    if incremental.empty:
        return current

    merged = clean_price_data(pd.concat([current, incremental]), symbol.key)
    target = cache_path(symbol)
    target.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(target, index=True)
    return merged


def fetch_nasdaq_history(symbol: SymbolConfig, start: date, end: date) -> pd.DataFrame:
    params = urllib.parse.urlencode(
        {
            "assetclass": "index",
            "fromdate": start.isoformat(),
            "todate": end.isoformat(),
            "limit": 9999,
        }
    )
    url = f"https://api.nasdaq.com/api/quote/{symbol.nasdaq_symbol}/historical?{params}"
    request = urllib.request.Request(url, headers=NASDAQ_HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    rows = (((payload or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Adj Close", "Volume"])

    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "Date": _parse_date(row.get("date")),
                "Open": _parse_number(row.get("open")),
                "High": _parse_number(row.get("high")),
                "Low": _parse_number(row.get("low")),
                "Close": _parse_number(row.get("close") or row.get("last")),
                "Adj Close": _parse_number(row.get("close") or row.get("last")),
                "Volume": _parse_number(row.get("volume")) or 0,
            }
        )

    return clean_price_data(pd.DataFrame(records), symbol.key)


def _parse_date(value: Any) -> str:
    text = str(value).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Invalid Nasdaq date: {value}")


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace("$", "").replace(",", "").strip()
    if not text or text in {"--", "N/A"}:
        return None
    return float(text)


def _write_error_log(errors: list[str]) -> Path:
    path = ERROR_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        now = datetime.now().isoformat(timespec="seconds")
        for error in errors:
            writer.writerow([now, error])
    return path
