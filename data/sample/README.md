# Demonstration dataset

`sample_sales.csv` contains 750 deterministic synthetic retail order-line records generated
with seed `20260717`. It is designed for repeatable ETL, SQL, API, and Power BI testing.

The people, transactions, and resulting findings are fictional. Any insight derived from
this file must be labelled as a demonstration finding, not a real-world business claim.

Regenerate the sample and test fixtures from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\generate_sample_data.py
```
