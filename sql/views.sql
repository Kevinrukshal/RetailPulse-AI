-- Power BI-friendly analytical views. Normalized tables remain the source of truth.

-- statement
CREATE OR REPLACE VIEW executive_summary AS
WITH order_totals AS (
    SELECT
        o.order_id,
        o.customer_id,
        SUM(oi.sales) AS revenue,
        SUM(oi.profit) AS profit,
        SUM(oi.quantity) AS units
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    GROUP BY o.order_id, o.customer_id
)
SELECT
    COALESCE(ROUND(SUM(revenue), 2), 0) AS total_revenue,
    COALESCE(ROUND(SUM(profit), 2), 0) AS total_profit,
    COALESCE(ROUND(SUM(profit) / NULLIF(SUM(revenue), 0), 6), 0) AS profit_margin,
    COUNT(*)::integer AS total_orders,
    COUNT(DISTINCT customer_id)::integer AS unique_customers,
    COALESCE(ROUND(AVG(revenue), 2), 0) AS average_order_value,
    COALESCE(ROUND(AVG(units), 2), 0) AS average_units_per_order
FROM order_totals;

-- statement
CREATE OR REPLACE VIEW monthly_performance AS
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', o.order_date)::date AS month_start,
        SUM(oi.sales) AS revenue,
        SUM(oi.profit) AS profit,
        SUM(oi.quantity) AS units,
        COUNT(DISTINCT o.order_id) AS orders,
        COUNT(DISTINCT o.customer_id) AS customers
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    GROUP BY DATE_TRUNC('month', o.order_date)::date
), comparisons AS (
    SELECT
        monthly.*,
        LAG(revenue, 1) OVER (ORDER BY month_start) AS previous_month_revenue,
        LAG(revenue, 12) OVER (ORDER BY month_start) AS previous_year_revenue
    FROM monthly
)
SELECT
    month_start,
    ROUND(revenue, 2) AS revenue,
    ROUND(profit, 2) AS profit,
    ROUND(profit / NULLIF(revenue, 0), 6) AS profit_margin,
    units::integer,
    orders::integer,
    customers::integer,
    ROUND(
        100 * (revenue - previous_month_revenue) / NULLIF(previous_month_revenue, 0), 2
    ) AS month_over_month_growth_pct,
    ROUND(
        100 * (revenue - previous_year_revenue) / NULLIF(previous_year_revenue, 0), 2
    ) AS year_over_year_growth_pct
FROM comparisons;

-- statement
CREATE OR REPLACE VIEW product_performance AS
WITH product_metrics AS (
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        p.subcategory,
        SUM(oi.sales) AS revenue,
        SUM(oi.profit) AS profit,
        SUM(oi.quantity) AS units,
        COUNT(DISTINCT oi.order_id) AS orders,
        AVG(oi.discount) AS average_discount
    FROM products AS p
    JOIN order_items AS oi ON oi.product_id = p.product_id
    GROUP BY p.product_id, p.product_name, p.category, p.subcategory
)
SELECT
    product_id,
    product_name,
    category,
    subcategory,
    ROUND(revenue, 2) AS revenue,
    ROUND(profit, 2) AS profit,
    ROUND(profit / NULLIF(revenue, 0), 6) AS profit_margin,
    units::integer,
    orders::integer,
    ROUND(average_discount, 6) AS average_discount,
    DENSE_RANK() OVER (ORDER BY revenue DESC) AS revenue_rank,
    DENSE_RANK() OVER (ORDER BY profit DESC) AS profit_rank,
    (profit < 0) AS is_loss_making
FROM product_metrics;

-- statement
CREATE OR REPLACE VIEW customer_performance AS
WITH reference_date AS (
    SELECT MAX(order_date) AS max_order_date FROM orders
), customer_metrics AS (
    SELECT
        c.customer_id,
        c.customer_name,
        c.segment,
        c.region,
        SUM(oi.sales) AS lifetime_revenue,
        SUM(oi.profit) AS lifetime_profit,
        COUNT(DISTINCT o.order_id) AS purchase_frequency,
        MAX(o.order_date) AS last_purchase_date,
        SUM(oi.sales) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS average_order_value,
        (r.max_order_date - MAX(o.order_date))::integer AS recency_days
    FROM customers AS c
    JOIN orders AS o ON o.customer_id = c.customer_id
    JOIN order_items AS oi ON oi.order_id = o.order_id
    CROSS JOIN reference_date AS r
    GROUP BY c.customer_id, c.customer_name, c.segment, c.region, r.max_order_date
), scored AS (
    SELECT
        customer_metrics.*,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS recency_score,
        NTILE(5) OVER (ORDER BY purchase_frequency) AS frequency_score,
        NTILE(5) OVER (ORDER BY lifetime_revenue) AS monetary_score
    FROM customer_metrics
)
SELECT
    customer_id,
    customer_name,
    segment,
    region,
    ROUND(lifetime_revenue, 2) AS lifetime_revenue,
    ROUND(lifetime_profit, 2) AS lifetime_profit,
    purchase_frequency::integer,
    last_purchase_date,
    ROUND(average_order_value, 2) AS average_order_value,
    recency_days,
    recency_score,
    frequency_score,
    monetary_score,
    CASE
        WHEN recency_score >= 4 AND frequency_score >= 4 AND monetary_score >= 4
            THEN 'Champions'
        WHEN frequency_score >= 4 AND monetary_score >= 3 THEN 'Loyal Customers'
        WHEN recency_score <= 2 AND frequency_score >= 3 THEN 'At Risk'
        WHEN recency_score >= 4 AND frequency_score <= 2 THEN 'New Customers'
        ELSE 'Developing'
    END AS rfm_segment
FROM scored;

-- statement
CREATE OR REPLACE VIEW regional_performance AS
SELECT
    c.region,
    ROUND(SUM(oi.sales), 2) AS revenue,
    ROUND(SUM(oi.profit), 2) AS profit,
    ROUND(SUM(oi.profit) / NULLIF(SUM(oi.sales), 0), 6) AS profit_margin,
    COUNT(DISTINCT o.order_id)::integer AS orders,
    COUNT(DISTINCT c.customer_id)::integer AS customers,
    SUM(oi.quantity)::integer AS units,
    RANK() OVER (ORDER BY SUM(oi.sales) DESC) AS revenue_rank
FROM customers AS c
JOIN orders AS o ON o.customer_id = c.customer_id
JOIN order_items AS oi ON oi.order_id = o.order_id
GROUP BY c.region;

-- statement
CREATE OR REPLACE VIEW profit_leakage AS
SELECT
    oi.order_item_key,
    o.order_id,
    o.order_date,
    c.region,
    p.product_id,
    p.product_name,
    p.category,
    p.subcategory,
    oi.sales,
    oi.profit,
    ROUND(oi.profit / NULLIF(oi.sales, 0), 6) AS profit_margin,
    oi.discount,
    oi.quantity,
    CASE
        WHEN oi.profit < 0 THEN 'Loss-making line'
        WHEN oi.discount > 0.20 THEN 'Excessive discount'
        ELSE 'Weak margin'
    END AS leakage_reason
FROM order_items AS oi
JOIN orders AS o ON o.order_id = oi.order_id
JOIN customers AS c ON c.customer_id = o.customer_id
JOIN products AS p ON p.product_id = oi.product_id
WHERE oi.profit < 0
   OR oi.discount > 0.20
   OR oi.profit / NULLIF(oi.sales, 0) < 0.05;
