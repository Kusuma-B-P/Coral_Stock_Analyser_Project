# Design: Stock Move Analyzer (Coral + Claude)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        User (Terminal)                       │
│                  python analyze.py NVDA                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       analyze.py                             │
│   1. Load .env keys                                          │
│   2. Run fetch_prices.py <ticker>                            │
│   3. Run 5x coral sql queries                                │
│   4. Assemble data block                                     │
│   5. Call Claude API                                         │
│   6. Print analysis                                          │
└───────┬──────────────────────────────┬───────────────────────┘
        │                              │
        ▼                              ▼
┌───────────────┐            ┌─────────────────────┐
│ fetch_prices  │            │     Coral CLI        │
│   .py         │            │  (coral sql "...")   │
│               │            │                      │
│ yfinance →    │            │  Executes SQL across │
│ data/prices   │            │  registered sources  │
│ .jsonl        │            └──────────┬───────────┘
└───────────────┘                       │
                            ┌───────────┼───────────┐
                            ▼           ▼           ▼
                    ┌──────────┐ ┌──────────┐ ┌──────────┐
                    │ Finnhub  │ │  SEC     │ │  Local   │
                    │   API    │ │  EDGAR   │ │  JSONL   │
                    │ (HTTP)   │ │  API     │ │ (prices) │
                    └──────────┘ └──────────┘ └──────────┘
```

---

## Component Breakdown

### 1. `setup.ps1` — One-click Windows setup
- Downloads Coral binary, adds to PATH
- Runs `pip install` for Python deps
- Prompts for API keys, writes `.env`
- Patches absolute path into `sources/stock_prices.yaml`
- Runs `coral source add` for all three sources

### 2. `sources/finnhub.yaml` — Coral source spec
- Backend: `http`
- Base URL: `https://finnhub.io/api/v1`
- Auth: `HeaderAuth` with `X-Finnhub-Token` from secret input
- Tables:
  - `finnhub.news` → `/company-news`
  - `finnhub.analyst_ratings` → `/stock/recommendation`
  - `finnhub.insider_trades` → `/stock/insider-transactions`

### 3. `sources/sec_edgar.yaml` — Coral source spec
- Backend: `http`
- Base URL: `https://efts.sec.gov`
- Auth: `HeaderAuth` with `User-Agent` (required by SEC, no API key)
- Tables:
  - `sec_edgar.filings` → `/LATEST/search-index`

### 4. `sources/stock_prices.yaml` — Coral source spec
- Backend: `jsonl`
- Source: `file:///absolute/path/to/data/*.jsonl`
- Tables:
  - `stock_prices.daily` — OHLCV + company metadata

### 5. `fetch_prices.py` — Price data fetcher
- Input: ticker symbol (CLI arg)
- Uses `yfinance.download()` for OHLCV
- Uses `yfinance.Ticker.info` for company metadata
- Output: `data/prices.jsonl` (one JSON object per day)

### 6. `analyze.py` — Main agent script
- Loads `.env` via `python-dotenv`
- Calls `fetch_prices.py` as a subprocess
- Runs 5 `coral sql` queries via `subprocess.run(["coral", "sql", query])`
- Builds a prompt with all query results
- Calls `anthropic.Anthropic().messages.create()` with `claude-sonnet-4-20250514`
- Prints the analysis

### 7. `.kiro/mcp.json` — Kiro MCP config
- Registers `coral mcp-stdio` so Kiro's agent can call `sql`, `list_catalog`,
  `describe_table`, and `search_catalog` directly during development

---

## Data Models

### `stock_prices.daily` schema
| Column        | Type    | Description                       |
|---------------|---------|-----------------------------------|
| ticker        | Utf8    | Stock symbol e.g. NVDA            |
| company_name  | Utf8    | Full company name                 |
| sector        | Utf8    | Industry sector                   |
| date          | Utf8    | YYYY-MM-DD                        |
| open          | Float64 | Opening price                     |
| high          | Float64 | Daily high                        |
| low           | Float64 | Daily low                         |
| close         | Float64 | Closing price                     |
| volume        | Int64   | Daily trading volume              |
| market_cap    | Int64   | Market capitalization             |
| pe_ratio      | Float64 | Trailing P/E ratio                |
| week_52_high  | Float64 | 52-week high price                |
| week_52_low   | Float64 | 52-week low price                 |

### `finnhub.news` schema
| Column    | Type    | Description               |
|-----------|---------|---------------------------|
| id        | Int64   | Article ID                |
| headline  | Utf8    | Article headline          |
| summary   | Utf8    | Short summary             |
| datetime  | Int64   | Unix timestamp            |
| symbol    | Utf8    | Ticker symbol             |
| source    | Utf8    | News outlet               |
| url       | Utf8    | Article URL               |

### `finnhub.analyst_ratings` schema
| Column     | Type  | Description             |
|------------|-------|-------------------------|
| symbol     | Utf8  | Ticker symbol           |
| buy        | Int64 | Number of buy ratings   |
| strongBuy  | Int64 | Strong buy ratings      |
| sell       | Int64 | Sell ratings            |
| strongSell | Int64 | Strong sell ratings     |
| hold       | Int64 | Hold ratings            |
| period     | Utf8  | Rating period date      |

### `finnhub.insider_trades` schema
| Column           | Type    | Description                        |
|------------------|---------|------------------------------------|
| name             | Utf8    | Insider name                       |
| share            | Int64   | Shares involved                    |
| change           | Int64   | +buy / -sell                       |
| transactionDate  | Utf8    | Date of transaction                |
| transactionCode  | Utf8    | SEC transaction code               |
| transactionPrice | Float64 | Price per share                    |

---

## Coral SQL Queries (executed in `analyze.py`)

```sql
-- Q1: Recent price history
SELECT date, close, volume, company_name, sector
FROM stock_prices.daily
WHERE ticker = '<TICKER>'
ORDER BY date DESC LIMIT 10;

-- Q2: Price statistics
SELECT
  MAX(close) as recent_high,
  MIN(close) as recent_low,
  AVG(volume) as avg_volume
FROM stock_prices.daily
WHERE ticker = '<TICKER>';

-- Q3: Latest news
SELECT headline, summary, datetime, source
FROM finnhub.news
WHERE symbol = '<TICKER>'
  AND datetime >= <30_DAYS_AGO_UNIX>
ORDER BY datetime DESC LIMIT 10;

-- Q4: Analyst ratings
SELECT symbol, buy, strongBuy, sell, strongSell, hold, period
FROM finnhub.analyst_ratings
WHERE symbol = '<TICKER>' LIMIT 5;

-- Q5: Insider trades
SELECT name, share, change, transactionDate, transactionCode, transactionPrice
FROM finnhub.insider_trades
WHERE symbol = '<TICKER>'
ORDER BY transactionDate DESC LIMIT 10;
```

---

## Claude Prompt Structure

```
You are a financial analyst. A user wants to understand why <TICKER> is moving.

Here is live data pulled from multiple sources via SQL:

### PRICE SUMMARY
<coral sql results>

### PRICE CHANGE
<coral sql results>

### NEWS
<coral sql results>

### ANALYST RATINGS
<coral sql results>

### INSIDER TRADES
<coral sql results>

Based on this data, provide a clear analysis covering:
1. What the stock has done recently (price action, volume)
2. Key news triggers
3. Analyst sentiment
4. Insider activity
5. Overall verdict (1-2 sentences)

Be specific and reference the actual data. Max 400 words.
```

---

## File Structure

```
stock-analyzer/
├── .kiro/
│   └── mcp.json              ← Coral MCP config for Kiro
├── sources/
│   ├── finnhub.yaml          ← Coral source: news, ratings, insiders
│   ├── sec_edgar.yaml        ← Coral source: 8-K filings
│   └── stock_prices.yaml     ← Coral source: local JSONL prices
├── data/
│   └── prices.jsonl          ← Auto-generated, gitignored
├── fetch_prices.py           ← Downloads price data via yfinance
├── analyze.py                ← Main agent: queries Coral + calls Claude
├── setup.ps1                 ← One-click Windows setup script
├── .env                      ← API keys (gitignored)
├── .env.example              ← Key template (committed)
├── .gitignore
└── README.md
```

---

## Error Handling Strategy

| Scenario | Behaviour |
|---|---|
| Invalid ticker in yfinance | Print error, exit 1 |
| Coral not on PATH | Print install instructions, exit 1 |
| Coral query fails | Log warning, continue with other queries |
| Missing API key in .env | Print which key is missing, exit 1 |
| Claude API error | Print HTTP error code + message, exit 1 |
| Finnhub rate limit (60 req/min) | Coral handles; add 1s sleep between queries if needed |
