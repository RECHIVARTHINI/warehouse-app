# Deploy StockDesk to Azure

This repository's original [README](README.md) covers AWS. This guide deploys the same React + FastAPI + PostgreSQL app to Azure.

## Azure architecture

- **Azure Static Web Apps** hosts the Vite frontend.
- **Azure App Service (Linux)** runs the FastAPI backend.
- **Azure Database for PostgreSQL Flexible Server** stores products and stock alerts.

These workflows deploy application code from GitHub. They do not create Azure resources or configure the database/network for you.

## 1. Create PostgreSQL Flexible Server

In the Azure portal, create an Azure Database for PostgreSQL Flexible Server and a database named `inventory`. Choose the region and workload tier appropriate for your use. Networking is selected at creation: for a quick demo, public access with a narrow firewall allowlist is easiest; for production, configure private networking so only the app can reach the database. Do not enable unrestricted public access.

Record the server hostname, database name, admin username, and password. The app uses TLS for Azure PostgreSQL. Build the connection string in this shape (URL-encode special characters in the password):

```text
postgresql+psycopg2://USERNAME:URL_ENCODED_PASSWORD@SERVER.postgres.database.azure.com:5432/inventory?sslmode=require
```

## 2. Create the FastAPI App Service

Create a **Linux** App Service using a supported Python runtime (Python 3.13 works with the explicit startup command below). In Deployment Center, connect this GitHub repository if desired, or use the included GitHub Actions workflow described below.

Set these App Service application settings under **Settings → Environment variables**:

| Name | Value |
|---|---|
| `DATABASE_URL` | The PostgreSQL connection string above |
| `CORS_ORIGINS` | The exact Static Web Apps origin, for example `https://happy-field-123.azurestaticapps.net` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

Set **Configuration → General settings → Startup Command** to:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

The App Service package root must be the `backend` directory, which contains `main.py` and `requirements.txt`. App Service installs the requirements during deployment. Do not put credentials in this repository.

After creating the frontend (next step), return here and set `CORS_ORIGINS` to its actual URL, then save/restart the API.

## 3. Create the Static Web App

Create an Azure Static Web App connected to this GitHub repo. The frontend workflow is already configured for this monorepo:

- App location: `frontend`
- API location: blank
- Output location: `dist`
- Deployment branch: `main`

If Azure creates its own workflow file, use either that workflow or the included `.github/workflows/azure-frontend.yml`, not two competing deployments.

Copy the App Service URL, for example `https://YOUR-API.azurewebsites.net`. In GitHub repository **Settings → Secrets and variables → Actions → Variables**, create:

- `VITE_API_BASE_URL` = App Service URL (no trailing slash)
- `AZURE_WEBAPP_NAME` = App Service resource name

Under **Secrets**, create:

- `AZURE_STATIC_WEB_APPS_API_TOKEN` = deployment token from the Static Web App's **Manage deployment token** page
- `AZURE_WEBAPP_PUBLISH_PROFILE` = downloaded publish profile from the App Service's **Get publish profile** action

The frontend workflow injects `VITE_API_BASE_URL` during the build. It becomes part of the public browser bundle; never place a secret in a `VITE_` variable.

## 4. Deploy and verify

Commit and push the workflows and project files to `main`. The frontend workflow deploys on frontend changes; the API workflow deploys on backend changes. Both can also be started from GitHub Actions with **Run workflow**. The API workflow deploys the `backend` directory. Ensure the App Service publish profile deployment is enabled and that its application settings above are saved.

Check these URLs after the workflows complete:

```text
https://YOUR-API.azurewebsites.net/health
https://YOUR-API.azurewebsites.net/docs
https://YOUR-STATIC-WEB-APP.azurestaticapps.net
```

Use the UI to buy products until stock drops below threshold, confirm an alert appears, then restock. If the API fails to start, inspect App Service **Log stream**. If the browser reports a CORS error, make `CORS_ORIGINS` exactly match the frontend origin (scheme and host, no path/trailing slash), then restart the API.

## Current application limitations

This is a demo app. It has no authentication/authorization, and creates tables at startup instead of using migrations. Do not expose it as a production inventory system without adding access controls and a migration process.
