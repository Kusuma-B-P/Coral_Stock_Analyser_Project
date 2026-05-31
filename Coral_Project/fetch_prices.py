#!/usr/bin/env python3
"""
Fetches 30 days of daily OHLCV price data for a given ticker
using yfinance and saves it to data/prices.jsonl for Coral to query.

Usage: python fetch_prices.py NVDA
"""
import yfinance as yf
import json
import sys
import os


def fetch_prices(ticker: str) -> int:
    os.makedirs("data", exist_ok=True)
    # Redirect yfinance cache to project data dir to avoid SQLite disk I/O errors
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "yfcache")
    os.makedirs(cache_dir, exist_ok=True)
    yf.set_tz_cache_location(cache_dir)

    print(f"Fetching price data for {ticker}...")

    stock = yf.Ticker(ticker)

    df = None
    for attempt in range(3):
        try:
            df = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if not df.empty:
                break
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                import time
                time.sleep(5)

    if df is None or df.empty:
        print(f"ERROR: No data found for ticker '{ticker}'. Check the symbol.")
        sys.exit(1)


    df = df.reset_index()
    # Flatten multi-level columns if present (yfinance sometimes returns these)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    # Normalise the date column name -- yfinance 1.x returns 'index', older returns 'Date'
    if "index" in df.columns and "Date" not in df.columns:
        df = df.rename(columns={"index": "Date"})

    # Fetch company metadata
    try:
        info = stock.info
        company_name = info.get("longName", ticker)
        sector = info.get("sector", "Unknown")
        market_cap = info.get("marketCap", 0) or 0
        pe_ratio = info.get("trailingPE", None)
        week_52_high = info.get("fiftyTwoWeekHigh", None)
        week_52_low = info.get("fiftyTwoWeekLow", None)
    except Exception as e:
        print(f"Warning: Could not fetch company metadata: {e}")
        company_name, sector, market_cap = ticker, "Unknown", 0
        pe_ratio, week_52_high, week_52_low = None, None, None

    output_path = "data/prices.jsonl"
    with open(output_path, "w") as f:
        for _, row in df.iterrows():
            record = {
                "ticker": ticker,
                "company_name": company_name,
                "sector": sector,
                "date": str(row["Date"])[:10],
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
                "market_cap": int(market_cap),
                "pe_ratio": float(pe_ratio) if pe_ratio else None,
                "week_52_high": float(week_52_high) if week_52_high else None,
                "week_52_low": float(week_52_low) if week_52_low else None,
            }
            f.write(json.dumps(record) + "\n")

    print(f"Saved {len(df)} days of data for {company_name} ({ticker}) -> {output_path}")
    return len(df)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_prices.py <TICKER>")
        print("Example: python fetch_prices.py NVDA")
        sys.exit(1)

    ticker_input = sys.argv[1].upper().strip()
    fetch_prices(ticker_input)
