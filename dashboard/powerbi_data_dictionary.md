# Power BI Data Dictionary

Monetary columns use the source file's unspecified currency unit. The sample does not assert a
real currency or business. Ratios are decimals (`0.2861` = `28.61%`).

## Analytical views

### `monthly_performance`

Grain: one row per calendar month containing an order.

| Field | Definition | Default use |
|---|---|---|
| `month_start` | First day of order month | Date axis; no summary |
| `revenue`, `profit` | Monthly line sales and profit | Sum / currency |
| `profit_margin` | Profit divided by revenue | Percentage; never sum |
| `units`, `orders` | Quantity and distinct order count | Sum across disjoint months |
| `customers` | Distinct monthly customers | Never sum for multi-month uniques |
| `month_over_month_growth_pct` | Growth versus prior available month, percentage points | Never sum |
| `year_over_year_growth_pct` | Growth versus the row 12 months earlier, percentage points | Never sum |

### `product_performance`

Grain: one row per product across loaded history.

| Field | Definition | Default use |
|---|---|---|
| `product_id`, `product_name` | Product business key and label | Key / label |
| `category`, `subcategory` | Product hierarchy | Slicer / drill-down |
| `revenue`, `profit` | Lifetime sales and profit | Sum / currency |
| `profit_margin`, `average_discount` | Product margin and mean line discount | Percentage; never sum |
| `units`, `orders` | Quantity and distinct product order count | Product-level values |
| `revenue_rank`, `profit_rank` | Dense all-product rank | Never summarize |
| `is_loss_making` | Lifetime product profit is negative | Filter / warning |

### `customer_performance`

Grain: one row per customer across loaded history.

| Field | Definition | Default use |
|---|---|---|
| `customer_id`, `customer_name` | Customer key and label | Key / label |
| `segment`, `region` | Current customer attributes | Slicer / group |
| `lifetime_revenue`, `lifetime_profit` | Customer lifetime value | Sum / currency |
| `purchase_frequency` | Distinct lifetime orders | Customer-level value |
| `last_purchase_date`, `recency_days` | Latest order and days from dataset maximum date | Date / no summary |
| `average_order_value` | Lifetime revenue divided by orders | Currency; never sum |
| `recency_score`, `frequency_score`, `monetary_score` | Relative quintile scores from 1 to 5 | Category / tooltip |
| `rfm_segment` | Champions, Loyal, At Risk, New, or Developing | Slicer / legend |

### `regional_performance`

Grain: one row per customer region across loaded history.

| Field | Definition | Default use |
|---|---|---|
| `region` | Current customer region | Key / label |
| `revenue`, `profit` | Regional sales and profit | Sum / currency |
| `profit_margin` | Regional profit divided by revenue | Percentage; never sum |
| `orders`, `customers`, `units` | Distinct orders, distinct customers, and quantity | KPI / bar value |
| `revenue_rank` | Revenue rank across regions | Never summarize |

### `profit_leakage`

Grain: one qualifying order-item line. A line qualifies when profit is negative, discount is
above 20%, or margin is below 5%. Conditions can overlap, but each line receives one prioritized
reason: loss-making, excessive discount, then weak margin.

| Field | Definition | Default use |
|---|---|---|
| `order_item_key` | Stable fact-line key | Key; no summary |
| `order_id`, `order_date` | Order key and date | Drill-through / date axis |
| `region` | Customer region | Slicer |
| `product_id`, `product_name` | Product key and label | Drill-through / group |
| `category`, `subcategory` | Product hierarchy | Slicer / drill-down |
| `sales`, `profit`, `quantity` | Qualifying line metrics | Sum |
| `profit_margin`, `discount` | Line margin and discount | Percentage |
| `leakage_reason` | Prioritized inclusion reason | Legend / slicer |

## Optional normalized model

Use `order_items` as the fact. Relate `orders[order_id]` 1:* to `order_items[order_id]`,
`customers[customer_id]` 1:* to `orders[customer_id]`, and `products[product_id]` 1:* to
`order_items[product_id]`. Use single-direction dimension-to-fact filters. Add a Date table with
`Date[Date]` 1:* to `orders[order_date]`.

`etl_runs`, `data_quality_results`, and `rejected_records` are audit tables. Keep them outside
the business model unless creating a separate data-quality page.
