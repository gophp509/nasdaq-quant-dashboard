from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
METADATA_DIR = DATA_DIR / "metadata"
DATA_STATUS_PATH = METADATA_DIR / "data_status.json"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CHARTS_DIR = OUTPUT_DIR / "charts"
HISTORY_DIR = OUTPUT_DIR / "history"
DEFAULT_OUTPUT_PATH = OUTPUT_DIR / "summary.json"
WORK_DIR = PROJECT_ROOT / "work"
MPL_CONFIG_DIR = WORK_DIR / "matplotlib"

START_DATE = "2010-01-01"
TRADING_DAYS = 252
DATA_SOURCE = "Nasdaq Official"


@dataclass(frozen=True)
class SymbolConfig:
    key: str
    ticker: str
    cache_name: str
    nasdaq_symbol: str


SYMBOLS: tuple[SymbolConfig, ...] = (
    SymbolConfig(key="IXIC", ticker="^IXIC", cache_name="IXIC.csv", nasdaq_symbol="COMP"),
    SymbolConfig(key="NDX", ticker="^NDX", cache_name="NDX.csv", nasdaq_symbol="NDX"),
)

MONTE_CARLO_DAYS = 60
MONTE_CARLO_PATHS = 5000
MONTE_CARLO_SEED = 42
