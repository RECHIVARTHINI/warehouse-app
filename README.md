# Simple Inventory Management — AWS Deployment Practice

> Deploying to Azure? See the [Azure deployment guide](README-AZURE.md) and the GitHub Actions workflows in `.github/workflows/`.

A beginner-friendly project focused on deploying:
- React + Vite frontend → AWS Amplify
- FastAPI REST API → EC2 (Amazon Linux 2023)
- PostgreSQL database → Amazon RDS

## Three use cases
1. **Store:** list products and click Buy.
2. **Low-stock notification:** when a purchase makes stock lower than the product's threshold, FastAPI records a warehouse alert in PostgreSQL.
3. **Warehouse:** view low-stock alerts and restock a product. Restocking updates PostgreSQL and resolves the alert.

For deployment simplicity, the Store and Warehouse are two logical parts of one FastAPI backend, not two separately deployed microservices. The backend sends the warehouse notification by creating a database alert. This avoids extra infrastructure while demonstrating the requested flow.

## Project layout
```text
inventory-aws-deployment/
  backend/
    main.py
    database.py
    models.py
    schemas.py
    requirements.txt
    .env.example
  frontend/
    index.html
    package.json
    vite.config.js
    amplify.yml
    .env.example
    src/
      main.jsx
      App.jsx
      style.css
```

## 1. Create the PostgreSQL database on RDS
Use your existing private PostgreSQL RDS instance if you still have it. Otherwise create a PostgreSQL RDS database:
- Keep **Public access = No**.
- Put it in the same VPC as your EC2 instance.
- Create/choose a DB subnet group containing private subnets in at least two Availability Zones.
- In the RDS security group, allow inbound PostgreSQL TCP 5432 **from the EC2 security group only** (not `0.0.0.0/0`).
- Note the RDS endpoint, database name, username and password.
- Ensure the EC2 instance can reach the RDS instance on TCP 5432.

For a first practice deployment, a small burstable instance and a low-cost development database are sufficient; check current AWS pricing and stop/delete resources when finished.

## 2. Prepare the backend locally
Install Python 3.11+ and Git. From the project root:

```bash
cd backend
python -m venv .venv
```

Activate the environment:
- Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
- Linux/macOS: `source .venv/bin/activate`

Then:
```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your local PostgreSQL connection details. Example URL:
```env
DATABASE_URL=postgresql+psycopg2://appuser:YOUR_URL_ENCODED_PASSWORD@localhost:5432/inventory
CORS_ORIGINS=http://localhost:5173
```
If your password contains characters such as `@`, `:`, `/`, or `#`, URL-encode it. Never commit `.env` or real credentials.

Run:
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
The API docs are at `http://127.0.0.1:8000/docs`. Tables and sample products are created automatically on first start.

**Local DB option:** install PostgreSQL locally and create a database named `inventory`, or point `DATABASE_URL` at a development PostgreSQL instance. The RDS database can remain private; do not make it public just to test from your laptop.

## 3. Deploy FastAPI to EC2
This project matches the Amazon Linux 2023 + Nginx setup used in the AWS practice.

### 3.1 Launch/choose EC2
- Use Amazon Linux 2023 in a public subnet.
- Security group inbound: SSH 22 only from **your current public IP**, and HTTP 80 from the internet. Do not open port 8000 publicly.
- Attach an IAM role only if you need AWS permissions; this app itself does not need broad AWS permissions.
- Confirm EC2 can connect to private RDS through the security group rule described above.

### 3.2 Copy the backend to EC2
From your computer, run this from the project root (replace the host/key paths):
```bash
scp -i "C:\path\to\your-key.pem" -r backend ec2-user@EC2_PUBLIC_IP:~/inventory-backend
```
Windows users can also upload the folder using an SFTP client. Do not upload `.env` with real credentials in a public repository.

SSH into EC2:
```bash
ssh -i "C:\path\to\your-key.pem" ec2-user@EC2_PUBLIC_IP
```

Install packages and create the environment:
```bash
sudo dnf update -y
sudo dnf install python3 python3-pip nginx -y
cd ~/inventory-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a private environment file:
```bash
sudo nano /etc/inventory-api.env
```
Add (replace values):
```env
DATABASE_URL=postgresql+psycopg2://DB_USERNAME:URL_ENCODED_PASSWORD@YOUR_RDS_ENDPOINT:5432/YOUR_DB_NAME
CORS_ORIGINS=http://localhost:5173
```
Save, then restrict permissions:
```bash
sudo chmod 600 /etc/inventory-api.env
```
Use the actual database name/credentials. RDS requires network access and valid credentials; use `sslmode=require` if needed by your DB policy, appended as `?sslmode=require` to the URL.

### 3.3 Test the API on EC2
```bash
cd ~/inventory-backend
source .venv/bin/activate
set -a
source /etc/inventory-api.env
set +a
uvicorn main:app --host 127.0.0.1 --port 8000
```
In another SSH terminal:
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/products
```
Stop the foreground server with Ctrl+C.

### 3.4 Run FastAPI with systemd
Create:
```bash
sudo nano /etc/systemd/system/inventory-api.service
```
Paste and adjust the home directory if your project is elsewhere:
```ini
[Unit]
Description=Inventory Management FastAPI
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/inventory-backend
EnvironmentFile=/etc/inventory-api.env
ExecStart=/home/ec2-user/inventory-backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
Enable and check:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now inventory-api
sudo systemctl status inventory-api
sudo journalctl -u inventory-api -n 80 --no-pager
```

### 3.5 Configure Nginx as reverse proxy
Create:
```bash
sudo nano /etc/nginx/conf.d/inventory-api.conf
```
Paste:
```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Test and reload:
```bash
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```
Test from your laptop:
- `http://EC2_PUBLIC_IP/health`
- `http://EC2_PUBLIC_IP/docs`

Do not expose port 8000 in the EC2 security group. Nginx accepts HTTP on port 80 and forwards requests internally to FastAPI on `127.0.0.1:8000`.

## 4. Deploy React frontend to AWS Amplify
1. Push the `frontend` folder to a GitHub repository. You can put the whole project in one repo; Amplify's app root will be `frontend`.
2. In AWS Amplify, choose **Host web app** and connect the GitHub repository/branch.
3. In build settings, set the app root to `frontend` if Amplify asks for it. The included `amplify.yml` builds from that folder.
4. Add an Amplify environment variable:
   - `VITE_API_BASE_URL` = `http://EC2_PUBLIC_IP`
5. Deploy. Amplify builds the Vite app and gives you an HTTPS URL.

Important: this simple deployment uses HTTP from the HTTPS Amplify page to EC2, which browsers may block as mixed content. For a reliable production-like setup, put HTTPS on the API using a domain + TLS certificate (commonly Route 53 + ACM + an HTTPS-capable front door such as an ALB, or a domain with a certificate on Nginx). For initial deployment testing, you can verify the API directly and use a temporary development frontend locally; do not treat plain HTTP as production-ready. If you already have a domain, set up HTTPS before relying on the Amplify site.

After you configure `VITE_API_BASE_URL`, update the backend's `CORS_ORIGINS` to include the exact Amplify URL, e.g. `https://main.xxxxx.amplifyapp.com`. Restart the backend:
```bash
sudo systemctl restart inventory-api
```
CORS origins are comma-separated, no trailing slash. During initial local testing, use `http://localhost:5173`.

## 5. Test the three use cases
1. Open the frontend.
2. Store view: see products and stock count; click Buy.
3. When stock becomes less than the product threshold, the low-stock alert appears in the Warehouse panel.
4. Warehouse view: enter a restock quantity and click Restock. The database stock increases and the alert is resolved.

Use `/docs` to try the API endpoints:
- `GET /health`
- `GET /products`
- `POST /store/buy` with `{"product_id": 1}`
- `GET /warehouse/alerts`
- `POST /warehouse/restock` with `{"product_id": 1, "quantity": 10}`

## Troubleshooting
- **API cannot reach RDS:** verify endpoint/port/database/credentials, EC2 and RDS VPC/subnets, and RDS SG inbound TCP 5432 source = EC2 SG.
- **502 from Nginx:** `sudo systemctl status inventory-api` and `sudo journalctl -u inventory-api -n 80 --no-pager`.
- **Browser CORS error:** set `CORS_ORIGINS` to the exact frontend origin, then restart service.
- **Amplify build fails:** ensure app root is `frontend`, and `npm run build` works locally.
- **Frontend says API URL missing:** set `VITE_API_BASE_URL` in Amplify environment variables and redeploy.

## Cleanup reminder
AWS charges may continue for running EC2/RDS, storage, snapshots, public IPv4 addresses, and related resources. When practice is complete, back up anything you need and stop/delete resources you no longer need.
