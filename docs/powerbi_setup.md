# Power BI Setup and Verification

This guide builds the RetailPulse report in Power BI Desktop from local PostgreSQL. A `.pbix`
binary is intentionally not committed: the semantic model, measures, page design, and validation
steps are version-controlled instead.

## 1. Start and load the platform

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api python -m etl.pipeline --file data/sample/sample_sales.csv
docker compose ps
```

The second ETL run is safe and should insert zero duplicate facts.

## 2. Connect Power BI Desktop

1. Select **Get data > PostgreSQL database**.
2. Enter `localhost:5432` and the `POSTGRES_DB` database configured in `.env` (template default:
   `retailpulse`).
3. Choose **Import** mode. DirectQuery adds needless latency for this portfolio-sized dataset.
4. Authenticate with the local PostgreSQL credentials from `.env`; never store them in source
   control or screenshots.
5. Select the five analytical views listed in `dashboard/README.md`.
6. Optionally select `orders`, `order_items`, `customers`, and `products` for cross-view slicers
   and fact-level DAX.

If prompted, install the current 64-bit Npgsql provider recommended by Power BI and restart it.

## 3. Build the semantic model

For a views-only report, leave the views disconnected because each has a different grain. Joining
them by region, product, or month creates many-to-many paths and duplicated totals.

For the optional fact model:

```text
Date (1) -> (*) orders (1) -> (*) order_items (*) <- (1) products
                         ^
                         |
                    customers (1)
```

- Use single-direction dimension-to-fact filtering.
- Mark a contiguous Date table as the model's date table.
- Sort month names by month number and use year-month labels on trend axes.
- Hide audit columns from report view but retain business keys for drill-through.
- Disable automatic date/time to avoid hidden date tables.

```dax
Date =
VAR MinDate = MIN ( orders[order_date] )
VAR MaxDate = MAX ( orders[order_date] )
RETURN
ADDCOLUMNS (
    CALENDAR ( DATE ( YEAR ( MinDate ), 1, 1 ), DATE ( YEAR ( MaxDate ), 12, 31 ) ),
    "Year", YEAR ( [Date] ),
    "Month Number", MONTH ( [Date] ),
    "Month Name", FORMAT ( [Date], "MMM" ),
    "Year Month", FORMAT ( [Date], "yyyy-MM" ),
    "Quarter", "Q" & QUARTER ( [Date] )
)
```

Copy measures from `dashboard/measures.dax`. Prefer fact measures when normalized tables are
loaded and view alternatives for a views-only report.

## 4. Assemble report pages

### Executive Overview

- Cards: revenue, profit, margin, orders, customers, and average order value.
- Line/combo chart: monthly revenue and profit with MoM/YoY tooltips.
- Bar chart: revenue and profit by region.
- Slicers: date, region, category, and subcategory.

### Product Performance

- Matrix: category > subcategory > product with revenue, profit, margin, units, and rank.
- Scatter plot: average discount versus margin, sized by revenue.
- Bar charts: top-revenue and loss-making products.
- Conditional formatting for negative profit.

### Customer & Region

- Stacked bar: customer count and lifetime revenue by RFM segment.
- Table: customer, segment, region, revenue, profit, frequency, recency, and AOV.
- Prefer a regional bar chart to a map because region names alone can be geocoded incorrectly.
- Customer drill-through filtered by `customer_id`.

### Profit Leakage

- Cards: leakage line count and loss value.
- Bar chart: profit by leakage reason and category.
- Scatter plot: discount versus margin, sized by sales.
- Detail table: date, order, product, region, sales, discount, profit, and reason.

## 5. Reconcile the report

```powershell
docker compose exec db psql -U retail_user -d retailpulse -c "SELECT * FROM executive_summary;"
Invoke-RestMethod http://localhost:8000/api/v1/summary
```

The deterministic, unfiltered synthetic demonstration baseline is:

| KPI | Expected value |
|---|---:|
| Revenue | 597,016.99 |
| Profit | 170,830.64 |
| Profit margin | 28.6140% |
| Orders | 311 |
| Customers | 79 |
| Average order value | 1,919.67 |
| Average units per order | 10.56 |

If cards differ, inspect visual filters, relationship direction, accidental sums of ratios, and
whether the sample was regenerated with a different seed.

## 6. Refresh and security

- Desktop refresh needs the local containers running.
- Power BI Service would need an on-premises gateway or hosted database; neither is required here.
- Store credentials only in Power BI data-source settings, never in DAX, M, or this repository.
- A production BI identity should receive `SELECT` on approved views only.
- Keep the **Synthetic demonstration data** label visible in shared screenshots.
