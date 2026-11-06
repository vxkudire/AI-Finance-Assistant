# MCP tools API

The AI Finance Assistant exposes a read-only [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server over **stdio**. It registers six tools for market data, news, portfolio analysis, and savings calculations. It does not expose an HTTP or REST endpoint, persist submitted holdings, or place trades.

## Connect

Run the server from the repository root with the project environment:

```shell
python -m src.mcp_server
```

Configure an MCP client to launch the same command using the repository as its working directory. For example:

```json
{
  "mcpServers": {
    "ai-finance-assistant": {
      "command": "C:\\path\\to\\AI-Finance-Assistant\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.mcp_server"],
      "cwd": "C:\\path\\to\\AI-Finance-Assistant"
    }
  }
}
```

The server uses Yahoo Finance for quotes and market data and the RSS feeds configured in `config.yaml` for news. These tools do not require API keys. Market prices may be delayed; outputs are for financial education, not personalized financial advice.

## Tool reference

All tools accept named JSON arguments and return structured objects. Invalid arguments are reported as MCP tool errors. Provider outages are generally represented in the result (for example, in `missing` or `skipped`) rather than as validation errors.

### `get_quotes`

Fetch current quotes for 1–25 ticker symbols. Symbols are trimmed, uppercased, and deduplicated before lookup.

| Argument | Type | Required | Constraints |
|---|---|---:|---|
| `tickers` | `string[]` | Yes | 1–25 symbols; each symbol must match the server's ticker format. |

Example request:

```json
{"tickers":["aapl","MSFT","^GSPC"]}
```

Response shape:

```json
{
  "quotes": [
    {"ticker": "AAPL", "price": 190.0, "prev_close": 188.0, "change_pct": 1.0638}
  ],
  "missing": ["^GSPC"],
  "rate_limited": false
}
```

`quotes` contains successfully retrieved symbols only. `missing` lists requested symbols without a quote; `rate_limited` indicates the provider rate-limited the request.

### `get_market_overview`

Fetch major-index and sector ETF quotes, actual index levels, and normalized performance.

| Argument | Type | Required | Constraints |
|---|---|---:|---|
| `period` | `string` | No | One of `5d`, `1mo`, `3mo`, `6mo`, `1y`, `ytd`; default `1mo`. |

Example request:

```json
{"period":"1mo"}
```

Response shape:

```json
{
  "indices": [
    {"ticker":"^GSPC","price":6000.0,"prev_close":5980.0,"change_pct":0.3344,"name":"S&P 500"}
  ],
  "sectors": [
    {"ticker":"XLK","price":200.0,"prev_close":199.0,"change_pct":0.5025,"name":"Technology"}
  ],
  "normalized_performance": [
    {"Date":"2025-01-02","S&P 500":100.0,"Dow Jones":100.0}
  ],
  "index_levels": [
    {"Date":"2025-01-02","S&P 500":6000.0,"Dow Jones":42000.0}
  ],
  "as_of":"2025-01-02T16:00:00+00:00",
  "missing_quotes":["^IXIC"],
  "period":"1mo"
}
```

`indices` and `sectors` contain available quotes only. `normalized_performance` rebases the available major stock-index history to 100 at the start of the period; `index_levels` contains actual levels. Both are arrays of records with a `Date` field and one field per available index, and may be empty when history is unavailable. `missing_quotes` lists unavailable index and sector symbols.

### `get_financial_news`

Fetch headlines from the RSS feeds in `config.yaml`, optionally filtering by terms. If no headline matches, the server returns general headlines instead.

| Argument | Type | Required | Constraints |
|---|---|---:|---|
| `terms` | `string[]` or `null` | No | Optional case-insensitive title/summary terms; blank terms are ignored. |
| `limit` | `integer` or `null` | No | 1–25; defaults to `data.max_news_items` from configuration. |

Example request:

```json
{"terms":["inflation","interest rates"],"limit":5}
```

Response shape:

```json
{
  "items": [
    {"source":"Finance Daily","title":"Rates hold steady","summary":"Central bank update","published":"Thu, 02 Jan 2025 15:00:00 GMT","link":"https://example.test/story"}
  ],
  "some_feeds_failed": false
}
```

Each item has `source`, `title`, `summary`, `published`, and `link` strings. `some_feeds_failed` is true if one or more configured feeds could not be fetched.

### `analyze_portfolio`

Calculate current valuation, position weights, gain/loss, concentration, and sector mix for 1–50 holdings. Holdings are processed for this request only and are not stored.

| Argument | Type | Required | Constraints |
|---|---|---:|---|
| `holdings` | `object[]` | Yes | 1–50 objects; each must include a valid `ticker` and positive finite `shares`. |
| `include_sector` | `boolean` | No | Whether to retrieve sector metadata; default `true`. |

Each holding object accepts:

| Field | Type | Required | Constraints |
|---|---|---:|---|
| `ticker` | `string` | Yes | Valid ticker symbol; normalized to uppercase. |
| `shares` | `number` | Yes | Finite and greater than 0. |
| `cost_basis` | `number` | No | Finite, non-negative per-share cost basis. |

Example request:

```json
{
  "holdings": [
    {"ticker":"AAPL","shares":10,"cost_basis":150},
    {"ticker":"VTI","shares":5}
  ],
  "include_sector":true
}
```

Response shape:

```json
{
  "rows": [
    {"ticker":"AAPL","shares":10.0,"price":190.0,"value":1900.0,"cost_basis":150.0,"gain_pct":26.6667,"sector":"Technology","weight":0.76},
    {"ticker":"VTI","shares":3.0,"price":200.0,"value":600.0,"cost_basis":null,"gain_pct":null,"sector":"ETF","weight":0.24}
  ],
  "total_value":2500.0,
  "top_weight":0.76,
  "hhi":0.6352,
  "effective_holdings":1.5743,
  "sectors":{"Technology":0.76,"Exchange Traded Fund":0.24},
  "skipped":["XYZ"]
}
```

`gain_pct` is `null` if cost basis is absent or zero. `skipped` lists holdings that could not be priced, so the returned metrics may describe only the priced positions. When sector lookup is unavailable, the position is retained with sector `Unknown`.

### `project_future_value`

Project a starting balance plus monthly contributions with monthly compounding.

| Argument | Type | Required | Constraints |
|---|---|---:|---|
| `present` | `number` | Yes | Finite and non-negative starting balance. |
| `monthly` | `number` | Yes | Finite and non-negative monthly contribution. |
| `annual_rate` | `number` | Yes | Finite decimal rate from `-0.99` through `1`; for example, `0.07` means 7%. |
| `years` | `number` | Yes | Finite, from 0 through 100. |

Example request and response:

```json
{"present":1000,"monthly":100,"annual_rate":0.07,"years":10}
```

```json
{"future_value":19318.14}
```

The numeric value shown is illustrative; the result depends on the inputs.

### `required_monthly_contribution`

Calculate the monthly contribution needed to reach a target, assuming monthly compounding.

| Argument | Type | Required | Constraints |
|---|---|---:|---|
| `target` | `number` | Yes | Finite and non-negative target balance. |
| `present` | `number` | Yes | Finite and non-negative starting balance. |
| `annual_rate` | `number` | Yes | Finite decimal rate from `-0.99` through `1`; for example, `0.07` means 7%. |
| `years` | `number` | Yes | Finite, from 0 through 100. |

Example request and response:

```json
{"target":50000,"present":5000,"annual_rate":0.05,"years":10}
```

```json
{"required_monthly_contribution":268.96}
```

If the starting balance already reaches the target under the assumed return, the required contribution is zero. At a zero-year horizon, the result is the unfunded gap (or zero if already funded).

## Validation and failures

- Invalid arguments produce an MCP tool error, including invalid ticker formats, out-of-range list sizes, non-finite numeric values, non-positive shares, invalid periods, and calculator values outside their allowed bounds.
- For ticker validation, symbols are limited to 15 characters and must begin with a letter, digit, or `^`; subsequent characters may also include `.`, `-`, `=`, or `^`.
- Quote and portfolio provider failures are reported through `missing`, `rate_limited`, or `skipped` fields where applicable. News fetch failures are reported by `some_feeds_failed`.
- Empty market history is returned as an empty record list. News results may be empty if no items are available.
- This server is read-only and does not provide personalized financial recommendations.
