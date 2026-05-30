# 📈 Stock Move Analyzer

An AI-powered web app that explains why a stock, cryptocurrency, or commodity is moving — by querying live data from multiple sources through [Coral](https://withcoral.com) SQL, analyzing charts with Gemini Vision, and generating plain-English reports with Groq.

---

## 🏗️ Architecture

![Architecture](stock_move_analyzer_architecture%20(1).svg)

---

## 🛠️ Tech Stack

![Tech Stack](image.png)

---

## What it does

Type any ticker and get a complete AI-written analysis backed by real live data:

- 📊 30-day candlestick chart with MA10 & MA20 (yfinance)
- 📰 Breaking news and analyst ratings (Finnhub via Coral SQL)
- 👤 Insider buy/sell transactions (Finnhub via Coral SQL)
- 🏛️ SEC 8-K major event filings (SEC EDGAR via Coral SQL)
- ₿ Live crypto market data — price, market cap, volume, ATH (CoinGecko via Coral SQL)
- 🥇 Commodity prices — Gold, Silver, Oil, Gas, Copper (yfinance futures)
- 🤖 Chart analysis by Gemini Vision (falls back to Groq if quota exceeded)
- 🦙 Full written analysis by Groq llama-3.3-70b

---

## Supported Asset Classes

| Asset | Example | Full Analysis |
|-------|---------|--------------|
| 🏢 US Stocks (NYSE/NASDAQ) | `NVDA`, `AAPL`, `TSLA` | ✅ Complete |
| ₿ Cryptocurrency | `BTC`, `ETH`, `SOL` | ⚡ Price + AI |
| 🥇 Commodities | Gold, Silver, Oil | ⚡ Price + AI |

---

## Coral SQL Sources (4 registered)

| Source | API | Tables | Used For |
|--------|-----|--------|---------|
| `finnhub.yaml` | Finnhub | `news`, `analyst_ratings`, `insider_trades` | US Stocks |
| `sec_edgar.yaml` | SEC EDGAR (US Govt) | `filings` | US Stocks |
| `stock_prices.yaml` | Local JSONL file | `daily` | Stocks + Commodities |
| `coingecko.yaml` | CoinGecko | `markets` | Crypto |

---

## Quick Start (Windows)

### 1. Get your free API keys
- **Finnhub**: https://finnhub.io (free, instant signup)
- **Groq**: https://console.groq.com (free)
- **Gemini**: https://aistudio.google.com/app/apikey (free)

### 2. Run setup
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

### 3. Register Coral sources
```powershell
coral source add --file sources\finnhub.yaml
coral source add --file sources\sec_edgar.yaml
coral source add --file sources\stock_prices.yaml
coral source add --file sources\coingecko.yaml
```

### 4. Launch the web app
```powershell
.\venv\Scripts\streamlit.exe run app.py
```

Open your browser at **http://localhost:8501**

### 5. Or run CLI analysis
```powershell
.\venv\Scripts\python.exe analyze.py NVDA
.\venv\Scripts\python.exe analyze.py AAPL
.\venv\Scripts\python.exe analyze.py TSLA
```

---

## How it works

```
User selects asset (Stock / Crypto / Commodity)
         |
fetch_prices.py → data/prices.jsonl  (Stocks & Commodities)
CoinGecko API   → via Coral SQL      (Crypto)
         |
generate_chart.py → data/chart.png
         |
Coral SQL Layer:
  ├── finnhub.news
  ├── finnhub.analyst_ratings
  ├── finnhub.insider_trades
  ├── sec_edgar.filings
  ├── stock_prices.daily
  └── coingecko.markets
         |
Gemini Vision → chart analysis (falls back to Groq)
         |
Groq llama-3.3-70b → full written analysis
         |
Streamlit Web UI → displays everything
```

---

## Project Structure

```
├── app.py                  # Streamlit web frontend
├── analyze.py              # CLI pipeline
├── fetch_prices.py         # yfinance price fetcher
├── generate_chart.py       # Candlestick chart generator
├── sources/
│   ├── finnhub.yaml        # Coral source — Finnhub API
│   ├── sec_edgar.yaml      # Coral source — SEC EDGAR
│   ├── stock_prices.yaml   # Coral source — local JSONL
│   └── coingecko.yaml      # Coral source — CoinGecko API
├── data/
│   ├── prices.jsonl        # Generated price data
│   └── chart.png           # Generated chart image
├── .env                    # API keys (not committed)
└── .env.example            # API keys template
```

---

## API Keys Required

| Key | Service | Cost |
|-----|---------|------|
| `FINNHUB_API_KEY` | Finnhub | Free |
| `GEMINI_API_KEY` | Google Gemini | Free (daily limit) |
| `GROQ_API_KEY` | Groq | Free |

CoinGecko and SEC EDGAR require no API key.

---

## Built with

- [Coral](https://withcoral.com) — SQL layer over live APIs
- [Groq](https://groq.com) — llama-3.3-70b-versatile
- [Google Gemini](https://ai.google.dev) — gemini-2.0-flash-lite (Vision)
- [Finnhub](https://finnhub.io) — news, ratings, insider trades
- [CoinGecko](https://coingecko.com) — crypto market data
- [yfinance](https://pypi.org/project/yfinance/) — stock & commodity prices
- [SEC EDGAR](https://efts.sec.gov) — public filings
- [Streamlit](https://streamlit.io) — web UI
- [mplfinance](https://pypi.org/project/mplfinance/) — candlestick charts
