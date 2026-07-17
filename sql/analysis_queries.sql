-- Documented portfolio query library. Results from sample_sales.csv are demonstrations.

-- query: 01_executive_summary
SELECT * FROM executive_summary;

-- query: 02_monthly_revenue_profit
SELECT month_start, revenue, profit, profit_margin
FROM monthly_performance
ORDER BY month_start;

-- query: 03_quarterly_trends
SELECT
    DATE_TRUNC('quarter', o.order_date)::date AS quarter_start,
    ROUND(SUM(oi.sales), 2) AS revenue,
    ROUND(SUM(oi.profit), 2) AS profit,
    ROUND(SUM(oi.profit) / NULLIF(SUM(oi.sales), 0), 6) AS profit_margin
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
GROUP BY DATE_TRUNC('quarter', o.order_date)::date
ORDER BY quarter_start;

-- query: 04_month_over_month_growth
SELECT month_start, revenue, month_over_month_growth_pct
FROM monthly_performance
ORDER BY month_start;

-- query: 05_year_over_year_growth
SELECT month_start, revenue, year_over_year_growth_pct
FROM monthly_performance
WHERE year_over_year_growth_pct IS NOT NULL
ORDER BY month_start;

-- query: 06_top_products_by_revenue
SELECT product_id, product_name, category, revenue, profit, revenue_rank
FROM product_performance
ORDER BY revenue_rank, product_id
LIMIT 10;

-- query: 07_top_products_by_profit
SELECT product_id, product_name, category, revenue, profit, profit_rank
FROM product_performance
ORDER BY profit_rank, product_id
LIMIT 10;

-- query: 08_loss_making_products
SELECT product_id, product_name, category, revenue, profit, profit_margin
FROM product_performance
WHERE is_loss_making
ORDER BY profit, product_id;

-- query: 09_category_performance
SELECT
    p.category,
    ROUND(SUM(oi.sales), 2) AS revenue,
    ROUND(SUM(oi.profit), 2) AS profit,
    ROUND(SUM(oi.profit) / NULLIF(SUM(oi.sales), 0), 6) AS profit_margin,
    RANK() OVER (ORDER BY SUM(oi.profit) DESC) AS profit_rank
FROM products AS p
JOIN order_items AS oi ON oi.product_id = p.product_id
GROUP BY p.category
ORDER BY profit_rank;

-- query: 10_subcategory_performance
SELECT
    p.category,
    p.subcategory,
    ROUND(SUM(oi.sales), 2) AS revenue,
    ROUND(SUM(oi.profit), 2) AS profit,
    ROUND(SUM(oi.profit) / NULLIF(SUM(oi.sales), 0), 6) AS profit_margin
FROM products AS p
JOIN order_items AS oi ON oi.product_id = p.product_id
GROUP BY p.category, p.subcategory
ORDER BY profit ASC, p.category, p.subcategory;

-- query: 11_discount_impact
SELECT
    CASE
        WHEN discount = 0 THEN 'None'
        WHEN discount <= 0.10 THEN 'Low'
        WHEN discount <= 0.20 THEN 'Medium'
        ELSE 'High'
    END AS discount_band,
    COUNT(*)::integer AS order_lines,
    ROUND(AVG(discount), 6) AS average_discount,
    ROUND(SUM(sales), 2) AS revenue,
    ROUND(SUM(profit), 2) AS profit,
    ROUND(SUM(profit) / NULLIF(SUM(sales), 0), 6) AS profit_margin
FROM order_items
GROUP BY discount_band
ORDER BY MIN(discount);

-- query: 12_customer_lifetime_value
SELECT
    customer_id,
    customer_name,
    rfm_segment,
    lifetime_revenue,
    lifetime_profit,
    purchase_frequency,
    average_order_value
FROM customer_performance
ORDER BY lifetime_revenue DESC, customer_id
LIMIT 20;

-- query: 13_rfm_segment_distribution
SELECT
    rfm_segment,
    COUNT(*)::integer AS customers,
    ROUND(SUM(lifetime_revenue), 2) AS revenue,
    ROUND(SUM(lifetime_profit), 2) AS profit
FROM customer_performance
GROUP BY rfm_segment
ORDER BY revenue DESC;

-- query: 14_at_risk_customers
SELECT
    customer_id,
    customer_name,
    region,
    recency_days,
    purchase_frequency,
    lifetime_revenue,
    lifetime_profit
FROM customer_performance
WHERE rfm_segment = 'At Risk'
ORDER BY lifetime_revenue DESC, recency_days DESC;

-- query: 15_regional_performance
SELECT region, revenue, profit, profit_margin, orders, customers, revenue_rank
FROM regional_performance
ORDER BY revenue_rank;

-- query: 16_state_performance
SELECT
    c.state,
    c.region,
    ROUND(SUM(oi.sales), 2) AS revenue,
    ROUND(SUM(oi.profit), 2) AS profit,
    ROUND(SUM(oi.profit) / NULLIF(SUM(oi.sales), 0), 6) AS profit_margin
FROM customers AS c
JOIN orders AS o ON o.customer_id = c.customer_id
JOIN order_items AS oi ON oi.order_id = o.order_id
GROUP BY c.state, c.region
ORDER BY profit ASC, c.state;

-- query: 17_loss_making_orders
WITH order_profit AS (
    SELECT
        o.order_id,
        o.order_date,
        c.region,
        SUM(oi.sales) AS revenue,
        SUM(oi.profit) AS profit,
        AVG(oi.discount) AS average_discount
    FROM orders AS o
    JOIN customers AS c ON c.customer_id = o.customer_id
    JOIN order_items AS oi ON oi.order_id = o.order_id
    GROUP BY o.order_id, o.order_date, c.region
)
SELECT
    order_id,
    order_date,
    region,
    ROUND(revenue, 2) AS revenue,
    ROUND(profit, 2) AS profit,
    ROUND(average_discount, 6) AS average_discount
FROM order_profit
WHERE profit < 0
ORDER BY profit, order_id;

-- query: 18_high_revenue_low_margin_products
WITH product_metrics AS (
    SELECT
        p.product_id,
        p.product_name,
        SUM(oi.sales) AS revenue,
        SUM(oi.profit) AS profit,
        SUM(oi.profit) / NULLIF(SUM(oi.sales), 0) AS profit_margin
    FROM products AS p
    JOIN order_items AS oi ON oi.product_id = p.product_id
    GROUP BY p.product_id, p.product_name
), threshold AS (
    SELECT PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY revenue) AS revenue_p75
    FROM product_metrics
)
SELECT
    product_id,
    product_name,
    ROUND(revenue, 2) AS revenue,
    ROUND(profit, 2) AS profit,
    ROUND(profit_margin, 6) AS profit_margin
FROM product_metrics
CROSS JOIN threshold
WHERE revenue >= revenue_p75 AND profit_margin < 0.10
ORDER BY revenue DESC;

-- query: 19_customer_revenue_concentration
WITH ranked_customers AS (
    SELECT
        customer_id,
        customer_name,
        lifetime_revenue,
        SUM(lifetime_revenue) OVER () AS total_revenue,
        SUM(lifetime_revenue) OVER (
            ORDER BY lifetime_revenue DESC, customer_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_revenue
    FROM customer_performance
)
SELECT
    customer_id,
    customer_name,
    lifetime_revenue,
    ROUND(100 * cumulative_revenue / NULLIF(total_revenue, 0), 2) AS cumulative_revenue_pct
FROM ranked_customers
ORDER BY lifetime_revenue DESC, customer_id
LIMIT 20;

-- query: 20_category_monthly_share
WITH monthly_category AS (
    SELECT
        DATE_TRUNC('month', o.order_date)::date AS month_start,
        p.category,
        SUM(oi.sales) AS category_revenue
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    JOIN products AS p ON p.product_id = oi.product_id
    GROUP BY DATE_TRUNC('month', o.order_date)::date, p.category
)
SELECT
    month_start,
    category,
    ROUND(category_revenue, 2) AS category_revenue,
    ROUND(
        100 * category_revenue / NULLIF(SUM(category_revenue) OVER (PARTITION BY month_start), 0),
        2
    ) AS monthly_revenue_share_pct
FROM monthly_category
ORDER BY month_start, category_revenue DESC;

-- query: 21_profit_leakage_summary
SELECT
    leakage_reason,
    COUNT(*)::integer AS affected_lines,
    ROUND(SUM(sales), 2) AS affected_revenue,
    ROUND(SUM(profit), 2) AS affected_profit
FROM profit_leakage
GROUP BY leakage_reason
ORDER BY affected_profit;

-- query: 22_latest_data_quality
SELECT
    er.etl_run_id,
    er.source_file,
    er.completed_at,
    er.total_rows,
    er.valid_rows,
    er.invalid_rows,
    er.quality_score,
    dqr.issue_counts
FROM etl_runs AS er
JOIN data_quality_results AS dqr ON dqr.etl_run_id = er.etl_run_id
WHERE er.status = 'completed'
ORDER BY er.completed_at DESC
LIMIT 1;
