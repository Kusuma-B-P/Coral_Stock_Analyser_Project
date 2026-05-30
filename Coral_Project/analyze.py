#!/usr/bin/env python3
"""
Stock Move Analyzer -- powered by Coral + Gemini + Groq
- Fetches price data via yfinance
- Generates a candlestick chart and sends it to Gemini Vision for chart analysis
- Queries live data (news, ratings, insider trades) via Coral SQL
- Combines chart analysis + SQL data and sends to Groq (llama-3.3-70b-versatile)
- Prints two clearly labelled sections: Chart Analysis and Fundamental Analysis

Usage: python analyze.py NVDA
"""
import sys
import subprocess
import os
import base64
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from google import genai
from google.genai import types
from groq import Groq

load_dotenv()

GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


def check_env():
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not FINNHUB_API_KEY:
        missing.append("FINNHUB_API_KEY")
    if missing:
        print(f"ERROR: Missing keys in .env: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your keys.")
        sys.exit(1)


def fetch_sec_filings(company_name: str, ticker: str) -> str:
    """Fetch recent 8-K filings directly from SEC EDGAR full-text search API."""
    print("  -> SEC 8-K filings (EDGAR direct)...")
    try:
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "forms": "8-K",
            "entity": company_name,
            "dateRange": "custom",
            "startdt": (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),
            "enddt": datetime.now().strftime("%Y-%m-%d"),
        }
        headers = {"User-Agent": "StockAnalyzer contact@example.com"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        if not hits:
            return "(no recent 8-K filings found)"
        rows = []
        for h in hits[:10]:
            src = h.get("_source", {})
            name = (src.get("display_names") or [""])[0]
            rows.append(
                f"{src.get('file_date','')} | {src.get('form_type') or src.get('form','')} | "
                f"{', '.join(src.get('items', []))} | {name}"
            )
        return "file_date | form | items | entity\n" + "\n".join(rows)
    except Exception as e:
        print(f"    Warning: SEC EDGAR fetch failed: {e}")
        return f"(SEC EDGAR unavailable: {e})"


def run_coral_sql(query: str, label: str) -> str:
    """Run a SQL query through Coral CLI and return result as text."""
    print(f"  -> {label}...")
    try:
        result = subprocess.run(
            ["coral", "sql", query.strip()],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "FINNHUB_API_KEY": FINNHUB_API_KEY}
        )
        if result.returncode != 0:
            print(f"    Warning: {result.stderr.strip()[:100]}")
            return f"(query failed: {result.stderr.strip()[:200]})"
        return result.stdout.strip() or "(no results)"
    except subprocess.TimeoutExpired:
        print(f"    Warning: {label} timed out")
        return "(query timed out)"
    except FileNotFoundError:
        print("ERROR: 'coral' not found. Run setup.ps1 first.")
        sys.exit(1)


def analyze_chart_with_gemini(ticker: str, chart_path: str) -> str:
    """Send chart image to Gemini Vision and return the analysis text."""
    print("  -> Chart image analysis (Gemini Vision)...")
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        with open(chart_path, "rb") as f:
            image_data = f.read()

        prompt = (
            f"This is a stock price chart for {ticker}. "
            "Describe what you see: the trend, any patterns (head and shoulders, "
            "double top, support/resistance), volume behaviour, and what the "
            "moving averages suggest."
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[
                types.Part.from_bytes(data=image_data, mime_type="image/png"),
                prompt,
            ],
        )
        return response.text.strip()
    except Exception as e:
        print(f"    Warning: Gemini chart analysis failed: {e}")
        return f"(chart analysis unavailable: {e})"


def fetch_and_analyze(ticker: str):
    ticker = ticker.upper().strip()

    print(f"\n{'='*60}")
    print(f"  Stock Move Analyzer: {ticker}")
    print(f"{'='*60}\n")

    # Step 1: Refresh price data
    print("Fetching latest price data from yfinance...")
    subprocess.run(
        [sys.executable, "fetch_prices.py", ticker],
        check=True
    )

    # Step 2: Generate candlestick chart
    print("\nGenerating candlestick chart...")
    subprocess.run(
        [sys.executable, "generate_chart.py"],
        check=True
    )

    # Step 3: Gemini Vision -- chart analysis
    chart_path = "data/chart.png"
    print("\nAnalysing chart with Gemini Vision...\n")
    chart_analysis = analyze_chart_with_gemini(ticker, chart_path)

    # Step 4: Prepare time filters for Coral queries
    now_unix = int(datetime.now().timestamp())
    ago_unix = int((datetime.now() - timedelta(days=30)).timestamp())

    print("\nQuerying data sources via Coral SQL...\n")

    # Step 5: Run all Coral queries (unchanged)
    results = {}

    results["price_history"] = run_coral_sql(f"""
        SELECT date, open, close, volume, week_52_high, week_52_low
        FROM stock_prices.daily
        WHERE ticker = '{ticker}'
        ORDER BY date DESC LIMIT 10
    """, "Price history (last 10 days)")

    results["price_stats"] = run_coral_sql(f"""
        SELECT
          MAX(close)  AS recent_high,
          MIN(close)  AS recent_low,
          AVG(volume) AS avg_volume,
          company_name,
          sector,
          pe_ratio,
          market_cap
        FROM stock_prices.daily
        WHERE ticker = '{ticker}'
        GROUP BY company_name, sector, pe_ratio, market_cap
        LIMIT 1
    """, "Price statistics + company info")

    results["news"] = run_coral_sql(f"""
        SELECT headline, summary, datetime, source
        FROM finnhub.news
        WHERE symbol = '{ticker}'
          AND datetime >= {ago_unix}
          AND datetime <= {now_unix}
        ORDER BY datetime DESC LIMIT 10
    """, "Recent news (Finnhub)")

    results["analyst_ratings"] = run_coral_sql(f"""
        SELECT symbol, buy, "strongBuy", sell, "strongSell", hold, period
        FROM finnhub.analyst_ratings
        WHERE symbol = '{ticker}'
        LIMIT 5
    """, "Analyst ratings (Finnhub)")

    results["insider_trades"] = run_coral_sql(f"""
        SELECT symbol, name, share, change, "transactionDate", "transactionCode", "transactionPrice"
        FROM finnhub.insider_trades
        WHERE symbol = '{ticker}'
        ORDER BY "transactionDate" DESC LIMIT 10
    """, "Insider trades (Finnhub)")

    # Step 5b: SEC 8-K filings via direct API (Coral doesn't support nested JSON extraction)
    # Extract company name from price stats if available
    import re
    company_match = re.search(r'company_name\s*\|\s*(\S[^\|]+)', results.get("price_stats", ""))
    company_name_for_edgar = company_match.group(1).strip() if company_match else ticker
    results["sec_filings"] = fetch_sec_filings(company_name_for_edgar, ticker)

    # Step 6: Build Groq prompt combining chart analysis + SQL data
    sql_block = "\n\n".join([
        f"### {label.upper().replace('_', ' ')}\n{data}"
        for label, data in results.items()
        if data and "query failed" not in data and "timed out" not in data
    ])

    if not sql_block.strip():
        print("\nERROR: All Coral queries failed. Check that sources are registered.")
        print("Run: coral source list")
        sys.exit(1)

    groq_prompt = f"""You are a senior financial analyst. A user wants to understand why {ticker} stock is moving.

You have two sources of information:

### CHART ANALYSIS
{chart_analysis}

### FUNDAMENTAL DATA (from live SQL queries via Coral)
{sql_block}

Based on all of this data, write a clear fundamental analysis covering:
1. **Recent price action** -- What has the stock done? How does recent volume compare to average?
2. **Key news triggers** -- What headlines or events might explain the move?
3. **Analyst sentiment** -- Are analysts broadly bullish, bearish, or neutral right now?
4. **Insider activity** -- Are insiders buying or selling? What does it signal?
5. **SEC FILINGS** -- List any recent 8-K major event filings and what they signal about the company.
6. **Overall verdict** -- In 1-2 sentences, why is this stock most likely moving?

Be specific: reference actual numbers and dates from the data.
If the data is inconclusive on any point, say so honestly.
Keep the total response under 500 words."""

    # Step 7: Call Groq
    print("\nGroq is generating the fundamental analysis...\n")
    groq_client = Groq(api_key=GROQ_API_KEY)

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": groq_prompt}],
            max_tokens=1024,
        )
        fundamental_analysis = completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"ERROR: Groq API call failed: {e}")
        sys.exit(1)

    # Step 8: Print final output with two clear sections
    print(f"\n{'='*60}")
    print(f"  Analysis for {ticker}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    print("Chart Analysis (from Gemini)")
    print("-" * 60)
    print(chart_analysis)

    print(f"\n{'='*60}\n")

    print("Fundamental Analysis (from Groq)")
    print("-" * 60)
    print(fundamental_analysis)

    print(f"\n{'='*60}")
    print(f"  Chart saved to: {chart_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py <TICKER>")
        print("Examples:")
        print("  python analyze.py NVDA")
        print("  python analyze.py AAPL")
        print("  python analyze.py TSLA")
        sys.exit(1)

    check_env()
    fetch_and_analyze(sys.argv[1])