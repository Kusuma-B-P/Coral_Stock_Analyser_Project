#!/usr/bin/env python3
"""
Stock Move Analyzer — Streamlit Frontend
Supports: US Stocks, Crypto, Commodities
Run with: streamlit run app.py
"""
import streamlit as st
import subprocess
import sys
import os
import re
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Stock Move Analyzer", page_icon="📈", layout="wide")

st.markdown("""
<style>
    .main-title {
        font-size: 2.4rem; font-weight: 700;
        background: linear-gradient(90deg, #00d4ff, #7b2ff7);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .subtitle { color: #888; font-size: 1rem; margin-top: 0; margin-bottom: 2rem; }
    .section-header {
        font-size: 1.1rem; font-weight: 600; color: #00d4ff;
        border-bottom: 1px solid #333; padding-bottom: 4px; margin-bottom: 12px;
    }
    .analysis-box {
        background: #0e1117; border: 1px solid #2a2a3a;
        border-radius: 10px; padding: 1.2rem 1.5rem;
        line-height: 1.7; color: #ffffff;
    }
    .stButton > button {
        background: linear-gradient(90deg, #00d4ff, #7b2ff7);
        color: white; border: none; border-radius: 8px;
        padding: 0.5rem 2rem; font-size: 1rem; font-weight: 600; width: 100%;
    }
    .stButton > button:hover { opacity: 0.9; }
</style>
""", unsafe_allow_html=True)

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))

ASSET_TYPES = {
    "🏢 US Stock (NYSE / NASDAQ)": "stock",
    "₿ Crypto (Bitcoin, Ethereum...)": "crypto",
    "🥇 Commodity (Gold, Oil, Silver...)": "commodity",
}
CRYPTO_QUICK = {"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
                "SOL": "solana", "XRP": "ripple", "ADA": "cardano"}
COMMODITY_TICKERS = {
    "GC=F": "Gold", "SI=F": "Silver", "CL=F": "Crude Oil",
    "NG=F": "Natural Gas", "HG=F": "Copper", "PL=F": "Platinum",
    "ZW=F": "Wheat", "ZC=F": "Corn",
}
STOCK_QUICK = ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN", "META", "GOOGL", "AMD", "NFLX"]

# ── Helper functions ───────────────────────────────────────────────────────────
def run_coral_sql(query: str) -> str:
    # Use ./coral on Linux (Render), coral on Windows (local)
    coral_cmd = "./coral" if os.path.exists("./coral") else "coral"
    try:
        result = subprocess.run(
            [coral_cmd, "sql", query.strip()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=30,
            env={**os.environ, "FINNHUB_API_KEY": FINNHUB_API_KEY},
            cwd=BASE_DIR,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode != 0:
            return f"(query failed: {stderr.strip()[:200]})"
        return stdout.strip() or "(no results)"
    except subprocess.TimeoutExpired:
        return "(query timed out)"
    except FileNotFoundError:
        return "(coral not found)"


def _check_coral() -> bool:
    coral_cmd = "./coral" if os.path.exists(os.path.join(BASE_DIR, "coral")) else "coral"
    try:
        r = subprocess.run([coral_cmd, "--version"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, cwd=BASE_DIR)
        return r.returncode == 0
    except Exception:
        return False

CORAL_AVAILABLE = _check_coral()


# ── Direct API fallbacks (used when Coral is not available on cloud) ───────────
def _finnhub_news(ticker: str) -> list:
    try:
        r = requests.get("https://finnhub.io/api/v1/company-news",
                         params={"symbol": ticker, "from": "1970-01-01",
                                 "to": "2099-12-31", "token": FINNHUB_API_KEY}, timeout=15)
        return r.json()[:10] if r.ok else []
    except Exception:
        return []

def _finnhub_ratings(ticker: str) -> list:
    try:
        r = requests.get("https://finnhub.io/api/v1/stock/recommendation",
                         params={"symbol": ticker, "token": FINNHUB_API_KEY}, timeout=15)
        return r.json()[:5] if r.ok else []
    except Exception:
        return []

def _finnhub_insider(ticker: str) -> list:
    try:
        r = requests.get("https://finnhub.io/api/v1/stock/insider-transactions",
                         params={"symbol": ticker, "token": FINNHUB_API_KEY}, timeout=15)
        return r.json().get("data", [])[:10] if r.ok else []
    except Exception:
        return []

def _yfinance_prices(ticker: str) -> list:
    try:
        import yfinance as yf
        df = yf.download(ticker, period="1mo", interval="1d", progress=False)
        if df.empty:
            return []
        df = df.reset_index()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        if "index" in df.columns and "Date" not in df.columns:
            df = df.rename(columns={"index": "Date"})
        rows = []
        for _, row in df.iterrows():
            rows.append({"date": str(row["Date"])[:10],
                         "open": round(float(row["Open"]), 2),
                         "close": round(float(row["Close"]), 2),
                         "volume": int(row["Volume"])})
        return rows[-10:][::-1]
    except Exception:
        return []


def fetch_crypto_history(coin_id: str, days: int = 30) -> list:
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        r = requests.get(url, params={"vs_currency": "usd", "days": days, "interval": "daily"}, timeout=15)
        r.raise_for_status()
        prices = r.json().get("prices", [])
        return [{"date": datetime.fromtimestamp(p[0]/1000).strftime("%Y-%m-%d"),
                 "price": round(p[1], 2)} for p in prices]
    except Exception:
        return []


def fetch_sec_filings(company_name: str) -> list:
    try:
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {"forms": "8-K", "entity": company_name,
                  "dateRange": "custom",
                  "startdt": (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"),
                  "enddt": datetime.now().strftime("%Y-%m-%d")}
        r = requests.get(url, params=params,
                         headers={"User-Agent": "StockAnalyzer contact@example.com"}, timeout=15)
        r.raise_for_status()
        rows = []
        for h in r.json().get("hits", {}).get("hits", [])[:8]:
            src = h.get("_source", {})
            rows.append({"date": src.get("file_date", ""),
                         "form": src.get("form_type") or src.get("form", ""),
                         "items": ", ".join(src.get("items", [])),
                         "entity": (src.get("display_names") or [""])[0]})
        return rows
    except Exception:
        return []


def analyze_chart_with_groq(label: str, price_data: str) -> str:
    prompt = f"""You are a technical analyst. Analyze the 30-day daily price data for {label}.
PRICE DATA: {price_data}
Describe: 1. Trend 2. Patterns 3. MA10/MA20 4. Volume 5. Support/Resistance. Keep under 200 words."""
    try:
        return call_groq(prompt)
    except Exception as e:
        return f"(chart analysis unavailable: {e})"


def analyze_chart_with_gemini(label: str, chart_path: str) -> str:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        with open(chart_path, "rb") as f:
            image_data = f.read()
        prompt = (f"This is a price chart for {label}. "
                  "Describe the trend, patterns, volume behaviour, and what moving averages suggest.")
        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[types.Part.from_bytes(data=image_data, mime_type="image/png"), prompt],
        )
        return response.text.strip()
    except Exception as e:
        return f"(chart analysis unavailable: {e})"


def get_chart_analysis(label: str, chart_path: str, price_data: str) -> tuple:
    gemini_result = analyze_chart_with_gemini(label, chart_path)
    if "unavailable" in gemini_result:
        return call_groq(f"Analyze price data for {label}: {price_data[:500]}. Describe trend, patterns, key levels. Under 200 words."), "groq"
    return gemini_result, "gemini"


def call_groq(prompt: str) -> str:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    return completion.choices[0].message.content.strip()


def parse_table(raw: str) -> list:
    lines = [l for l in raw.splitlines() if l.strip() and not l.startswith("+")]
    if len(lines) < 2:
        return []
    def split_row(line):
        return [p.strip() for p in line.split("|")[1:-1]]
    headers = split_row(lines[0])
    rows = []
    for line in lines[1:]:
        vals = split_row(line)
        if len(vals) == len(headers):
            rows.append(dict(zip(headers, vals)))
    return rows

SEC_ITEM_DESC = {
    "1.01": "📝 New Agreement — Company signed a major new contract",
    "1.02": "❌ Agreement Terminated — An important contract was ended",
    "1.03": "⚖️ Bankruptcy — Company filed for or emerged from bankruptcy",
    "2.01": "🏢 Major Asset Deal — Company bought or sold a significant asset",
    "2.02": "💰 Earnings Results — Company released its financial results",
    "2.03": "💳 New Debt — Company took on a new loan",
    "2.04": "⚠️ Debt Default — Company missed a payment or defaulted",
    "2.05": "💸 Cost Cuts — Company announced layoffs or cost reduction",
    "3.01": "📋 Stock Delisted — Stock removed from a stock exchange",
    "3.02": "📊 Stock Reduced — Company reduced shares available",
    "4.01": "🔄 Auditor Changed — Company switched its auditing firm",
    "5.01": "🏛️ Board Changes — Changes to the board of directors",
    "5.02": "👔 Executive Change — CEO/CFO hired, fired, or resigned",
    "5.03": "📜 Company Rules Changed — Changes to company charter",
    "5.04": "🗳️ Shareholder Vote — Results of a shareholder vote",
    "5.07": "🗳️ Annual Meeting Results — Results from annual shareholder meeting",
    "7.01": "📢 Press Release — Company issued a public announcement",
    "8.01": "📌 Other Major Event — Significant event occurred",
    "9.01": "📎 Financial Documents — Financial statements attached",
}

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">📈 Stock Move Analyzer</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">AI-powered analysis — US Stocks · Crypto · Commodities</p>', unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 What do you want to analyze?")
    asset_label = st.selectbox("Asset Type", list(ASSET_TYPES.keys()))
    asset_type  = ASSET_TYPES[asset_label]
    ticker_input = ""

    if asset_type == "stock":
        st.info("🇺🇸 **US-listed stocks only (NYSE / NASDAQ)**\n\nEnter the ticker symbol — 1 to 5 capital letters.\n\n**Examples:** `NVDA` → NVIDIA · `AAPL` → Apple · `TSLA` → Tesla\n\n💡 Don't know the ticker? Google **\"company name stock ticker\"**")
        ticker_input = st.text_input("Enter Ticker Symbol", placeholder="e.g. NVDA", max_chars=5)
        ticker_input = ticker_input.upper().strip() if ticker_input else ""
        st.markdown("**⚡ Quick picks**")
        cols = st.columns(3)
        for i, t in enumerate(STOCK_QUICK):
            if cols[i % 3].button(t): ticker_input = t

    elif asset_type == "crypto":
        st.info("₿ **Cryptocurrency**\n\nEnter the coin symbol.\n\n**Examples:** `BTC` · `ETH` · `SOL` · `BNB` · `XRP`\n\nData from CoinGecko via Coral SQL.\n\n⚠️ No news, insider trades, or SEC filings for crypto.")
        ticker_input = st.text_input("Enter Coin Symbol", placeholder="e.g. BTC, ETH", max_chars=10)
        ticker_input = ticker_input.upper().strip() if ticker_input else ""
        st.markdown("**⚡ Quick picks**")
        cols = st.columns(3)
        for i, sym in enumerate(CRYPTO_QUICK.keys()):
            if cols[i % 3].button(sym): ticker_input = sym

    elif asset_type == "commodity":
        st.info("🥇 **Commodities**\n\nSelect from the list.\n\n**Available:** Gold · Silver · Crude Oil · Natural Gas · Copper · Platinum\n\n⚠️ No news, insider trades, or SEC filings for commodities.")
        commodity_options = {v: k for k, v in COMMODITY_TICKERS.items()}
        selected = st.selectbox("Select Commodity", list(commodity_options.keys()))
        ticker_input = commodity_options[selected]

    st.divider()
    run_btn = st.button("🚀 Run Analysis", disabled=not ticker_input)
    st.divider()
    st.markdown("**Data Sources**")
    st.markdown("- 🪸 **Coral** — SQL layer over live APIs")
    st.markdown("- 📊 yfinance — price data (stocks & commodities)")
    st.markdown("- 🦎 CoinGecko — crypto prices (via Coral SQL)")
    st.markdown("- 🤖 Gemini Vision — chart AI (falls back to Groq)")
    st.markdown("- 🦙 Groq llama-3.3-70b — analysis & chart fallback")
    if asset_type == "stock":
        st.markdown("- 📰 Finnhub — news & ratings (via Coral SQL)")
        st.markdown("- 🏛️ SEC EDGAR — 8-K filings (via Coral SQL)")

# ── Main content ───────────────────────────────────────────────────────────────
if not ticker_input:
    st.info("👈 Select an asset type and enter a symbol in the sidebar, then click **Run Analysis**.")
    st.markdown("### Supported Assets")
    c1, c2, c3 = st.columns(3)
    c1.success("**🏢 US Stocks**\nFull analysis: prices, news, ratings, insider trades, SEC filings")
    c2.info("**₿ Crypto**\nBitcoin, Ethereum & 10,000+ coins via CoinGecko. Price chart + AI analysis.")
    c3.warning("**🥇 Commodities**\nGold, Silver, Oil, Gas, Copper. Price chart + AI analysis.")
    st.stop()

if run_btn:
    display_name = ticker_input
    if asset_type == "commodity":
        display_name = COMMODITY_TICKERS.get(ticker_input, ticker_input)
    elif asset_type == "crypto":
        display_name = f"{ticker_input} (Crypto)"
    st.markdown(f"## Analysis for **{display_name}**  `{datetime.now().strftime('%Y-%m-%d %H:%M')}`")
    chart_path = os.path.join(BASE_DIR, "data", "chart.png")

    # ══════════════════════════════════════════════════════════════════════════
    # CRYPTO FLOW
    # ══════════════════════════════════════════════════════════════════════════
    if asset_type == "crypto":
        coin_id = CRYPTO_QUICK.get(ticker_input, ticker_input.lower())

        with st.status("🪸 Fetching crypto data via Coral SQL (CoinGecko)...", expanded=False) as status:
            raw_crypto = run_coral_sql(f"""
                SELECT name, symbol, current_price, market_cap, market_cap_rank,
                       total_volume, high_24h, low_24h, ath, ath_change_percentage,
                       price_change_24h, price_change_percentage_24h,
                       circulating_supply, max_supply, last_updated
                FROM coingecko.markets WHERE id = '{coin_id}' LIMIT 1
            """)
            crypto_rows = parse_table(raw_crypto)
            if not crypto_rows:
                # Fallback: fetch directly from CoinGecko API
                try:
                    r = requests.get(
                        f"https://api.coingecko.com/api/v3/coins/markets",
                        params={"vs_currency": "usd", "ids": coin_id,
                                "order": "market_cap_desc", "per_page": 1, "page": 1},
                        timeout=15)
                    data = r.json()
                    if data:
                        d = data[0]
                        crypto_rows = [{"name": d.get("name",""), "symbol": d.get("symbol",""),
                            "current_price": str(d.get("current_price","")),
                            "market_cap": str(d.get("market_cap","")),
                            "market_cap_rank": str(d.get("market_cap_rank","")),
                            "total_volume": str(d.get("total_volume","")),
                            "high_24h": str(d.get("high_24h","")),
                            "low_24h": str(d.get("low_24h","")),
                            "ath": str(d.get("ath","")),
                            "ath_change_percentage": str(d.get("ath_change_percentage","")),
                            "price_change_24h": str(d.get("price_change_24h","")),
                            "price_change_percentage_24h": str(d.get("price_change_percentage_24h","")),
                            "circulating_supply": str(d.get("circulating_supply","")),
                            "max_supply": str(d.get("max_supply",""))}]
                        raw_crypto = str(data[0])
                except Exception:
                    pass
            if not crypto_rows:
                status.update(label=f"❌ Coin not found: {ticker_input}", state="error")
                st.error(f"Could not find '{ticker_input}'. Try full coin ID e.g. 'bitcoin'.")
                st.stop()
            c = crypto_rows[0]
            status.update(label="✅ Crypto data fetched via Coral SQL", state="complete")

        with st.status("📥 Fetching 30-day price history...", expanded=False) as status:
            history = fetch_crypto_history(coin_id)
            status.update(label="✅ Price history fetched", state="complete")

        with st.status("📊 Generating price chart...", expanded=False) as status:
            try:
                import matplotlib; matplotlib.use("Agg")
                import matplotlib.pyplot as plt
                import matplotlib.dates as mdates
                dates  = [datetime.strptime(h["date"], "%Y-%m-%d") for h in history]
                prices = [h["price"] for h in history]
                fig, ax = plt.subplots(figsize=(14, 5))
                ax.plot(dates, prices, color="#00d4ff", linewidth=2)
                ax.fill_between(dates, prices, alpha=0.1, color="#00d4ff")
                ax.set_title(f"{ticker_input} — 30 Day Price (USD)", color="white", fontsize=14)
                ax.set_facecolor("#0e1117"); fig.patch.set_facecolor("#0e1117")
                ax.tick_params(colors="white")
                for spine in ax.spines.values(): spine.set_edgecolor("#333")
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
                plt.xticks(rotation=45)
                os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
                plt.tight_layout()
                plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor="#0e1117")
                plt.close()
                status.update(label="✅ Chart generated", state="complete")
            except Exception as e:
                status.update(label=f"⚠️ Chart failed: {e}", state="error")

        with st.status("🤖 Analysing chart...", expanded=False) as status:
            history_text = "\n".join([f"{h['date']}: ${h['price']}" for h in history])
            chart_analysis, chart_source = get_chart_analysis(f"{ticker_input} crypto", chart_path, history_text)
            source_label = "Gemini Vision" if chart_source == "gemini" else "Groq llama-3.3-70b"
            status.update(label=f"✅ Chart analysed by {source_label}", state="complete")

        price_usd  = c.get("current_price", "N/A")
        change_24h = c.get("price_change_percentage_24h", "N/A")
        market_cap = c.get("market_cap", "N/A")
        volume_24h = c.get("total_volume", "N/A")
        high_24h   = c.get("high_24h", "N/A")
        low_24h    = c.get("low_24h", "N/A")
        ath        = c.get("ath", "N/A")
        rank       = c.get("market_cap_rank", "N/A")
        name       = c.get("name", ticker_input)
        circ_supply= c.get("circulating_supply", "N/A")
        max_supply = c.get("max_supply", "N/A")

        groq_prompt = f"""You are a crypto analyst. Analyze why {name} ({ticker_input}) is moving.
CHART ANALYSIS: {chart_analysis}
MARKET DATA (CoinGecko via Coral SQL): Price=${price_usd}, 24h Change={change_24h}%, High=${high_24h}, Low=${low_24h}, MarketCap=${market_cap}, Volume=${volume_24h}, ATH=${ath}, Rank=#{rank}
Write analysis covering: 1.Price action 2.Market sentiment 3.Volume 4.Key levels 5.Overall verdict. Under 400 words."""

        with st.status("🦙 Groq generating analysis...", expanded=False) as status:
            try:
                fundamental_analysis = call_groq(groq_prompt)
                status.update(label="✅ Analysis complete", state="complete")
            except Exception as e:
                status.update(label="❌ Groq failed", state="error")
                st.error(str(e)); st.stop()

        st.divider()
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown('<p class="section-header">📊 30-Day Price Chart</p>', unsafe_allow_html=True)
            if os.path.exists(chart_path): st.image(chart_path, use_container_width=True)
        with right:
            st.markdown('<p class="section-header">📋 Market Data (via Coral SQL)</p>', unsafe_allow_html=True)
            m1, m2 = st.columns(2)
            m1.metric("Current Price", f"${float(price_usd):,}" if price_usd != "N/A" else "N/A")
            m2.metric("24h Change", f"{float(change_24h):.2f}%" if change_24h != "N/A" else "N/A")
            m3, m4 = st.columns(2)
            m3.metric("24h High", f"${float(high_24h):,}" if high_24h != "N/A" else "N/A")
            m4.metric("24h Low",  f"${float(low_24h):,}" if low_24h != "N/A" else "N/A")
            m5, m6 = st.columns(2)
            m5.metric("Market Cap Rank", f"#{rank}")
            m6.metric("All Time High", f"${float(ath):,}" if ath != "N/A" else "N/A")
            try:
                st.markdown(f"**Market Cap:** ${float(market_cap)/1e9:.2f}B")
                st.markdown(f"**24h Volume:** ${float(volume_24h)/1e9:.2f}B")
                st.markdown(f"**Circulating Supply:** {float(circ_supply):,.0f}")
            except Exception: pass

        st.divider()
        st.markdown(f'<p class="section-header">🤖 Chart Analysis — {source_label}</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="analysis-box">{chart_analysis}</div>', unsafe_allow_html=True)
        st.divider()
        st.markdown('<p class="section-header">🦙 AI Analysis — Groq</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="analysis-box">{fundamental_analysis}</div>', unsafe_allow_html=True)
        if history:
            st.divider()
            st.markdown('<p class="section-header">📂 Raw Data (Coral SQL — CoinGecko)</p>', unsafe_allow_html=True)
            tab_price, tab_raw = st.tabs(["📈 Price History (30d)", "🪸 Coral SQL Output"])
            with tab_price: st.dataframe(history[-10:][::-1], use_container_width=True)
            with tab_raw: st.code(raw_crypto)

    # ══════════════════════════════════════════════════════════════════════════
    # COMMODITY FLOW
    # ══════════════════════════════════════════════════════════════════════════
    elif asset_type == "commodity":
        commodity_name = COMMODITY_TICKERS.get(ticker_input, ticker_input)

        with st.status(f"📥 Fetching {commodity_name} price data...", expanded=False) as status:
            try:
                subprocess.run([sys.executable, os.path.join(BASE_DIR, "fetch_prices.py"), ticker_input],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=BASE_DIR)
                status.update(label="✅ Price data fetched", state="complete")
            except subprocess.CalledProcessError as e:
                status.update(label="❌ Failed to fetch price data", state="error")
                st.error(f"Error: {(e.stderr or b'').decode()}"); st.stop()

        with st.status("📊 Generating candlestick chart...", expanded=False) as status:
            try:
                subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_chart.py")],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=BASE_DIR)
                status.update(label="✅ Chart generated", state="complete")
            except Exception:
                status.update(label="⚠️ Chart generation failed", state="error")

        with st.status("🪸 Fetching price stats via Coral SQL...", expanded=False) as status:
            raw_price_history = run_coral_sql(f"""
                SELECT date, open, close, volume, week_52_high, week_52_low
                FROM stock_prices.daily WHERE ticker = '{ticker_input}'
                ORDER BY date DESC LIMIT 10
            """)
            raw_price_stats = run_coral_sql(f"""
                SELECT MAX(close) AS recent_high, MIN(close) AS recent_low,
                       AVG(volume) AS avg_volume, company_name
                FROM stock_prices.daily WHERE ticker = '{ticker_input}'
                GROUP BY company_name LIMIT 1
            """)
            status.update(label="✅ Price stats fetched via Coral SQL", state="complete")

        with st.status("🤖 Analysing chart...", expanded=False) as status:
            chart_analysis, chart_source = get_chart_analysis(commodity_name, chart_path, raw_price_history)
            source_label = "Gemini Vision" if chart_source == "gemini" else "Groq llama-3.3-70b"
            status.update(label=f"✅ Chart analysed by {source_label}", state="complete")

        groq_prompt = f"""You are a commodity analyst. Analyze why {commodity_name} is moving.
CHART ANALYSIS: {chart_analysis}
PRICE DATA: {raw_price_history}
STATS: {raw_price_stats}
Write analysis covering: 1.Price action 2.Trend 3.Volume 4.Key levels 5.Overall verdict. Under 400 words."""

        with st.status("🦙 Groq generating analysis...", expanded=False) as status:
            try:
                fundamental_analysis = call_groq(groq_prompt)
                status.update(label="✅ Analysis complete", state="complete")
            except Exception as e:
                status.update(label="❌ Groq failed", state="error")
                st.error(str(e)); st.stop()

        st.divider()
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown('<p class="section-header">📊 Candlestick Chart (MA10 · MA20)</p>', unsafe_allow_html=True)
            if os.path.exists(chart_path): st.image(chart_path, use_container_width=True)
        with right:
            st.markdown('<p class="section-header">📋 Price Stats (via Coral SQL)</p>', unsafe_allow_html=True)
            stats_rows = parse_table(raw_price_stats)
            if stats_rows:
                s = stats_rows[0]
                m1, m2 = st.columns(2)
                m1.metric("Recent High", f"${float(s.get('recent_high', 0)):.2f}")
                m2.metric("Recent Low",  f"${float(s.get('recent_low', 0)):.2f}")
                try: st.metric("Avg Daily Volume", f"{float(s.get('avg_volume', 0)):,.0f}")
                except: pass
            st.info("ℹ️ News, insider trades, and SEC filings are not available for commodities.")

        st.divider()
        st.markdown(f'<p class="section-header">🤖 Chart Analysis — {source_label}</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="analysis-box">{chart_analysis}</div>', unsafe_allow_html=True)
        st.divider()
        st.markdown('<p class="section-header">🦙 AI Analysis — Groq</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="analysis-box">{fundamental_analysis}</div>', unsafe_allow_html=True)
        st.divider()
        st.markdown('<p class="section-header">📂 Price History (Coral SQL)</p>', unsafe_allow_html=True)
        price_rows = parse_table(raw_price_history)
        if price_rows: st.dataframe(price_rows, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # US STOCK FLOW
    # ══════════════════════════════════════════════════════════════════════════
    else:
        ticker = ticker_input

        with st.status("📥 Fetching price data from yfinance...", expanded=False) as status:
            try:
                subprocess.run([sys.executable, os.path.join(BASE_DIR, "fetch_prices.py"), ticker],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=BASE_DIR)
                status.update(label="✅ Price data fetched", state="complete")
            except subprocess.CalledProcessError as e:
                status.update(label="❌ Failed to fetch price data", state="error")
                st.error(f"yfinance error: {(e.stderr or b'').decode()}"); st.stop()

        with st.status("📊 Generating candlestick chart...", expanded=False) as status:
            try:
                subprocess.run([sys.executable, os.path.join(BASE_DIR, "generate_chart.py")],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=BASE_DIR)
                status.update(label="✅ Chart generated", state="complete")
            except Exception:
                status.update(label="❌ Chart generation failed", state="error")

        with st.status("🪸 Querying live data via Coral SQL...", expanded=False) as status:
            now_unix = int(datetime.now().timestamp())
            ago_unix = int((datetime.now() - timedelta(days=30)).timestamp())

            if CORAL_AVAILABLE:
                raw_price_history = run_coral_sql(f"""
                    SELECT date, open, close, volume, week_52_high, week_52_low
                    FROM stock_prices.daily WHERE ticker = '{ticker}' ORDER BY date DESC LIMIT 10
                """)
                raw_price_stats = run_coral_sql(f"""
                    SELECT MAX(close) AS recent_high, MIN(close) AS recent_low,
                           AVG(volume) AS avg_volume, company_name, sector, pe_ratio, market_cap
                    FROM stock_prices.daily WHERE ticker = '{ticker}'
                    GROUP BY company_name, sector, pe_ratio, market_cap LIMIT 1
                """)
                raw_news = run_coral_sql(f"""
                    SELECT headline, summary, datetime, source, url FROM finnhub.news
                    WHERE symbol = '{ticker}' AND datetime >= {ago_unix} AND datetime <= {now_unix}
                    ORDER BY datetime DESC LIMIT 10
                """)
                raw_ratings = run_coral_sql(f"""
                    SELECT symbol, buy, "strongBuy", sell, "strongSell", hold, period
                    FROM finnhub.analyst_ratings WHERE symbol = '{ticker}' LIMIT 5
                """)
                raw_insider = run_coral_sql(f"""
                    SELECT symbol, name, title, share, change, "transactionDate", "transactionCode", "transactionPrice"
                    FROM finnhub.insider_trades WHERE symbol = '{ticker}'
                    ORDER BY "transactionDate" DESC LIMIT 10
                """)
                # for tabs
                _news_direct = None; _ratings_direct = None
                _insider_direct = None; _prices_direct = None
            else:
                # Direct API fallback — same data, no Coral CLI needed
                _prices_direct    = _yfinance_prices(ticker)
                _news_direct      = _finnhub_news(ticker)
                _ratings_direct   = _finnhub_ratings(ticker)
                _insider_direct   = _finnhub_insider(ticker)
                raw_price_history = "\n".join([f"{r['date']} | {r['open']} | {r['close']} | {r['volume']}" for r in _prices_direct]) or "(no data)"
                raw_price_stats   = f"price data for {ticker}"
                raw_news          = "\n".join([f"{n.get('headline','')} | {n.get('source','')}" for n in _news_direct]) or "(no news)"
                raw_ratings       = "\n".join([f"buy:{r.get('buy',0)} strongBuy:{r.get('strongBuy',0)} sell:{r.get('sell',0)} hold:{r.get('hold',0)}" for r in _ratings_direct]) or "(no ratings)"
                raw_insider       = "\n".join([f"{r.get('name','')} | {r.get('transactionCode','')} | {r.get('change','')} | {r.get('transactionDate','')}" for r in _insider_direct]) or "(no trades)"

            status.update(label="✅ Live data fetched via Coral SQL", state="complete")

        with st.status("🏛️ Fetching SEC 8-K filings...", expanded=False) as status:
            company_match = re.search(r'company_name\s*\|\s*(\S[^\|]+)', raw_price_stats)
            company_name  = company_match.group(1).strip() if company_match else ticker
            sec_rows = fetch_sec_filings(company_name)
            status.update(label=f"✅ {len(sec_rows)} SEC filings found", state="complete")

        with st.status("🤖 Analysing chart...", expanded=False) as status:
            chart_analysis, chart_source = get_chart_analysis(ticker, chart_path, raw_price_history)
            source_label = "Gemini Vision" if chart_source == "gemini" else "Groq llama-3.3-70b"
            status.update(label=f"✅ Chart analysed by {source_label}", state="complete")

        sec_text = "\n".join([f"{r['date']} | {r['form']} | {r['items']} | {r['entity']}" for r in sec_rows]) or "(no recent 8-K filings found)"
        sql_block = f"PRICE HISTORY:\n{raw_price_history}\nPRICE STATS:\n{raw_price_stats}\nNEWS:\n{raw_news}\nRATINGS:\n{raw_ratings}\nINSIDER TRADES:\n{raw_insider}\nSEC FILINGS:\n{sec_text}"

        groq_prompt = f"""You are a senior financial analyst. Explain why {ticker} stock is moving.
CHART ANALYSIS: {chart_analysis}
FUNDAMENTAL DATA: {sql_block}
Write analysis covering: 1.Recent price action 2.Key news triggers 3.Analyst sentiment 4.Insider activity 5.SEC FILINGS 6.Overall verdict. Reference actual numbers. Under 500 words."""

        with st.status("🦙 Groq generating fundamental analysis...", expanded=False) as status:
            try:
                fundamental_analysis = call_groq(groq_prompt)
                status.update(label="✅ Analysis complete", state="complete")
            except Exception as e:
                status.update(label="❌ Groq failed", state="error")
                st.error(str(e)); st.stop()

        st.divider()
        left, right = st.columns([3, 2], gap="large")
        with left:
            st.markdown('<p class="section-header">📊 Candlestick Chart (MA10 · MA20)</p>', unsafe_allow_html=True)
            if os.path.exists(chart_path): st.image(chart_path, use_container_width=True)
            else: st.warning("Chart not available.")
        with right:
            st.markdown('<p class="section-header">📋 Price Stats (via Coral SQL)</p>', unsafe_allow_html=True)
            stats_rows = parse_table(raw_price_stats)
            if stats_rows:
                s = stats_rows[0]
                m1, m2 = st.columns(2)
                m1.metric("Recent High", f"${float(s.get('recent_high', 0)):.2f}")
                m2.metric("Recent Low",  f"${float(s.get('recent_low', 0)):.2f}")
                m3, m4 = st.columns(2)
                try: m3.metric("Avg Volume", f"{float(s.get('avg_volume', 0))/1e6:.1f}M")
                except: pass
                pe = s.get('pe_ratio', 'N/A')
                m4.metric("P/E Ratio", pe if pe and pe != 'None' else "N/A")
                st.markdown(f"**Company:** {s.get('company_name', ticker)}")
                st.markdown(f"**Sector:** {s.get('sector', 'N/A')}")
                try: st.markdown(f"**Market Cap:** ${float(s.get('market_cap','0'))/1e9:.1f}B")
                except: pass
            st.divider()
            st.markdown('<p class="section-header">🏦 Analyst Ratings (via Coral SQL)</p>', unsafe_allow_html=True)
            if CORAL_AVAILABLE:
                rating_rows = parse_table(raw_ratings)
            else:
                rating_rows = _ratings_direct or []
            if rating_rows:
                r = rating_rows[0]
                buy  = int(r.get("buy", 0) or 0) + int(r.get("strongBuy", 0) or 0)
                sell = int(r.get("sell", 0) or 0) + int(r.get("strongSell", 0) or 0)
                hold = int(r.get("hold", 0) or 0)
                total = buy + sell + hold or 1
                c1, c2, c3 = st.columns(3)
                c1.metric("🟢 Buy", buy); c2.metric("🔴 Sell", sell); c3.metric("🟡 Hold", hold)
                st.progress(int(buy/total*100), text=f"{buy/total*100:.0f}% Bullish")
            else:
                st.info("No ratings data.")

        st.divider()
        st.markdown(f'<p class="section-header">🤖 Chart Analysis — {source_label}</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="analysis-box">{chart_analysis}</div>', unsafe_allow_html=True)
        st.divider()
        st.markdown('<p class="section-header">🦙 Fundamental Analysis — Groq</p>', unsafe_allow_html=True)
        st.markdown(f'<div class="analysis-box">{fundamental_analysis}</div>', unsafe_allow_html=True)
        st.divider()

        st.markdown('<p class="section-header">📂 Raw Data (Coral SQL)</p>', unsafe_allow_html=True)
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Price History", "📰 News", "👤 Insider Trades", "🏛️ SEC Filings", "⭐ Ratings"])

        with tab1:
            if CORAL_AVAILABLE:
                price_rows = parse_table(raw_price_history)
            else:
                price_rows = _prices_direct or []
            if price_rows: st.dataframe(price_rows, use_container_width=True)
            else: st.code(raw_price_history)

        with tab2:
            if CORAL_AVAILABLE:
                news_rows = parse_table(raw_news)
            else:
                news_rows = [{"headline": n.get("headline",""), "summary": n.get("summary",""),
                              "datetime": str(n.get("datetime","")), "source": n.get("source",""),
                              "url": n.get("url","")} for n in (_news_direct or [])]
            if news_rows:
                for n in news_rows:
                    ts = n.get("datetime", "")
                    try: ts = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
                    except: pass
                    headline = n.get("headline", ""); url = n.get("url", ""); source = n.get("source", "")
                    if url:
                        st.markdown(f"**[{headline}]({url})**  \n*{source} · {ts} · [Read full article →]({url})*")
                    else:
                        st.markdown(f"**{headline}**  \n*{source} · {ts}*")
                    if n.get("summary"): st.caption(n["summary"][:200])
                    st.divider()
            else: st.code(raw_news)

        with tab3:
            if CORAL_AVAILABLE:
                insider_rows = parse_table(raw_insider)
            else:
                code_map = {"S": "🔴 Sold", "P": "🟢 Bought", "A": "🎁 Awarded",
                            "F": "💸 Tax Withholding", "M": "🔄 Option Exercise",
                            "G": "🎁 Gift", "D": "🔴 Sold"}
                insider_rows = []
                for r in (_insider_direct or []):
                    try: cf = f"{abs(int(float(r.get('change',0)))):,}"
                    except: cf = str(r.get("change",""))
                    try: sf = f"{int(float(r.get('share',0))):,}"
                    except: sf = str(r.get("share",""))
                    try: pf = f"${float(r.get('transactionPrice',0)):.2f}"
                    except: pf = str(r.get("transactionPrice",""))
                    insider_rows.append({"name": r.get("name",""),
                        "transactionCode": r.get("transactionCode",""),
                        "change": cf, "share": sf,
                        "transactionPrice": pf,
                        "transactionDate": r.get("transactionDate","")})
            if insider_rows:
                code_map = {"S": "🔴 Sold", "P": "🟢 Bought", "A": "🎁 Awarded",
                            "F": "💸 Tax Withholding", "M": "🔄 Option Exercise",
                            "G": "🎁 Gift", "D": "🔴 Sold"}
                display_rows = []
                for row in insider_rows:
                    try: change_fmt = f"{abs(int(float(row.get('change', 0)))):,}"
                    except: change_fmt = row.get("change", "")
                    try: shares_fmt = f"{int(float(row.get('share', 0))):,}"
                    except: shares_fmt = row.get("share", "")
                    try: price_fmt = f"${float(row.get('transactionPrice', 0)):.2f}"
                    except: price_fmt = row.get("transactionPrice", "")
                    display_rows.append({"Name": row.get("name", ""),
                        "Action": code_map.get(row.get("transactionCode", ""), row.get("transactionCode", "")),
                        "Shares Traded": change_fmt, "Shares Remaining": shares_fmt,
                        "Price per Share": price_fmt, "Date": row.get("transactionDate", "")})
                st.dataframe(display_rows, use_container_width=True)
            else: st.info("No insider trade data available.")

        with tab4:
            if sec_rows:
                for row in sec_rows:
                    items_raw = row.get("items", "")
                    desc = SEC_ITEM_DESC.get(items_raw, f"📌 SEC Filing — Item {items_raw}")
                    col_date, col_form, col_item = st.columns([1, 1, 4])
                    col_date.markdown(f"**📅 {row.get('date','')}**")
                    col_form.markdown(f"`{row.get('form','')}`")
                    col_item.markdown(f"**{desc}**")
                    st.caption(f"🏢 {row.get('entity','')}")
                    st.divider()
            else: st.info("No recent 8-K filings found for this company.")

        with tab5:
            if CORAL_AVAILABLE:
                if rating_rows: st.dataframe(rating_rows, use_container_width=True)
                else: st.code(raw_ratings)
            else:
                if _ratings_direct: st.dataframe(_ratings_direct, use_container_width=True)
                else: st.info("No ratings data available.")

else:
    st.markdown("### How it works")
    c1, c2, c3 = st.columns(3)
    c1.success("**🏢 US Stocks**\nFull analysis: prices, news, analyst ratings, insider trades, SEC filings")
    c2.info("**₿ Crypto**\nBitcoin, Ethereum & 10,000+ coins via CoinGecko. Price chart + AI analysis.")
    c3.warning("**🥇 Commodities**\nGold, Silver, Oil, Gas, Copper. Price chart + AI analysis.")
