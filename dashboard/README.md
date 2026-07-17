# RetailPulse Power BI Dashboard

This folder is the implementation handoff for a four-page Power BI report backed by the
PostgreSQL analytical views. The bundled data is synthetic demonstration content; dashboard
screenshots and portfolio commentary must not describe its outputs as real company results.

## Report pages

1. **Executive Overview** — revenue, profit, margin, orders, customers, average order value,
   monthly trends, and regional contribution.
2. **Product Performance** — category drill-down, top products, margin versus discount, and
   loss-making product flags.
3. **Customer & Region** — RFM segments, top customers, regional rank, frequency, recency,
   and customer value.
4. **Profit Leakage** — loss value, affected lines, leakage reason, discount bands, and an
   order/product drill-through table.

## Sources and model

Import `monthly_performance`, `product_performance`, `customer_performance`,
`regional_performance`, and `profit_leakage` with the PostgreSQL connector. Import `orders`,
`order_items`, `customers`, and `products` only when date-aware cross-filtering or custom
fact-grain measures are required.

The connection and verification procedure is in
[`docs/powerbi_setup.md`](../docs/powerbi_setup.md). Field grains are documented in
[`powerbi_data_dictionary.md`](powerbi_data_dictionary.md); reusable measures are in
[`measures.dax`](measures.dax).

## Visual standards

- Format money to two decimals and ratios as percentages; do not sum ratio fields.
- Use teal/green for positive profit, red for losses, and slate/gray for neutral comparisons.
- Add date, region, category, and subcategory slicers when the normalized model is imported.
- Show `Last Refreshed At` and **Synthetic demonstration data** on every page.
- Use labels or icons alongside color for loss and warning status.
- Validate KPI cards against `executive_summary` after every refresh.

## Acceptance checklist

- All views load without transformation errors.
- Revenue and profit reconcile to PostgreSQL and the API.
- Fields use the documented grain and aggregation behavior.
- Slicers do not create ambiguous relationship paths or duplicated totals.
- Empty states do not imply a real zero trend.
- The report contains no password, `.env` value, or personal data.
