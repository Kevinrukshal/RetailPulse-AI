# Database Design

## Source-of-truth tables

| Table | Grain | Purpose |
|---|---|---|
| `customers` | one customer | Current customer and geography attributes |
| `products` | one product | Current category hierarchy and product name |
| `orders` | one order | Customer, order date, and ship date |
| `order_items` | one source line | Sales, profit, quantity, discount, lineage, stable key |
| `etl_runs` | one execution | Status, duration, source hash, row counts, quality score |
| `data_quality_results` | one ETL run | Detailed validation and warning counts |
| `rejected_records` | one invalid source row | Original payload and all rejection reasons |

Foreign keys protect business relationships; checks enforce valid date order, non-negative sales,
positive quantity, discounts from 0 to 1, valid audit status, and valid quality percentages.

## Analytical views

`executive_summary`, `monthly_performance`, `product_performance`, `customer_performance`,
`regional_performance`, and `profit_leakage` provide reporting grains. View definitions live in
`sql/views.sql` and are installed by Alembic migration `0002`.

## Migrations

```powershell
docker compose exec api alembic current
docker compose exec api alembic upgrade head
docker compose exec api alembic check
```

Create future revisions with `alembic revision -m "description"`, review generated SQL, and test
both upgrade and downgrade on disposable data before merging. Never edit a migration already
applied to a shared environment.

## Idempotency and transactions

Dimensions and order headers are upserted. `order_items.order_item_key` is unique, so a rerun of
the identical source inserts no duplicate facts. Loading dimensions, facts, audit results, and
rejections is transactional; a database error rolls the execution back rather than exposing a
partially loaded business state.

## Backup and access

The Compose named volume is durable across container recreation but is not a backup. For any real
deployment, schedule `pg_dump`, test restoration, encrypt stored copies, and give the API/BI users
only required privileges. Synthetic sample data contains no real customer information.
