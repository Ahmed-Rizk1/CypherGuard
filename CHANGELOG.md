# Changelog

All notable changes to SecureNet SOC are documented in this file.

## [1.4.0] — 2026-05-16 — Phase 5: Documentation & Final Polish

### Added
- Complete `README.md` rewrite with architecture diagram and API reference
- Architecture overview document with Mermaid diagrams (`docs/architecture.md`)
- Database ERD with table documentation (`docs/database_erd.md`)
- Mobile integration guide with code examples (`docs/mobile_integration_guide.md`)
- WebSocket protocol documentation (`docs/websocket_protocol.md`)
- ML model documentation with drift detection guide (`docs/ml_model.md`)
- Environment setup guide for Docker and local dev (`docs/environment_setup.md`)
- OpenAPI/Swagger docs enabled on both gateways (`/docs`, `/redoc`)
- `.dockerignore` for optimized builds
- This CHANGELOG

## [1.3.0] — 2026-05-16 — Phase 4: Infrastructure & Observability

### Added
- **Grafana dashboards:** Security dashboard (8 panels), ML & AI dashboard (9 panels)
- **Prometheus alerts:** 21 rules across 4 groups (critical, security, ML, infrastructure)
- **Redis Sentinel HA:** Primary + replica + 3 sentinels with quorum failover
- **Production compose override:** `docker-compose.prod.yml` with resource limits, PostgreSQL tuning, log rotation
- **CI/CD pipeline:** 5-stage GitHub Actions (lint → security scan → test → config validation → build)
- **Health check script:** `scripts/healthcheck.py` with JSON and exit-code modes
- Infrastructure test suite (21 tests)

### Changed
- Upgraded CI pipeline from basic lint+test to 5-stage with bandit security scanning
- Extended Prometheus retention to 30 days / 5GB

## [1.2.0] — 2026-05-16 — Phase 3: Database & ML Improvements

### Added
- **Alembic migration:** Composite pagination indexes, model_registry table, decision_logs.user_id
- **ModelRegistry ORM:** Tracks model version, algorithm, accuracy, file hash, activation status
- **Prediction logging:** Every ML inference persisted to `ml_predictions` table
- **Feature drift detection:** KL divergence detector with configurable window/threshold
- **Model hot-reload:** `POST /model/reload` with SHA256 hash verification
- **LLM prompt versioning:** v1/v2 externalized templates in `shared/llm_config.py`
- **LLM response validation:** Pydantic schema enforcement for severity, field lengths
- **Model fallback chain:** GPT-4o-mini → Llama-3 free tier
- **Audit log population:** `write_audit_log()` helper for login events
- ML/DB test suite (25 tests)

### Changed
- LLM analyzer now validates responses before use (invalid → heuristic fallback)
- ML engine logs predictions to PostgreSQL instead of fire-and-forget

## [1.1.0] — 2026-05-16 — Phase 2: Mobile/API Completion

### Added
- **15 mobile gateway endpoints:** Auth, alerts, firewall, decisions, dashboard, user profile, FCM
- **9 versioned API gateway endpoints:** Alerts, dashboard summary, user profile
- **Standard response envelope:** `success_response()`, `paginated_response()`, `error_response()`
- **Cursor-based pagination:** `created_at DESC` ordering with `per_page + 1` fetch pattern
- **API versioning:** `/v1/` prefix with backward-compatible legacy routes
- **ORM-to-dict converters:** Safe serialization (no password hash leakage)
- Phase 2 API test suite (29 tests)

### Changed
- Alert fetching moved from Redis (ephemeral) to PostgreSQL (persistent)
- Mobile gateway rewritten from scratch with full API surface

## [1.0.0] — 2026-05-16 — Phase 1: Security Hardening

### Added
- **JWT `jti` claims** with Redis-based token blacklisting
- **Refresh token rotation** (one-time use tokens)
- **Account lockout** (5 failures / 15 min) with constant-time comparison
- **Security headers middleware** (OWASP-compliant)
- **Request body size limits** (1MB)
- **Startup secret validation** (`validate_secrets()`)
- Security test suite (26 tests)

### Fixed
- Duplicate `setup_logging` import in LLM analyzer
- Gateway tests updated for httpx ASGITransport compatibility

### Security
- Unauthenticated requests now return 401 (was 403)
- Error responses sanitized to not leak internal details

## [0.9.0] — Pre-Phases — Initial MVP

### Features
- Event-driven microservices architecture (Redis Streams)
- Real-time packet capture (scapy) → feature extraction → ML inference
- LLM-powered threat classification (GPT-4o-mini via OpenRouter)
- Human-in-the-loop decision engine with mobile dispatch
- Atomic Lua-script decision execution
- React dashboard with real-time WebSocket telemetry
- Docker Compose multi-service deployment
- Prometheus metrics on all services
- Basic Grafana operations dashboard
