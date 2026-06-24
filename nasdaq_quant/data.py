from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import RAW_DATA_DIR, SymbolConfig


REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Adj Close", "Volume")


def cache_path(symbol: SymbolConfig) -> Path:
    return RAW_DATA_DIR / symbol.cache_name


def normalize_price_data(df: pd.DataFrame, label: str) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    data = df.copy()
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"])
        data = data.set_index("Date")
    data.index = pd.to_datetime(data.index)
    data.index.name = "Date"

    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")

    data = data.loc[:, REQUIRED_COLUMNS].copy()
    for column in REQUIRED_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.sort_index()


def validate_price_data(df: pd.DataFrame, label: str) -> None:
    if df.empty:
        raise ValueError(f"{label} has no records")
    if df.index.has_duplicates:
        raise ValueError(f"{label} has duplicate Date values")
    if not df.index.is_monotonic_increasing:
        raise ValueError(f"{label} Date values are not sorted")
    for column in ("Open", "High", "Low", "Close"):
        if df[column].isna().any():
            raise ValueError(f"{label} column {column} contains empty values")
    if pd.isna(df.index.max()):
        raise ValueError(f"{label} latest date is invalid")


def clean_price_data(df: pd.DataFrame, label: str) -> pd.DataFrame:
    data = normalize_price_data(df, label)
    data = data.dropna(subset=["Open", "High", "Low", "Close"])
    data = data[~data.index.duplicated(keep="last")]
    data = data.sort_index()
    validate_price_data(data, label)
    return data


def read_price_csv(path: Path, label: str) -> pd.DataFrame:
    data = pd.read_csv(path, parse_dates=["Date"])
    return clean_price_data(data, label)


def load_price_data(symbol: SymbolConfig) -> pd.DataFrame:
    path = cache_path(symbol)
    if not path.exists():
        legacy_path = path.parent.parent / symbol.cache_name
        if legacy_path.exists():
            path = legacy_path
        else:
            raise FileNotFoundError(f"Missing local CSV: {cache_path(symbol)}")

    data = read_price_csv(path, symbol.key)
    data.attrs["data_source"] = "cache"
    data.attrs["download_status"] = "cache_hit"
    data.attrs["cache_path"] = str(path)
    return data
