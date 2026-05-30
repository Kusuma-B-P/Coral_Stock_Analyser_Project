# Requirements: Stock Move Analyzer (Coral + Claude)

## Overview

A CLI tool that explains why a stock is moving by querying multiple live data
sources (news, analyst ratings, insider trades, price history, SEC filings) as
SQL tables through Coral, then using Claude to synthesize a plain-English analysis.

---

## User Stories & Acceptance Criteria (EARS Notation)

---

### REQ-1: Install Coral CLI

**User Story**
As a developer on Windows, I want to install the Coral CLI so that I can register
data sources and run SQL queries against live APIs.

**Acceptance Criteria**

- WHEN the setup script runs, THE SYSTEM SHALL download the latest Coral Windows
  binary from GitHub releases and place it at `%USERPROFILE%\.local\bin\coral.exe`.
- WHEN installation completes, THE SYSTEM SHALL verify that `coral --version`
  returns a version string without error.
- IF `coral.exe` already exists at the target path, THE SYSTEM SHALL overwrite it
  with the latest version.

---

### REQ-2: Install Python Dependencies

**User Story**
As a developer, I want all required Python packages installed so that the scripts
can fetch data and call the Claude API.

**Acceptance Criteria**

- WHEN setup runs, THE SYSTEM SHALL install `yfinance`, `anthropic`, `requests`,
  and `python-dotenv` via pip.
- IF any package fails to install, THE SYSTEM SHALL print the error and exit with
  a non-zero code.

---

### REQ-3: Configure API Keys Securely

**User Story**
As a developer, I want my API keys stored in a `.env` file so that they are never
committed to version control.

**Acceptance Criteria**

- THE SYSTEM SHALL provide a `.env.example` file with placeholder values for
  `FINNHUB_API_KEY` and `ANTHROPIC_API_KEY`.
- THE SYSTEM SHALL include `.env` and `data/` in `.gitignore`.
- WHEN `analyze.py` starts, THE SYSTEM SHALL load keys from `.env` using
  `python-dotenv` and exit with a clear error message if either key is missing.

---

### REQ-4: Register Finnhub as a Coral Source

**User Story**
As a developer, I want Finnhub's news, analyst ratings, and insider trades exposed
as SQL tables in Coral so the agent can query them without custom API code.

**Acceptance Criteria**

- THE SYSTEM SHALL provide `sources/finnhub.yaml` that defines three tables:
  `finnhub.news`, `finnhub.analyst_ratings`, and `finnhub.insider_trades`.
- WHEN `coral source add --file sources/finnhub.yaml` runs, THE SYSTEM SHALL
  register the source without error.
- WHEN `coral source test finnhub` runs, THE SYSTEM SHALL return at least one
  row from `finnhub.analyst_ratings` for a valid ticker.
- THE SYSTEM SHALL pass the `FINNHUB_API_KEY` secret through Coral's input
  mechanism so it is never hard-coded in the YAML.

---

### REQ-5: Register SEC EDGAR as a Coral Source

**User Story**
As a developer, I want SEC EDGAR 8-K filings exposed as a SQL table in Coral so
the agent can detect major corporate events without an API key.

**Acceptance Criteria**

- THE SYSTEM SHALL provide `sources/sec_edgar.yaml` that defines the table
  `sec_edgar.filings`.
- WHEN `coral source add --file sources/sec_edgar.yaml` runs, THE SYSTEM SHALL
  register the source without error.
- THE SYSTEM SHALL set the `User-Agent` header to the value required by SEC EDGAR
  (format: `AppName contact@email.com`).

---

### REQ-6: Fetch and Store Daily Price Data

**User Story**
As a developer, I want a script that fetches 30 days of OHLCV price data for any
ticker and saves it as a JSONL file so Coral can query it as a SQL table.

**Acceptance Criteria**

- WHEN `python fetch_prices.py NVDA` is run, THE SYSTEM SHALL fetch 30 days of
  daily OHLC + volume data for NVDA from yfinance.
- THE SYSTEM SHALL include company metadata (name, sector, market cap, P/E ratio,
  52-week high/low) as extra columns.
- THE SYSTEM SHALL write output to `data/prices.jsonl`, creating the `data/`
  directory if it does not exist.
- IF the ticker symbol is invalid or has no data, THE SYSTEM SHALL print a clear
  error and exit with a non-zero code.
- THE SYSTEM SHALL provide `sources/stock_prices.yaml` that exposes
  `stock_prices.daily` as a Coral table backed by `data/prices.jsonl`.

---

### REQ-7: Run Multi-Source SQL Analysis via Coral

**User Story**
As a developer, I want the main script to query all data sources through Coral SQL
so the agent does not need custom API code for each source.

**Acceptance Criteria**

- WHEN `python analyze.py NVDA` is run, THE SYSTEM SHALL first call
  `fetch_prices.py NVDA` to refresh local price data.
- THE SYSTEM SHALL run at least five distinct `coral sql` queries covering:
  price history, price summary stats, recent news, analyst ratings, and insider trades.
- IF a Coral query returns an error, THE SYSTEM SHALL log it and continue with the
  remaining queries rather than crashing.
- THE SYSTEM SHALL collect all query results into a structured data block before
  calling the Claude API.

---

### REQ-8: Generate a Claude Analysis

**User Story**
As a user, I want Claude to read the Coral query results and explain in plain
English why the stock is moving, so I can understand the situation in under a minute.

**Acceptance Criteria**

- WHEN all Coral queries have completed, THE SYSTEM SHALL send the combined results
  to the Claude API using model `claude-sonnet-4-20250514`.
- THE SYSTEM SHALL instruct Claude to cover: recent price action, key news triggers,
  analyst sentiment, insider activity, and an overall verdict.
- THE SYSTEM SHALL print the analysis to stdout in a clearly formatted block.
- THE SYSTEM SHALL limit the analysis to approximately 400 words.
- IF the Claude API call fails, THE SYSTEM SHALL print the HTTP error and exit with
  a non-zero code.

---

### REQ-9: One-Click Windows Setup

**User Story**
As a first-time user on Windows, I want a single PowerShell setup script so I can
go from zero to running `python analyze.py NVDA` in under 10 minutes.

**Acceptance Criteria**

- THE SYSTEM SHALL provide `setup.ps1` that performs all steps: Coral install,
  pip install, `.env` creation, and `coral source add` for all three sources.
- WHEN setup completes, THE SYSTEM SHALL print a success message and the exact
  command to run a first analysis.
- THE SYSTEM SHALL automatically replace the `REPLACE_WITH_ABSOLUTE_PATH`
  placeholder in `sources/stock_prices.yaml` with the real current directory path.

---

### REQ-10: Connect Coral to Kiro via MCP

**User Story**
As a developer using Kiro, I want Coral registered as an MCP server so Kiro can
query my data sources directly during development.

**Acceptance Criteria**

- THE SYSTEM SHALL provide `.kiro/mcp.json` that registers `coral mcp-stdio` as
  a stdio MCP server named `coral`.
- WHEN Kiro starts with this config, THE SYSTEM SHALL make the `sql`, `list_catalog`,
  `describe_table`, and `search_catalog` MCP tools available to Kiro's agent.
