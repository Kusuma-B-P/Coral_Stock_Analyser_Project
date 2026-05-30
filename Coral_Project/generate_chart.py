#!/usr/bin/env python3
"""
Generates a candlestick chart with volume bars and MA10/MA20 overlays
from data/prices.jsonl and saves it to data/chart.png.

Usage: python generate_chart.py
"""
import json
import os
import sys
import pandas as pd
import mplfinance as mpf


def load_prices(path: str = "data/prices.jsonl") -> pd.DataFrame:
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run fetch_prices.py <TICKER> first.")
        sys.exit(1)

    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        print(f"ERROR: {path} is empty.")
        sys.exit(1)

    df = pd.DataFrame(records)

    # Parse date and set as index (required by mplfinance)
    df["Date"] = pd.to_datetime(df["date"])
    df = df.set_index("Date").sort_index()

    # Ensure correct dtypes
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype(int)

    # mplfinance expects title-cased OHLCV column names
    df = df.rename(columns={
        "open":   "Open",
        "high":   "High",
        "low":    "Low",
        "close":  "Close",
        "volume": "Volume",
    })

    return df


def generate_chart(df: pd.DataFrame, output_path: str = "data/chart.png"):
    os.makedirs("data", exist_ok=True)

    ticker       = df["ticker"].iloc[-1]       if "ticker"       in df.columns else ""
    company_name = df["company_name"].iloc[-1] if "company_name" in df.columns else ticker

    title = f"{company_name} ({ticker})  —  Daily Candlestick  |  MA10 & MA20"

    # Moving average lines as addplot overlays
    ma10 = mpf.make_addplot(df["Close"].rolling(10).mean(), color="dodgerblue",  width=1.2, label="MA10")
    ma20 = mpf.make_addplot(df["Close"].rolling(20).mean(), color="darkorange",  width=1.2, label="MA20")

    mpf.plot(
        df,
        type="candle",
        style="charles",
        title=title,
        ylabel="Price (USD)",
        ylabel_lower="Volume",
        volume=True,
        addplot=[ma10, ma20],
        savefig=dict(fname=output_path, dpi=150, bbox_inches="tight"),
        figsize=(14, 8),
        tight_layout=True,
    )


def main():
    df = load_prices()
    generate_chart(df)
    print("Chart saved to data/chart.png")


if __name__ == "__main__":
    main()