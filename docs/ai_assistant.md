# Guarded AI Business Assistant

The optional assistant explains RetailPulse analytics; it does not generate or execute SQL. It is
disabled by default and the platform remains fully operational without an API key or AI package.

## Request flow

```text
question -> deterministic intent -> approved SQL template -> read-only PostgreSQL
         -> bounded rows + approved documentation -> OpenAI narrator -> grounded answer
```

Supported intents are loss-making product lines, highest regional margin, last-quarter revenue,
top customers by profit, discount impact, and categories to investigate. Unsupported questions
return `422` with the approved catalog instead of falling through to free-form SQL.

## Safety controls

- User text never enters SQL. A regular-expression router selects an enum, and that enum selects
  one static query from `ai/safe_sql.py`.
- Every query is `SELECT`-only, has a bound limit of at most 20 rows, executes in a read-only
  transaction, and receives a PostgreSQL statement timeout.
- Only `orders`, `order_items`, `product_performance`, `customer_performance`,
  `regional_performance`, and `profit_leakage` appear in the approved catalog.
- Local retrieval reads only five hardcoded repository documents, resolves paths below the project
  root, and sends bounded excerpts.
- The provider receives structured query evidence and documentation after SQL has executed. Its
  instructions prohibit SQL and unsupported numerical claims.
- Responses return the exact structured data and source names alongside the narrative, with an
  explicit synthetic-demonstration flag.
- Provider failures return safe `502`/`503` messages without keys, SQL, or stack traces.

## Enable locally

Edit the untracked `.env` file:

```env
INSTALL_AI=true
AI_ENABLED=true
AI_PROVIDER=openai
OPENAI_API_KEY=your_key_from_a_secret_store
AI_MODEL=gpt-5.6-luna
AI_ROW_LIMIT=10
AI_QUERY_TIMEOUT_MS=2000
```

Then rebuild because the OpenAI SDK is an optional dependency:

```powershell
docker compose up --build -d api
Invoke-RestMethod http://localhost:8000/api/v1/assistant/status
$body = @{ question = "Which products lost the most money?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/assistant/query `
  -ContentType application/json -Body $body
```

For a local Python environment, install `.[dev,ai]`. The provider uses the OpenAI Responses API
and its `output_text` helper, following the official
[text generation guide](https://developers.openai.com/api/docs/guides/text). The model remains an
environment setting; consult the official [model catalog](https://developers.openai.com/api/docs/models)
before changing it.

## Test strategy

Automated tests never call an external model. They use a fake narrator while exercising all six
approved queries against PostgreSQL, and a fake OpenAI client to verify the Responses API payload.
Prompt-injection test text proves that hostile instructions cannot change the selected query.

## Limitations

Intent routing is deliberately narrow and English-oriented. The local retriever is lexical rather
than embedding-based. Answers inherit the source data's limitations and must not be treated as
causal recommendations. Add a new intent only by reviewing its question patterns, fixed query,
expected grain, source documentation, result validation, and tests.

## Local access and data protection

See [local access setup](deployment.md#local-access-and-data-protection) for required API tokens,
loopback ports, upload limits, and explicit AI sharing permission.
