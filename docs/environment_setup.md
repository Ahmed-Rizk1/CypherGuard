# SecureNet SOC — Environment Setup Guide

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend services |
| Node.js | 18+ | React dashboard |
| Docker | 24+ | Container runtime |
| Docker Compose | v2+ | Multi-service orchestration |
| Git | 2.40+ | Version control |
| PostgreSQL | 16 | Database (or use Docker) |
| Redis | 7 | Message broker + cache (or use Docker) |

---

## Option A: Docker Setup (Recommended)

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/SecureNet-SOC.git
cd SecureNet-SOC

# Generate secrets automatically
python scripts/generate_secrets.py --write

# Or manually
cp .env.example .env
# Edit .env — set at minimum:
#   OPENROUTER_API_KEY=your-key
#   JWT_SECRET=<openssl rand -hex 32>
#   INTERNAL_API_KEY=<openssl rand -hex 32>
#   POSTGRES_PASSWORD=<openssl rand -hex 16>
```

### 2. Train ML Model

```bash
pip install -r requirements.txt
python ml_engine/train_production.py <path_to_cicids2017.csv>
```

### 3. Start Services

```bash
# Core only
docker compose up -d

# With monitoring (Prometheus + Grafana + Alertmanager)
docker compose --profile observability up -d

# Full production (+ TLS via Traefik)
docker compose --profile production --profile observability up -d

# With Redis HA (Sentinel)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile redis-ha up -d
```

### 4. Create Admin User

```bash
python scripts/create_admin.py --email admin@securenet.local --password YourStrongPassword123!
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Verify

```bash
python scripts/healthcheck.py
```

---

## Option B: Local Development (No Docker)

### 1. Install System Dependencies

**Redis:**
```bash
# Windows (via WSL or Memurai)
# Linux
sudo apt install redis-server
redis-server --appendonly yes
```

**PostgreSQL:**
```bash
# Install PostgreSQL 16
# Create database:
createdb -U postgres securenet
```

### 2. Python Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Frontend

```bash
cd soc-frontend
npm install
cd ..
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env:
#   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/securenet
#   REDIS_URL=redis://localhost:6379/0
#   OPENROUTER_API_KEY=your-key
```

### 5. Initialize Database

```bash
# Apply migrations
alembic upgrade head

# Create admin user
python scripts/create_admin.py --email admin@securenet.local --password YourPassword123!
```

### 6. Start All Services

```bash
# Windows — opens terminal per service
.\start_all.bat

# Or manually (each in separate terminal):
python -m uvicorn gateway.main:app --port 8000
python -m uvicorn ml_engine.main:app --port 8002
python -m uvicorn llm_analyzer.main:app --port 8003
python -m uvicorn firewall.main:app --port 8004
python -m uvicorn mobile_gateway.main:app --port 8005
python -m uvicorn extractor.main:app --port 8001

# Frontend
cd soc-frontend && npm run dev
```

---

## Environment Variables Reference

### Required

| Variable | Description | Example |
|---|---|---|
| `JWT_SECRET` | JWT signing key (min 32 chars) | `openssl rand -hex 32` |
| `INTERNAL_API_KEY` | Inter-service auth key | `openssl rand -hex 32` |
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | — | LLM API key (falls back to heuristics if empty) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ALERT_COOLDOWN_SECONDS` | `60` | Min seconds between alerts for same IP |
| `MOBILE_DECISION_TIMEOUT` | `60` | Seconds before auto-block on no mobile response |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | CORS allowed origins |
| `DRIFT_BASELINE_PATH` | `ml_engine/models/feature_baselines.json` | Drift detection baselines |
| `CHAOS_MODE` | `false` | Enable chaos testing (NEVER in prod) |

---

## Troubleshooting

### Services won't start
```bash
# Check .env is populated
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('JWT_SECRET', 'MISSING'))"

# Check Redis
redis-cli ping  # Should return PONG

# Check PostgreSQL
psql -U securenet -d securenet -c "SELECT 1;"
```

### Import errors
```bash
# Ensure project root is in PYTHONPATH
set PYTHONPATH=.   # Windows
export PYTHONPATH=. # Linux
```

### Frontend blank page
```bash
# Check gateway is running
curl http://localhost:8000/health

# Check CORS
# Ensure ALLOWED_ORIGINS includes http://localhost:5173
```

### Tests failing
```bash
# Ensure env vars set
set JWT_SECRET=test-secret-that-is-long-enough-for-validation
set INTERNAL_API_KEY=test-internal-key-long-enough-for-validation
pytest tests/ -v --tb=short
```
