# Tasks: Stock Move Analyzer (Coral + Claude)

## How to use this file in Kiro
1. Open Kiro → Spec panel → select this spec
2. Click **"Run all Tasks"** to let Kiro execute everything automatically
3. Or click **"Start Task"** above any individual task to run it one at a time

Tasks marked with `[depends: X]` will wait for task X to complete first.
Independent tasks run concurrently.

---

## Task List

- [ ] 1. Create project folder structure
- [ ] 2. Create `.gitignore` and `.env.example`
- [ ] 3. Create `sources/finnhub.yaml`
- [ ] 4. Create `sources/sec_edgar.yaml`
- [ ] 5. Create `sources/stock_prices.yaml`
- [ ] 6. Create `fetch_prices.py`
- [ ] 7. Create `analyze.py`
- [ ] 8. Create `setup.ps1`
- [ ] 9. Create `.kiro/mcp.json`
- [ ] 10. Create `README.md`

---

## Task Details

---

### Task 1: Create project folder structure

Create the following empty directories:
- `sources/`
- `data/`
- `.kiro/`

No files yet — just the directory skeleton.

**Acceptance check:** Running `dir` (Windows) shows `sources`, `data`, `.kiro` folders.

---

### Task 2: Create `.gitignore` and `.env.example`

**File: `.env.example`**
```
FINNHUB_API_KEY=your_finnhub_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

**File: `.gitignore`**
```
# API keys - never commit these
.env

# Auto-generated price data
data/

# Coral install artifacts
coral-bin/
coral-x86_64-pc-windows-msvc.zip

# Python
__pycache__/
*.pyc
*.pyo
.venv/
```

**Acceptance check:** Both files exist; `.env` is not tracked by git.

---

### Task 3: Create `sources/finnhub.yaml`

[depends: Task 1]

Create `sources/finnhub.yaml` with this exact content:

```yaml
name: finnhub
version: 0.1.0
dsl_version: 3
backend: http
inputs:
  FINNHUB_API_KEY:
    kind: secret
    hint: "Your Finnhub API key from https://finnhub.io (free tier)"
base_url: "https://finnhub.io/api/v1"
auth:
  type: HeaderAuth
  headers:
    - name: X-Finnhub-Token
      from: template
      template: "{{input.FINNHUB_API_KEY}}"
tables:
  - name: news
    description: "Latest company news. Filter by symbol and date range (unix timestamps)."
    request:
      method: GET
      path: /company-news
    response:
      rows_path: []
    columns:
      - name: id
        type: Int64
      - name: headline
        type: Utf8
      - name: summary
        type: Utf8
      - name: datetime
        type: Int64
      - name: symbol
        type: Utf8
      - name: source
        type: Utf8
      - name: url
        type: Utf8

  - name: analyst_ratings
    description: "Wall Street analyst buy/sell/hold consensus by ticker symbol."
    request:
      method: GET
      path: /stock/recommendation
    response:
      rows_path: []
    columns:
      - name: symbol
        type: Utf8
      - name: buy
        type: Int64
      - name: strongBuy
        type: Int64
      - name: sell
        type: Int64
      - name: strongSell
        type: Int64
      - name: hold
        type: Int64
      - name: period
        type: Utf8

  - name: insider_trades
    description: "Recent insider buy/sell transactions (Form 4 SEC filings)."
    request:
      method: GET
      path: /stock/insider-transactions
    response:
      rows_path:
        - data
    columns:
      - name: name
        type: Utf8
      - name: share
        type: Int64
      - name: change
        type: Int64
      - name: transactionDate
        type: Utf8
      - name: transactionCode
        type: Utf8
      - name: transactionPrice
        type: Float64
```

**Acceptance check:** `coral source add --file sources/finnhub.yaml` runs without error.

---

### Task 4: Create `sources/sec_edgar.yaml`

[depends: Task 1]

Create `sources/sec_edgar.yaml` with this exact content:

```yaml
name: sec_edgar
version: 0.1.0
dsl_version: 3
backend: http
inputs:
  SEC_USER_AGENT:
    kind: variable
    default: "StockAnalyzer contact@example.com"
    hint: "Required by SEC EDGAR. Format: AppName email@domain.com"
base_url: "https://efts.sec.gov"
auth:
  type: HeaderAuth
  headers:
    - name: User-Agent
      from: template
      template: "{{input.SEC_USER_AGENT}}"
tables:
  - name: filings
    description: "SEC EDGAR full-text search. Use form_type filter for 8-K (major events), 10-K (annual report), 10-Q (quarterly)."
    request:
      method: GET
      path: /LATEST/search-index
    response:
      rows_path:
        - hits
        - hits
    columns:
      - name: entity_name
        type: Utf8
      - name: file_date
        type: Utf8
      - name: form_type
        type: Utf8
      - name: period_of_report
        type: Utf8
      - name: file_num
        type: Utf8
```

**Acceptance check:** `coral source add --file sources/sec_edgar.yaml --interactive` completes.

---

### Task 5: Create `sources/stock_prices.yaml`

[depends: Task 1]

Create `sources/stock_prices.yaml` with this exact content.
Note: `REPLACE_WITH_ABSOLUTE_PATH` is a placeholder — `setup.ps1` replaces it automatically.

```yaml
name: stock_prices
version: 0.1.0
dsl_version: 3
backend: jsonl
tables:
  - name: daily
    description: "Daily OHLCV price data and company metadata. Refreshed per-ticker by running fetch_prices.py."
    source:
      location: "file:///REPLACE_WITH_ABSOLUTE_PATH/data/"
      glob: "*.jsonl"
    columns:
      - name: ticker
        type: Utf8
      - name: company_name
        type: Utf8
      - name: sector
        type: Utf8
      - name: date
        type: Utf8
      - name: open
        type: Float64
      - name: high
        type: Float64
      - name: low
        type: Float64
      - name: close
        type: Float64
      - name: volume
        type: Int64
      - name: market_cap
        type: Int64
      - name: pe_ratio
        type: Float64
      - name: week_52_high
        type: Float64
      - name: week_52_low
        type: Float64
```

**Acceptance check:** File exists; `setup.ps1` will patch the path and register it.

---

### Task 6: Create `fetch_prices.py`

[depends: Task 1]

Create `fetch_prices.py` in the project root:

```python
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
    print(f"Fetching price data for {ticker}...")

    stock = yf.Ticker(ticker)
    df = yf.download(ticker, period="1mo", interval="1d", progress=False)

    if df.empty:
        print(f"ERROR: No data found for ticker '{ticker}'. Check the symbol.")
        sys.exit(1)

    df = df.reset_index()
    # Flatten multi-level columns if present (yfinance sometimes returns these)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

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

    print(f"Saved {len(df)} days of data for {company_name} ({ticker}) → {output_path}")
    return len(df)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_prices.py <TICKER>")
        print("Example: python fetch_prices.py NVDA")
        sys.exit(1)

    ticker_input = sys.argv[1].upper().strip()
    fetch_prices(ticker_input)
```

**Acceptance check:** `python fetch_prices.py NVDA` creates `data/prices.jsonl` with 20+ rows.

---

### Task 7: Create `analyze.py`

[depends: Task 6]

Create `analyze.py` in the project root:

```python
#!/usr/bin/env python3
"""
Stock Move Analyzer — powered by Coral + Claude
Queries live data from Finnhub, SEC EDGAR, and local prices via Coral SQL,
then uses Claude to explain why the stock is moving.

Usage: python analyze.py NVDA
"""
import sys
import subprocess
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


def check_env():
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not FINNHUB_API_KEY:
        missing.append("FINNHUB_API_KEY")
    if missing:
        print(f"ERROR: Missing keys in .env: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your keys.")
        sys.exit(1)


def run_coral_sql(query: str, label: str) -> str:
    """Run a SQL query through Coral CLI and return result as text."""
    print(f"  ⟶ {label}...")
    try:
        result = subprocess.run(
            ["coral", "sql", query.strip()],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "FINNHUB_API_KEY": FINNHUB_API_KEY}
        )
        if result.returncode != 0:
            print(f"    ⚠ Warning: {result.stderr.strip()[:100]}")
            return f"(query failed: {result.stderr.strip()[:200]})"
        return result.stdout.strip() or "(no results)"
    except subprocess.TimeoutExpired:
        print(f"    ⚠ Warning: {label} timed out")
        return "(query timed out)"
    except FileNotFoundError:
        print("ERROR: 'coral' not found. Run setup.ps1 first.")
        sys.exit(1)


def fetch_and_analyze(ticker: str):
    ticker = ticker.upper().strip()

    print(f"\n{'='*60}")
    print(f"  Stock Move Analyzer: {ticker}")
    print(f"{'='*60}\n")

    # Step 1: Refresh price data
    print("📈 Fetching latest price data from yfinance...")
    subprocess.run(
        [sys.executable, "fetch_prices.py", ticker],
        check=True
    )

    # Step 2: Prepare time filters
    now_unix = int(datetime.now().timestamp())
    ago_unix = int((datetime.now() - timedelta(days=30)).timestamp())

    print("\n🔍 Querying data sources via Coral SQL...\n")

    # Step 3: Run all Coral queries
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
        SELECT symbol, buy, strongBuy, sell, strongSell, hold, period
        FROM finnhub.analyst_ratings
        WHERE symbol = '{ticker}'
        LIMIT 5
    """, "Analyst ratings (Finnhub)")

    results["insider_trades"] = run_coral_sql(f"""
        SELECT name, share, change, transactionDate, transactionCode, transactionPrice
        FROM finnhub.insider_trades
        WHERE symbol = '{ticker}'
        ORDER BY transactionDate DESC LIMIT 10
    """, "Insider trades (Finnhub)")

    # Step 4: Build prompt
    data_block = "\n\n".join([
        f"### {label.upper().replace('_', ' ')}\n{data}"
        for label, data in results.items()
        if data and "query failed" not in data and "timed out" not in data
    ])

    if not data_block.strip():
        print("\nERROR: All queries failed. Check that Coral sources are registered.")
        print("Run: coral source list")
        sys.exit(1)

    prompt = f"""You are a senior financial analyst. A user wants to understand why {ticker} stock is moving.

Here is live data queried from multiple sources via SQL through Coral:

{data_block}

Based only on this data, write a clear analysis covering:
1. **Recent price action** — What has the stock done? How does recent volume compare to average?
2. **Key news triggers** — What headlines or events might explain the move?
3. **Analyst sentiment** — Are analysts broadly bullish, bearish, or neutral right now?
4. **Insider activity** — Are insiders buying or selling? What does it signal?
5. **Overall verdict** — In 1-2 sentences, why is this stock most likely moving?

Be specific: reference actual numbers and dates from the data.
If the data is inconclusive on any point, say so honestly.
Keep the total response under 400 words."""

    # Step 5: Call Claude
    print("\n🤖 Claude is analyzing the data...\n")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
    except Exception as e:
        print(f"ERROR: Claude API call failed: {e}")
        sys.exit(1)

    # Step 6: Print result
    print(f"\n{'='*60}")
    print(f"  Analysis for {ticker}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")
    print(message.content[0].text)
    print(f"\n{'='*60}\n")


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
```

**Acceptance check:** `python analyze.py NVDA` prints a formatted analysis without crashing.

---

### Task 8: Create `setup.ps1`

[depends: Task 3, Task 4, Task 5]

Create `setup.ps1` in the project root:

```powershell
# setup.ps1 — One-click setup for Stock Move Analyzer on Windows
# Run with: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Stock Move Analyzer — Setup for Windows"      -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Install Coral ────────────────────────────────────
Write-Host "Step 1: Installing Coral CLI..." -ForegroundColor Yellow

$coralZip  = "coral-x86_64-pc-windows-msvc.zip"
$coralDir  = "coral-bin"
$coralDest = "$env:USERPROFILE\.local\bin"

Invoke-WebRequest `
  -Uri "https://github.com/withcoral/coral/releases/latest/download/$coralZip" `
  -OutFile $coralZip

Expand-Archive -Path $coralZip -DestinationPath $coralDir -Force
New-Item -ItemType Directory -Force -Path $coralDest | Out-Null
Copy-Item "$coralDir\coral.exe" "$coralDest\coral.exe" -Force

# Add to PATH for this session and permanently for user
if ($env:Path -notlike "*$coralDest*") {
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$coralDest;$([Environment]::GetEnvironmentVariable('Path','User'))",
        "User"
    )
    $env:Path = "$coralDest;$env:Path"
}

$coralVersion = coral --version 2>&1
Write-Host "Coral installed: $coralVersion" -ForegroundColor Green

# ── Step 2: Python dependencies ──────────────────────────────
Write-Host ""
Write-Host "Step 2: Installing Python dependencies..." -ForegroundColor Yellow
pip install yfinance anthropic requests python-dotenv
Write-Host "Python dependencies installed." -ForegroundColor Green

# ── Step 3: Create data directory ────────────────────────────
New-Item -ItemType Directory -Force -Path "data" | Out-Null

# ── Step 4: Configure API keys ───────────────────────────────
Write-Host ""
Write-Host "Step 3: Configure API keys" -ForegroundColor Yellow
Write-Host "  Finnhub: get your free key at https://finnhub.io"
Write-Host "  Anthropic: get your key at https://console.anthropic.com"
Write-Host ""

$finnhubKey  = Read-Host "Enter your Finnhub API key"
$anthropicKey = Read-Host "Enter your Anthropic API key"

@"
FINNHUB_API_KEY=$finnhubKey
ANTHROPIC_API_KEY=$anthropicKey
"@ | Out-File -FilePath ".env" -Encoding UTF8

Write-Host ".env file created." -ForegroundColor Green

# ── Step 5: Patch absolute path in stock_prices.yaml ─────────
Write-Host ""
Write-Host "Step 4: Patching absolute path into stock_prices.yaml..." -ForegroundColor Yellow

$absPath = (Get-Location).Path.Replace("\", "/")
$yamlPath = "sources/stock_prices.yaml"
(Get-Content $yamlPath) `
    -replace "REPLACE_WITH_ABSOLUTE_PATH", $absPath | `
    Set-Content $yamlPath

Write-Host "Path set to: $absPath" -ForegroundColor Green

# ── Step 6: Register Coral sources ───────────────────────────
Write-Host ""
Write-Host "Step 5: Registering Coral sources..." -ForegroundColor Yellow
$env:FINNHUB_API_KEY = $finnhubKey

Write-Host "  Adding finnhub..."
coral source add --file ./sources/finnhub.yaml

Write-Host "  Adding sec_edgar..."
coral source add --file ./sources/sec_edgar.yaml --interactive

Write-Host "  Adding stock_prices..."
coral source add --file ./sources/stock_prices.yaml

Write-Host ""
coral source list

# ── Done ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Setup Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run your first analysis:"
Write-Host "  python analyze.py NVDA" -ForegroundColor Yellow
Write-Host ""
```

**Acceptance check:** Running `powershell -ExecutionPolicy Bypass -File setup.ps1`
completes all steps and ends with `python analyze.py NVDA` instruction.

---

### Task 9: Create `.kiro/mcp.json`

[depends: Task 1]

Create `.kiro/mcp.json`:

```json
{
  "mcpServers": {
    "coral": {
      "type": "stdio",
      "command": "coral",
      "args": ["mcp-stdio"]
    }
  }
}
```

This gives Kiro's agent direct access to all registered Coral sources via MCP
tools: `sql`, `list_catalog`, `describe_table`, `search_catalog`, `list_columns`.

**Acceptance check:** After Kiro reloads, asking Kiro "list Coral tables" returns
the registered schemas.

---

### Task 10: Create `README.md`

[depends: Task 7, Task 8]

Create `README.md`:

```markdown
# Stock Move Analyzer

An AI agent that explains why a stock is moving by querying live data from
multiple sources as SQL tables through [Coral](https://withcoral.com), then
using Claude to synthesize the analysis.

## What it does

Type a ticker → get a plain-English explanation backed by real data:
- Recent price action and volume (yfinance)
- Breaking news and analyst ratings (Finnhub)
- Insider buy/sell transactions (Finnhub)
- SEC 8-K major event filings (SEC EDGAR)

## Quick Start (Windows)

### 1. Get your free API keys
- **Finnhub**: https://finnhub.io (free, instant signup)
- **Anthropic**: https://console.anthropic.com

### 2. Run setup
```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

### 3. Run an analysis
```powershell
python analyze.py NVDA
python analyze.py AAPL
python analyze.py TSLA
```

## How it works

```
python analyze.py NVDA
       ↓
fetch_prices.py → data/prices.jsonl
       ↓
coral sql (5 queries across Finnhub + SEC EDGAR + prices)
       ↓
Claude API → plain-English analysis
```

Coral turns every API into a SQL table. Instead of custom API code for each
source, the agent just writes SQL — and Coral handles auth, pagination, and
rate limits behind the scenes.

## Manual setup (if setup.ps1 doesn't work)

```powershell
# Install Coral
Invoke-WebRequest -Uri "https://github.com/withcoral/coral/releases/latest/download/coral-x86_64-pc-windows-msvc.zip" -OutFile coral.zip
Expand-Archive coral.zip -DestinationPath coral-bin
Copy-Item coral-bin\coral.exe "$env:USERPROFILE\.local\bin\coral.exe"

# Install Python deps
pip install yfinance anthropic requests python-dotenv

# Add your keys
copy .env.example .env
# Edit .env with your keys

# Register sources (fix absolute path in stock_prices.yaml first)
coral source add --file sources/finnhub.yaml
coral source add --file sources/sec_edgar.yaml --interactive
coral source add --file sources/stock_prices.yaml
```

## Extending the project

- Add Reddit sentiment (r/wallstreetbets) as a custom Coral HTTP source
- Add a Streamlit web UI for a browser-based interface
- Schedule `analyze.py` with Windows Task Scheduler for daily alerts
- Extend to a portfolio: loop over multiple tickers and compare

## Built with

- [Coral](https://withcoral.com) — SQL layer over live APIs
- [Claude](https://anthropic.com) — analysis and synthesis
- [Finnhub](https://finnhub.io) — news, ratings, insider trades
- [yfinance](https://pypi.org/project/yfinance/) — price history
- [SEC EDGAR](https://efts.sec.gov) — public filings
```

**Acceptance check:** README renders correctly on GitHub with all sections visible.
```

---

## Running Order (Kiro's dependency graph)

```
Wave 1 (parallel): Task 1
Wave 2 (parallel): Task 2, Task 3, Task 4, Task 5
Wave 3 (parallel): Task 6, Task 9
Wave 4 (parallel): Task 7
Wave 5 (parallel): Task 8, Task 10
```

Total estimated time with Kiro running tasks concurrently: ~3-5 minutes.
