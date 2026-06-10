# SecureNet IDS — Production Deployment Runbook

## Prerequisites

1. **Secrets generated**:
   ```bash
   openssl rand -hex 32   # → JWT_SECRET
   openssl rand -hex 32   # → INTERNAL_API_KEY
   openssl rand -hex 16   # → POSTGRES_PASSWORD
   ```

2. **Configuration**:
   ```bash
   cp .env.example .env
   # Edit .env with real secrets, domain, CORS origins, and OpenRouter API key
   ```

3. **ML Model trained**:
   ```bash
   python ml_engine/train_production.py <path_to_cicids_dataset.csv>
   ```

4. **Admin user created** (after Postgres is up):
   ```bash
   python scripts/create_admin.py --email admin@yourorg.com --password <strong_pw>
   ```

---

## Deployment Profiles

### Development (default)
```bash
docker compose up -d
# Starts: redis, postgres, all backend services, frontend on port 80
# Observability stack NOT included
```

### With Monitoring
```bash
docker compose --profile observability up -d
# Adds: prometheus (9090), grafana (3000), alertmanager (9093)
# Grafana dashboards: Operations, Security, ML & AI (auto-provisioned)
```

### Full Production (with TLS + HA)
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile production --profile observability up -d
# Adds: traefik (80/443) with auto Let's Encrypt
# Includes: resource limits, PostgreSQL tuning, log rotation
```

### With Redis HA (Sentinel)
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile production --profile observability --profile redis-ha up -d
# Adds: redis-replica + 3 sentinel instances (quorum=2)
```

---

## Post-Deployment Checklist

```bash
# Automated health check
python scripts/healthcheck.py --exit-on-failure

# Manual verification
[ ] docker compose ps                  # All containers "healthy" or "running"
[ ] curl http://localhost:8000/health   # Gateway responds {"status": "healthy"}
[ ] curl http://localhost:8005/health   # Mobile Gateway healthy
[ ] curl http://localhost:8002/model/info # ML Engine model loaded
[ ] curl http://localhost:8006/ready    # Decision engine Redis connected
[ ] curl http://localhost:9090/-/ready  # Prometheus ready
[ ] open http://localhost:3000          # Grafana login page loads
[ ] open http://localhost:8000/docs     # API documentation loads
[ ] open http://localhost:8005/docs     # Mobile API documentation loads
```

---

## Database Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Check current version
alembic current

# Generate new migration (after model changes)
alembic revision --autogenerate -m "description"

# Rollback one step
alembic downgrade -1
```

---

## Rolling Update (Zero-Downtime)

```bash
# 1. Build new images
docker compose build --parallel

# 2. Rolling restart (one service at a time)
docker compose up -d --no-deps gateway
docker compose up -d --no-deps extractor
docker compose up -d --no-deps ml-engine
docker compose up -d --no-deps llm-analyzer
docker compose up -d --no-deps firewall
docker compose up -d --no-deps decision-engine
docker compose up -d --no-deps mobile-gateway

# 3. Frontend last (no state)
docker compose up -d --no-deps frontend

# 4. Verify
python scripts/healthcheck.py --exit-on-failure
```

---

## ML Model Update

```bash
# 1. Retrain with new data
python ml_engine/train_production.py <new_dataset.csv>

# 2. Hot-reload without restart
curl -X POST http://localhost:8002/model/reload

# 3. Verify
curl http://localhost:8002/model/info
# Check: model_hash changed, version updated
```

---

## Secret Rotation

```bash
# 1. Add new secret as FIRST entry (comma-separated)
JWT_SECRET=new-secret-here,old-secret-here

# 2. Restart all services
docker compose restart

# 3. Wait for all old tokens to expire (max 1 hour)

# 4. Remove old secret
JWT_SECRET=new-secret-here

# 5. Restart again
docker compose restart
```

---

## Rollback

```bash
# If a deployment fails:
docker compose down
git checkout HEAD~1 -- docker-compose.yml
docker compose up -d

# Database rollback (if migration failed):
alembic downgrade -1

# Full database restore:
cat backup_YYYYMMDD.sql | docker exec -i securenet-postgres psql -U securenet securenet
```

---

## Database Backup

```bash
# Manual backup
docker exec securenet-postgres pg_dump -U securenet securenet > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260509.sql | docker exec -i securenet-postgres psql -U securenet securenet

# Automated daily backup (cron)
0 2 * * * docker exec securenet-postgres pg_dump -U securenet securenet | gzip > /backups/securenet_$(date +\%Y\%m\%d).sql.gz
```

---

## Monitoring Quick Reference

| Dashboard | URL | Purpose |
|---|---|---|
| Operations | http://localhost:3000/d/securenet-ops | Pipeline throughput, latency, queues |
| Security | http://localhost:3000/d/securenet-security | Auth events, blocked IPs, rate limits |
| ML & AI | http://localhost:3000/d/securenet-ml | Predictions, drift, LLM circuit breaker |
| Prometheus | http://localhost:9090 | Raw metrics and alerts |
| Alertmanager | http://localhost:9093 | Active alerts and silences |
