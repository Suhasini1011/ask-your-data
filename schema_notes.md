# Olist analytics database: schema notes

PostgreSQL. All tables are in the `analytics` schema: always write `analytics.table_name`.
Data: Brazilian eCommerce marketplace orders, 2016 to 2018. Money is in Brazilian reais (R$).

## Tables

### analytics.fact_orders: one row per order (99,441 rows)
- order_id (text, primary key)
- customer_unique_id (text): the real customer; joins to dim_customer
- order_status (text): delivered, shipped, canceled, unavailable, invoiced, processing, created, approved
- purchase_date (date): joins to dim_date.date_key
- purchase_ts, approved_ts, carrier_ts, delivered_ts (timestamp): delivered_ts is NULL if never delivered
- estimated_delivery_date (date): the delivery date promised to the customer
- items_count, sellers_count (integer)
- items_value (numeric): sum of item prices in the order
- freight_value (numeric): sum of shipping costs in the order
- payment_value (numeric): what the customer paid (includes freight and any instalment interest)
- max_installments (integer), main_payment_type (text): credit_card, boleto, voucher, debit_card
- review_id (text), review_score (integer 1 to 5, NULL if no review), has_review_comment (boolean)
- delivery_days (numeric): days from purchase to delivery
- days_vs_estimate (integer): delivered date minus promised date; positive means late
- is_late (boolean): delivered after the promised date; NULL if not delivered
- has_date_issue (boolean): impossible dates in the source data
- purchase_occasion (integer): 1 for a customer's first purchase day, 2 for their second, and so on
- in_analysis_window (boolean): true for purchases from Jan 2017 to Aug 2018

### analytics.fact_order_items: one row per item sold (112,650 rows)
- order_id, order_item_id (primary key together); order_id joins to fact_orders
- product_id (joins to dim_product), seller_id (joins to dim_seller)
- customer_unique_id, purchase_date, order_status, review_score, is_late, in_analysis_window: copied from the order
- shipping_limit_ts (timestamp)
- price (numeric): item price; freight_value (numeric): item shipping cost

### analytics.dim_customer: one row per real customer (96,096 rows)
- customer_unique_id (primary key), zip_prefix, city, state (2-letter code)

### analytics.dim_product: one row per product (32,951 rows)
- product_id (primary key)
- category (text): English category name, 'unknown' if missing; category_portuguese (text)
- photos_qty, weight_g, length_cm, height_cm, width_cm, description_length (integer)

### analytics.dim_seller: one row per seller (3,095 rows)
- seller_id (primary key), zip_prefix, city, state (2-letter code)

### analytics.dim_date: one row per day, 2016 to 2018
- date_key (date, primary key), year, quarter, month (1 to 12), month_name ('Jan'), year_month ('2017-01')
- day_of_week (1 = Monday to 7 = Sunday), day_name, is_weekend (boolean), in_analysis_window (boolean)

## Business rules (always follow these)

1. **Time window:** unless the question asks about other dates, filter to `in_analysis_window = true`.
   2016 and Sep to Oct 2018 are too thin to use.
2. **Revenue** means item revenue: `SUM(price)` from fact_order_items, excluding
   `order_status IN ('canceled', 'unavailable')`. Use fact_order_items for revenue by category or seller.
3. **Customer spend** means `SUM(payment_value)` from fact_orders.
4. **Late delivery rate:** among orders with `order_status = 'delivered' AND delivered_ts IS NOT NULL`,
   the share where `is_late = true`.
5. **Review scores:** a low review score means `review_score <= 2`. Averages AND percentages of
   review scores use only orders that have a review (`review_score IS NOT NULL`) as the base,
   because an order without a review cannot have a low score.
6. **Repeat customer:** a customer who bought on 2 or more different days
   (`COUNT(DISTINCT purchase_date) > 1`), excluding canceled and unavailable orders.
   Do not count customers with 2+ orders, because one checkout can create several orders.
7. **Lost sales:** `SUM(payment_value)` of orders with `order_status IN ('canceled', 'unavailable')`.
8. To count orders, use fact_orders. Never count orders by counting rows of fact_order_items.
9. When joining items to orders, aggregate items to order level first, to avoid double counting.
10. States are 2-letter codes, for example SP = São Paulo, RJ = Rio de Janeiro, MG = Minas Gerais.
11. **Delivered orders** always means `order_status = 'delivered' AND delivered_ts IS NOT NULL`,
    for counts as well as rates. 8 orders are marked delivered but have no delivery date
    (a data quality issue); exclude them.