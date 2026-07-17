# Browser dashboard

Open `http://localhost:8000` after starting Docker Compose. The service redirects to the bundled
dashboard, so no separate frontend server or Node.js installation is required.

## Import data

1. Click the upload area and select a `.csv` or `.xlsx` file (maximum 10 MB by default).
2. Select **Process file**.
3. Wait for the audited ETL result. Valid rows are loaded, invalid rows are quarantined, and the
   dashboard refreshes automatically.
4. Use the left navigation to inspect products, customers, regions, quality, and profit leakage.

The import uses the same required columns, aliases, validation rules, quality reporting, and stable
row keys as the command-line pipeline. Reprocessing the identical file does not duplicate sales
facts. The uploaded temporary copy is deleted after success or failure.

Configuration is environment-backed:

```text
UPLOAD_ENABLED=true
UPLOAD_MAX_MB=10
```

The dashboard is intended for trusted local use. There is no user authentication in this portfolio
release; disable upload or add an authenticated reverse proxy before exposing it to the internet.
