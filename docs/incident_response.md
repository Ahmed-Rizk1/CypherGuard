# SecureNet IDS — Incident Response Runbook

## Severity Levels

| Level | Definition | Response Time | Examples |
|---|---|---|---|
| P0 | Full system outage | 15 min | Gateway down, Redis dead, DB corruption |
| P1 | Major feature broken | 30 min | WebSocket dead, auth failures, no alerts |
| P2 | Degraded performance | 1 hour | LLM circuit open, high stream lag |
| P3 | Minor issue | 4 hours | Dashboard slowness, stale metrics |

---

## Incident Playbooks

### INC-001: Gateway Down (P0)

**Alert**: `ServiceDown{job="gateway"}`

```bash
# 1. Check container status
docker compose ps gateway
docker compose logs --tail=50 gateway

# 2. Common causes:
#    - ImportError → check shared module changes
#    - Port conflict → netstat -tulpn | grep 8000
#    - Secret validation failed → check .env

# 3. Restart
docker compose restart gateway

# 4. Verify
curl http://localhost:8000/health
```

### INC-002: Redis Down (P0)

**Alert**: `ServiceDown{job="gateway"}` (all services fail health checks)

```bash
# 1. Check Redis
docker compose logs --tail=50 redis
docker exec securenet-redis redis-cli ping

# 2. Check memory
docker exec securenet-redis redis-cli info memory

# 3. If OOM → flush non-critical data
docker exec securenet-redis redis-cli FLUSHDB

# 4. Restart
docker compose restart redis

# Note: Consumer groups will resume from last ACK'd message.
# Rate limiter fails-open during outage.
```

### INC-003: LLM Circuit Open (P2)

**Alert**: `LLMCircuitOpen`

```bash
# 1. Check circuit breaker state
curl http://localhost:8003/health

# 2. Check OpenRouter status: https://status.openrouter.ai
# 3. Check API key validity
# 4. Heuristic fallback is ACTIVE — alerts still being processed

# Resolution: Circuit auto-recovers after 30s (HALF_OPEN probe)
```

### INC-004: Alert Storm (P1)

**Alert**: `HighAlertRate`

```bash
# 1. Check if it's a real attack or false positives
docker compose logs --tail=100 ml-engine | grep "prediction"

# 2. Check ML model version
# 3. Check feature alignment

# 4. If false positive storm, temporarily raise threshold:
#    Update ALERT_COOLDOWN_SECONDS in .env
docker compose restart extractor
```

### INC-005: Brute Force Detected (P1)

**Alert**: `AuthBruteForce`

```bash
# 1. Identify source IPs
docker compose logs gateway | grep "login_failure" | tail -20

# 2. Rate limiter is already active (120/60s gateway, 5/60s mobile)
# 3. If persistent, block at firewall level:
#    iptables -A INPUT -s <attacker_ip> -j DROP
```

### INC-006: Decision Queue Growing (P2)

**Alert**: `DecisionQueueGrowing`

```bash
# 1. Check decision-log-writer health
docker compose ps decision-log-writer
docker compose logs --tail=50 decision-log-writer

# 2. Check Postgres connectivity
docker exec securenet-postgres pg_isready -U securenet

# 3. Check for deadlocks
docker exec securenet-postgres psql -U securenet -c "SELECT * FROM pg_stat_activity WHERE wait_event_type = 'Lock';"

# 4. Restart writer
docker compose restart decision-log-writer
```

### INC-007: WebSocket Mass Disconnect (P2)

**Alert**: `securenet_websocket_connections` drops to 0

```bash
# 1. Check gateway health and logs
docker compose logs --tail=50 gateway | grep "WebSocket"

# 2. Clients auto-reconnect with exponential backoff (1s → 30s)
# 3. Check Redis connectivity (telemetry push loop depends on it)
# 4. If persistent, restart gateway
docker compose restart gateway
```

---

## Post-Incident

1. **Timeline**: Document when incident started, detected, and resolved
2. **Root cause**: Identify the actual cause (not just the symptom)
3. **Action items**: Create tickets for preventive measures
4. **Metrics review**: Check Grafana dashboards for anomalies during incident window
