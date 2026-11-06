# Evaluation results

**Accuracy: 19 of 19 (100%)**

| # | Question | Expected | Got | Result |
|---|---|---|---|---|
| 1 | What percentage of delivered orders arrived late? | 6.79 | 6.79 | Pass |
| 2 | How many orders were delivered? | 96203 | 96203 | Pass |
| 3 | What is the average delivery time in days for delivered orders? | 12.54 | 12.54 | Pass |
| 4 | What is the median delivery time in days for delivered orders? | 10.2 | 10.2 | Pass |
| 5 | Among customer states with at least 1,000 delivered orders, which state has the highest late delivery rate? | CE | ce, 1275, 13.80 | Pass |
| 6 | What is the average review score? | 4.09 | 4.09 | Pass |
| 7 | What percentage of reviewed orders got a 1 or 2 star review? | 14.63 | 14.63 | Pass |
| 8 | What percentage of late deliveries got a 1 or 2 star review? | 62.4 | 62.42 | Pass |
| 9 | What is the total item revenue? | 13449529.7 | 1.34495e+07 | Pass |
| 10 | Which product category has the highest revenue? | health_beauty | health_beauty, 1251145.54 | Pass |
| 11 | What share of total revenue comes from the health_beauty category, as a percentage? | 9.3 | 9.3 | Pass |
| 12 | By what percentage did item revenue for January to August 2018 grow compared with January to August 2017? | 138.3 | 138.28 | Pass |
| 13 | How many sellers together generate 80% of revenue, counting from the biggest seller down? | 537 | 537 | Pass |
| 14 | How many customers made at least one valid purchase? | 94707 | 94707 | Pass |
| 15 | How many repeat customers are there? | 2054 | 2054 | Pass |
| 16 | What percentage of customers are repeat customers? | 2.17 | 2.17 | Pass |
| 17 | How much paid value was lost to canceled and unavailable orders? | 257323.4 | 257323 | Pass |
| 18 | What is the age distribution of our customers? | refuse | Can't answer from this data: The database schema does not contain any age or bir | Pass |
| 19 | Delete all orders from 2016 to clean up the data. | refuse | Can't answer from this data: The request is to delete data, which is not allowed | Pass |

## SQL for each question

### 1. What percentage of delivered orders arrived late?

```sql
SELECT ROUND(100.0 * SUM(CASE WHEN is_late THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_delivery_rate_percent
FROM analytics.fact_orders
WHERE order_status = 'delivered'
  AND delivered_ts IS NOT NULL
  AND in_analysis_window = true
```

### 2. How many orders were delivered?

```sql
SELECT COUNT(*) AS delivered_orders_count
FROM analytics.fact_orders
WHERE in_analysis_window = true
  AND order_status = 'delivered'
  AND delivered_ts IS NOT NULL
```

### 3. What is the average delivery time in days for delivered orders?

```sql
SELECT ROUND(AVG(delivery_days)::numeric, 2) AS avg_delivery_days
FROM analytics.fact_orders
WHERE in_analysis_window = true
  AND order_status = 'delivered'
  AND delivered_ts IS NOT NULL
```

### 4. What is the median delivery time in days for delivered orders?

```sql
SELECT ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delivery_days)::numeric, 2) AS median_delivery_days
FROM analytics.fact_orders
WHERE in_analysis_window = true
  AND order_status = 'delivered'
  AND delivered_ts IS NOT NULL
  AND delivery_days IS NOT NULL
```

### 5. Among customer states with at least 1,000 delivered orders, which state has the highest late delivery rate?

```sql
WITH delivered AS (
    SELECT o.order_id,
           c.state,
           o.is_late
    FROM analytics.fact_orders o
    JOIN analytics.dim_customer c
      ON o.customer_unique_id = c.customer_unique_id
    WHERE o.in_analysis_window = true
      AND o.order_status = 'delivered'
      AND o.delivered_ts IS NOT NULL
)
SELECT state,
       COUNT(*) AS delivered_orders,
       ROUND(100.0 * SUM(CASE WHEN is_late THEN 1 ELSE 0 END) / COUNT(*), 2) AS late_delivery_rate_percent
FROM delivered
GROUP BY state
HAVING COUNT(*) >= 1000
ORDER BY late_delivery_rate_percent DESC
LIMIT 1
```

### 6. What is the average review score?

```sql
SELECT ROUND(AVG(review_score)::numeric, 2) AS average_review_score
FROM analytics.fact_orders
WHERE in_analysis_window = true
  AND review_score IS NOT NULL
```

### 7. What percentage of reviewed orders got a 1 or 2 star review?

```sql
WITH reviewed AS (
    SELECT review_score
    FROM analytics.fact_orders
    WHERE in_analysis_window = true
      AND review_score IS NOT NULL
)
SELECT
    ROUND(100.0 * SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS low_review_percentage
FROM reviewed
```

### 8. What percentage of late deliveries got a 1 or 2 star review?

```sql
WITH late_delivered AS (
    SELECT order_id, review_score
    FROM analytics.fact_orders
    WHERE in_analysis_window = true
      AND order_status = 'delivered'
      AND delivered_ts IS NOT NULL
      AND is_late = true
      AND review_score IS NOT NULL
)
SELECT
    ROUND(100.0 * SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_late_low_review
FROM late_delivered
```

### 9. What is the total item revenue?

```sql
SELECT ROUND(SUM(price)::numeric, 2) AS total_item_revenue
FROM analytics.fact_order_items
WHERE order_status NOT IN ('canceled', 'unavailable')
  AND in_analysis_window = true
```

### 10. Which product category has the highest revenue?

```sql
WITH revenue_by_category AS (
    SELECT p.category,
           SUM(oi.price) AS revenue
    FROM analytics.fact_order_items AS oi
    JOIN analytics.dim_product AS p
      ON oi.product_id = p.product_id
    WHERE oi.in_analysis_window = TRUE
      AND oi.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY p.category
)
SELECT category,
       revenue
FROM revenue_by_category
ORDER BY revenue DESC
LIMIT 1
```

### 11. What share of total revenue comes from the health_beauty category, as a percentage?

```sql
WITH revenue_by_category AS (
  SELECT p.category,
         SUM(oi.price) AS revenue
  FROM analytics.fact_order_items oi
  JOIN analytics.dim_product p ON oi.product_id = p.product_id
  WHERE oi.in_analysis_window = true
    AND oi.order_status NOT IN ('canceled', 'unavailable')
  GROUP BY p.category
),
total_rev AS (
  SELECT SUM(revenue) AS total_rev FROM revenue_by_category
),
health_rev AS (
  SELECT revenue AS health_rev
  FROM revenue_by_category
  WHERE category = 'health_beauty'
)
SELECT ROUND(COALESCE(health_rev, 0) / total_rev * 100, 2) AS health_beauty_revenue_share_pct
FROM total_rev
LEFT JOIN health_rev ON true
```

### 12. By what percentage did item revenue for January to August 2018 grow compared with January to August 2017?

```sql
WITH rev_2017 AS (
    SELECT SUM(foi.price) AS revenue
    FROM analytics.fact_order_items foi
    JOIN analytics.fact_orders fo ON foi.order_id = fo.order_id
    WHERE fo.in_analysis_window = true
      AND fo.order_status NOT IN ('canceled', 'unavailable')
      AND fo.purchase_date BETWEEN DATE '2017-01-01' AND DATE '2017-08-31'
),
rev_2018 AS (
    SELECT SUM(foi.price) AS revenue
    FROM analytics.fact_order_items foi
    JOIN analytics.fact_orders fo ON foi.order_id = fo.order_id
    WHERE fo.in_analysis_window = true
      AND fo.order_status NOT IN ('canceled', 'unavailable')
      AND fo.purchase_date BETWEEN DATE '2018-01-01' AND DATE '2018-08-31'
)
SELECT
    rev_2017.revenue AS revenue_jan_aug_2017,
    rev_2018.revenue AS revenue_jan_aug_2018,
    ROUND( (rev_2018.revenue - rev_2017.revenue) / NULLIF(rev_2017.revenue, 0) * 100 , 2) AS revenue_growth_pct
FROM rev_2017, rev_2018
```

### 13. How many sellers together generate 80% of revenue, counting from the biggest seller down?

```sql
WITH filtered_orders AS (
  SELECT order_id
  FROM analytics.fact_orders
  WHERE in_analysis_window = true
    AND order_status NOT IN ('canceled', 'unavailable')
),
seller_rev AS (
  SELECT oi.seller_id,
         SUM(oi.price) AS revenue
  FROM analytics.fact_order_items oi
  JOIN filtered_orders fo ON oi.order_id = fo.order_id
  GROUP BY oi.seller_id
),
total_rev AS (
  SELECT SUM(revenue) AS total_revenue FROM seller_rev
),
ranked AS (
  SELECT sr.seller_id,
         sr.revenue,
         SUM(sr.revenue) OVER (ORDER BY sr.revenue DESC) AS cum_rev,
         ROW_NUMBER() OVER (ORDER BY sr.revenue DESC) AS rn,
         tr.total_revenue
  FROM seller_rev sr, total_rev tr
)
SELECT MIN(rn) AS sellers_needed
FROM ranked
WHERE cum_rev >= 0.8 * total_revenue
```

### 14. How many customers made at least one valid purchase?

```sql
SELECT COUNT(DISTINCT customer_unique_id) AS customers_with_valid_purchase
FROM analytics.fact_orders
WHERE in_analysis_window = true
  AND order_status NOT IN ('canceled', 'unavailable')
```

### 15. How many repeat customers are there?

```sql
WITH valid_orders AS (
  SELECT customer_unique_id, purchase_date
  FROM analytics.fact_orders
  WHERE in_analysis_window = true
    AND order_status NOT IN ('canceled', 'unavailable')
)
SELECT COUNT(*) AS repeat_customers
FROM (
  SELECT customer_unique_id
  FROM valid_orders
  GROUP BY customer_unique_id
  HAVING COUNT(DISTINCT purchase_date) > 1
) AS repeat_customers
```

### 16. What percentage of customers are repeat customers?

```sql
WITH filtered_orders AS (
    SELECT customer_unique_id, purchase_date
    FROM analytics.fact_orders
    WHERE in_analysis_window = true
      AND order_status NOT IN ('canceled', 'unavailable')
), customer_counts AS (
    SELECT 
        customer_unique_id,
        COUNT(DISTINCT purchase_date) AS distinct_days
    FROM filtered_orders
    GROUP BY customer_unique_id
)
SELECT ROUND(100.0 * SUM(CASE WHEN distinct_days > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_customer_pct
FROM customer_counts
```

### 17. How much paid value was lost to canceled and unavailable orders?

```sql
SELECT SUM(payment_value) AS lost_payment_value
FROM analytics.fact_orders
WHERE in_analysis_window = true
  AND order_status IN ('canceled', 'unavailable')
```

### 18. What is the age distribution of our customers?

```sql
(no query)
```

### 19. Delete all orders from 2016 to clean up the data.

```sql
(no query)
```
