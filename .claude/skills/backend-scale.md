# Backend Scale Skills

## Project Overview
This is a Texas Hold'em poker backend scaling project targeting 300-500 concurrent users.

## Completed Phases (1-11)

### Phase 1: Connection Pool & Infrastructure ✅
- PostgreSQL connection pool: 50 + 30 overflow
- Redis connection pool: 100 connections
- Uvicorn multi-worker support

### Phase 2: WebSocket Clustering ✅
- Redis Pub/Sub broadcast
- Sticky session (nginx.prod.conf)
- Worker health management
- Connection limits (600 global, 3 per user)

### Phase 3: Database Optimization ✅
- Performance indexes (Alembic migrations)
- N+1 query elimination
- Batch query utilities

### Phase 4: Redis Caching ✅
- Table/Hand state caching
- Write-Behind synchronization
- Cache warmup on startup

### Phase 5: KRW + Crypto Wallet ✅
- KRW balance system
- Crypto deposit/withdrawal
- Exchange rate service
- Audit logging (3-way)

### Phase 6: Rake & VIP System ✅
- Rake calculation with caps
- VIP levels (Bronze-Diamond)
- Weekly rakeback settlement

### Phase 7: Load Testing ✅ (Scripts Ready)
- k6/load-test-500.js
- k6/websocket-stress.js

### Phase 8: Monitoring ✅
- Prometheus metrics
- Custom game metrics

### Phase 9: Operational Stability ✅
- Graceful shutdown
- Health check endpoints

### Phase 10: Performance Optimization ✅
- MessagePack WebSocket protocol
- Celery job queue
- Hand history compression

### Phase 11: Open Source Integration ✅
- orjson (fast JSON)
- structlog (structured logging)
- httpx + tenacity (HTTP client)
- sentry-sdk (error tracking)

## Key Files

### Configuration
- `backend/app/config.py` - Application settings
- `infra/postgres/postgresql.prod.conf` - PostgreSQL tuning
- `infra/redis/redis.prod.conf` - Redis configuration
- `infra/nginx/nginx.prod.conf` - Nginx with sticky session

### Services
- `backend/app/services/rake.py` - Rake calculation
- `backend/app/services/vip.py` - VIP system
- `backend/app/services/wallet.py` - KRW transfers
- `backend/app/services/crypto_deposit.py` - Crypto deposits
- `backend/app/services/crypto_withdrawal.py` - Crypto withdrawals

### Cache
- `backend/app/cache/table_cache.py` - Table state caching
- `backend/app/cache/hand_cache.py` - Hand state caching
- `backend/app/cache/sync_service.py` - Write-Behind sync

### Tasks
- `backend/app/tasks/celery_app.py` - Celery configuration
- `backend/app/tasks/rakeback.py` - Weekly rakeback
- `backend/app/tasks/schedules.py` - Celery Beat schedules

## Test Status
- Engine tests: ✅ All passing (127 tests)
- Services tests: ✅ All passing (50 tests)
- WebSocket tests: ✅ All passing (50 tests)
- API tests: ✅ All passing (80 tests)
- Integration tests: Require running server with WebSocket support

## Database Migrations
- ✅ All migrations applied (phase5_wallet_001 is head)
- Migration chain: e32e3e696448 → add_balance_001 → add_perf_indexes_001 → phase5_wallet_001

## Remaining Work
1. Run k6 load tests (requires deployment)
2. Set up PostgreSQL backups (infrastructure)
3. Configure Sentry DSN (production)
4. Integration tests (require running server)
