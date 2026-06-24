from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .config import CHARTS_DIR, MPL_CONFIG_DIR

MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt


def create_chart(df: pd.DataFrame, symbol_key: str, output_dir: Path = CHARTS_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{symbol_key}.png"

    plot_df = df.dropna(subset=["Close"]).copy()
    recent = plot_df.tail(600)

    fig, axes = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(14, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1]},
    )

    axes[0].plot(recent.index, recent["Close"], label="Close", linewidth=1.4)
    axes[0].plot(recent.index, recent["MA20"], label="MA20", linewidth=1.0)
    axes[0].plot(recent.index, recent["MA50"], label="MA50", linewidth=1.0)
    axes[0].plot(recent.index, recent["MA200"], label="MA200", linewidth=1.0)
    axes[0].plot(recent.index, recent["BB_upper"], label="BB upper", linewidth=0.8, alpha=0.55)
    axes[0].plot(recent.index, recent["BB_lower"], label="BB lower", linewidth=0.8, alpha=0.55)
    axes[0].fill_between(
        recent.index,
        recent["BB_lower"].to_numpy(dtype=float),
        recent["BB_upper"].to_numpy(dtype=float),
        alpha=0.08,
    )
    axes[0].set_title(f"{symbol_key} price and trend indicators")
    axes[0].legend(loc="upper left", ncols=3, fontsize=8)
    axes[0].grid(alpha=0.2)

    axes[1].plot(recent.index, recent["RSI14"], label="RSI14", color="tab:purple", linewidth=1.0)
    axes[1].axhline(70, color="tab:red", linestyle="--", linewidth=0.8)
    axes[1].axhline(30, color="tab:green", linestyle="--", linewidth=0.8)
    axes[1].set_ylim(0, 100)
    axes[1].legend(loc="upper left", fontsize=8)
    axes[1].grid(alpha=0.2)

    axes[2].plot(recent.index, recent["MACD"], label="MACD", linewidth=1.0)
    axes[2].plot(recent.index, recent["MACD_signal"], label="Signal", linewidth=1.0)
    axes[2].bar(recent.index, recent["MACD_hist"], label="Hist", alpha=0.35, width=1.0)
    axes[2].legend(loc="upper left", fontsize=8)
    axes[2].grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
