---
name: Financial Market Data (Stocks, Options & Crypto)
description: Query live and historical financial market data for US equities, options chains, dividends, splits, and NBBO quotes via Polygon.io, alongside live cryptocurrency prices, market caps, and historical price charts via CoinGecko.
category: Finance
icon: 📈
tags: [stocks, crypto, finance, market-data, polygon, coingecko, options, dividends, bitcoin, trading, shares, btc, eth]
---

# 📈 Financial Market Data (Equities, Options & Crypto)

Autonomous protocols for retrieving and modeling US equity market data, options pricing, company fundamentals, and cryptocurrency market intelligence.

---

## 1. US Equities & Options Protocol (Polygon.io)

When the user requests stock quotes, historical candles (OHLCV), options chains, stock splits, or dividend histories, execute via `run_python` using `polygon-api-client` or direct REST API requests.

### Aggregate Bars (OHLCV)
```python
from polygon import RESTClient
import pandas as pd

client = RESTClient()
bars = client.get_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="day",       # "minute", "hour", "day", "week", "month"
    from_="2024-01-01",
    to="2024-12-31",
    adjusted=True,
    sort="asc",
    limit=50000,
)
df = pd.DataFrame(bars)
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
print(df[["timestamp", "open", "high", "low", "close", "volume"]].tail())
```

### Ticker Metadata & Last NBBO Quote
```python
details = client.get_ticker_details("NVDA")
print(f"Name: {details.name} | MCap: ${details.market_cap:,.0f}")

quote = client.get_last_quote(ticker="NVDA")
print(f"Bid: ${quote.bid_price} x {quote.bid_size} | Ask: ${quote.ask_price} x {quote.ask_size}")
```

### Options Chains
```python
contracts = list(client.list_options_contracts(
    underlying_ticker="AAPL",
    contract_type="call",           # "call", "put"
    expiration_date="2025-01-17",
    expired=False,
    limit=50,
))
for c in contracts[:5]:
    print(f"{c.ticker}: Strike=${c.strike_price} Exp={c.expiration_date} Type={c.contract_type}")
```

### Dividends & Splits
```python
for d in client.list_dividends(ticker="MSFT"):
    print(f"MSFT Ex-Date: {d.ex_dividend_date} | Cash Amount: ${d.cash_amount}")

for s in client.list_splits(ticker="NVDA"):
    print(f"NVDA Split: {s.execution_date} | Ratio: {s.split_from}:{s.split_to}")
```

---

## 2. Cryptocurrency Market Intelligence (CoinGecko)

Query free, unauthenticated CoinGecko REST endpoints for spot prices, top market cap rankings, volume, and historical charts.

### Spot Prices (BTC, ETH, SOL)
```python
import requests

r = requests.get("https://api.coingecko.com/api/v3/simple/price", params={
    "ids": "bitcoin,ethereum,solana",
    "vs_currencies": "usd",
    "include_market_cap": "true",
    "include_24hr_vol": "true",
    "include_24hr_change": "true",
})
data = r.json()
for coin, stats in data.items():
    print(f"{coin.upper()}: ${stats['usd']:,.2f} (24h: {stats.get('usd_24h_change', 0):+.2f}%)")
```

### Market Leaderboard & Historical Price Charts
```python
# Top 10 by Market Cap
r = requests.get("https://api.coingecko.com/api/v3/coins/markets", params={
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 10,
    "page": 1,
})
for coin in r.json():
    print(f"#{coin['market_cap_rank']} {coin['name']} ({coin['symbol'].upper()}): ${coin['current_price']:,.2f} | MCap: ${coin['market_cap']:,.0f}")

# 30-Day Historical Chart
r_chart = requests.get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart", params={
    "vs_currency": "usd",
    "days": "30",
    "interval": "daily",
})
```

---

## Output Formatting Standards
1. Structure output in **clean markdown tables** with currency symbols and comma separators.
2. Provide technical context: 24h range, 52-week highs/lows, market cap weighting, and implied volatility (IV) where applicable.
