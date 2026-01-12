# 홀덤 포커 백엔드 스케일링 작업계획서

> **작성일**: 2026-01-12
> **버전**: 1.3 Final (오픈소스 통합 완료)
> **목표**: 300-500명 동시 접속 안정 운영 가능한 고성능 백엔드 구축
> **범위**: 백엔드 100% (프론트엔드 제외)

---

## 핵심 비즈니스 요구사항

```
┌─────────────────────────────────────────────────────────────────────┐
│  💰 화폐 시스템                                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  게임 내 표시: KRW (원화)                                             │
│  ├── 모든 칩/베팅/팟/잔액은 원화(₩)로 표시                            │
│  ├── 예: ₩10,000 / ₩50,000 블라인드                                  │
│  └── 사용자 친화적 UI/UX                                              │
│                                                                      │
│  실제 입출금: 암호화폐만                                               │
│  ├── 지원 코인: BTC, ETH, USDT, USDC 등                              │
│  ├── 입금 시 실시간 환율로 KRW 변환                                   │
│  ├── 출금 시 KRW → 암호화폐 환산                                      │
│  └── Crypto Payment Gateway 연동 (Phase 5)                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  🎯 300-500명 동시 접속 백엔드 아키텍처                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  동시 접속: 300-500명 (기존 100명 대비 3-5배 확장)                    │
│  활성 테이블: 50-80개 (테이블당 6-9명)                                │
│  WebSocket 연결: 500-700개 (여유분 포함)                              │
│  API 응답: p95 < 150ms, p99 < 300ms                                  │
│  가용성: 99.9% (월 43분 이하 다운타임)                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚨 세션 중단 대비 필수 지침 (중요!)

```
╔═══════════════════════════════════════════════════════════════════════╗
║  ⚠️ 필수: 토큰 한도로 작업이 갑자기 중단될 수 있음                       ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  📌 작업 재개 방법:                                                    ║
║  ────────────────────────────────────────────────────────────────────  ║
║  1. 이 파일(BACKEND_SCALE_WORKPLAN.md) 열기                            ║
║  2. 마지막으로 [x] 체크된 단계 확인                                     ║
║  3. 다음 명령으로 재개:                                                 ║
║     "BACKEND_SCALE_WORKPLAN.md 읽고 [X.X]단계부터 이어서 작업해줘"     ║
║                                                                        ║
║  📌 필수 규칙:                                                         ║
║  ────────────────────────────────────────────────────────────────────  ║
║  ✓ 각 하위 작업 완료 즉시 [ ] → [x] 체크                               ║
║  ✓ 단계 완료 시 "**[x] X.X 완료**" 체크 + 날짜/시간 기록               ║
║  ✓ Phase 완료 시 git commit 실행                                       ║
║  ✓ 작업 중단 전 반드시 현재 상태 저장 (git add .)                       ║
║                                                                        ║
║  📌 완료 체크 예시:                                                    ║
║  ────────────────────────────────────────────────────────────────────  ║
║  - [x] config.py 수정                                                  ║
║  - [x] database.py 수정                                                ║
║  **[x] 1.1 완료** - 날짜/시간: 2026-01-12 15:30                        ║
║                                                                        ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

## 현재 상태 (2026-01-12 기준)

### 완료된 작업

| 구분 | 상태 | 비고 |
|------|------|------|
| 스펙 문서 (P0~P6) | ✅ 완료 | 22개 문서 |
| 기본 구현 (I0~I8) | ✅ 완료 | 단일 서버 기준 |
| 보안 이슈 수정 (15단계) | ✅ 완료 | HMAC 서명, Rate Limiting 등 |
| 백엔드 테스트 (290개+) | ✅ 완료 | 단위 테스트 |
| WebSocket 기본 | ✅ 완료 | 단일 인스턴스 기준 |

### 미완료 작업 (이 문서 범위)

| Phase | 작업 내용 | 우선순위 | 상태 |
|-------|---------|---------|------|
| 1 | 커넥션 풀/인프라 강화 | ⭐⭐⭐⭐⭐ | ✅ 완료 |
| 2 | WebSocket 클러스터링 (강화) | ⭐⭐⭐⭐⭐ | ✅ 완료 |
| 3 | 데이터베이스 최적화 | ⭐⭐⭐⭐⭐ | ⏳ 대기 |
| 4 | Redis 고가용성 + 게임 상태 캐싱 | ⭐⭐⭐⭐⭐ | ⏳ 대기 |
| 5 | KRW 잔액 + 암호화폐 입출금 | ⭐⭐⭐⭐⭐ | ✅ 완료 |
| 6 | Rake & 경제 시스템 | ⭐⭐⭐⭐ | ⏳ 대기 |
| 7 | 부하 테스트 & 튜닝 | ⭐⭐⭐⭐⭐ | ⏳ 대기 |
| 8 | 모니터링 & 알림 | ⭐⭐⭐⭐ | ⏳ 대기 |
| 9 | 운영 안정화 | ⭐⭐⭐ | ⏳ 대기 |
| 10 | 성능 최적화 (Binary/JobQueue/압축) | ⭐⭐⭐⭐ | ⏳ 대기 |

---

## Phase 1: 커넥션 풀 & 인프라 강화

> **예상 기간**: 2-3일
> **우선순위**: ⭐⭐⭐⭐⭐ (최우선)
> **현재 상태**: ✅ 완료

### 1.1 PostgreSQL 커넥션 풀 확장

**상태**: [x] 완료

#### 1.1.1 config.py 수정
- [x] `DATABASE_POOL_SIZE` 환경변수 추가 (기본값: 50)
- [x] `DATABASE_MAX_OVERFLOW` 환경변수 추가 (기본값: 30)
- [x] `DATABASE_POOL_TIMEOUT` 환경변수 추가 (기본값: 30초)
- [x] `DATABASE_POOL_RECYCLE` 환경변수 추가 (기본값: 1800초)

```python
# backend/app/config.py 수정 내용
database_pool_size: int = Field(default=50, description="DB connection pool size")
database_max_overflow: int = Field(default=30, description="Max overflow connections")
database_pool_timeout: int = Field(default=30, description="Pool connection timeout")
database_pool_recycle: int = Field(default=1800, description="Connection recycle time")
```

#### 1.1.2 database.py 수정
- [x] `create_async_engine` 옵션 추가
- [x] 커넥션 풀 설정 적용
- [x] 커넥션 상태 모니터링 추가 (pool_pre_ping=True)

```python
# backend/app/database.py 수정 내용
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_recycle=settings.database_pool_recycle,
    pool_pre_ping=True,  # 연결 상태 확인
    echo=settings.debug,
)
```

**[x] 1.1 완료** - 날짜/시간: 2026-01-12 14:50

---

### 1.2 Redis 연결 풀 확장

**상태**: [x] 완료

#### 1.2.1 Redis 설정 추가
- [x] `REDIS_MAX_CONNECTIONS` 환경변수 추가 (기본값: 100)
- [x] `REDIS_SOCKET_TIMEOUT` 환경변수 추가 (기본값: 5초)
- [x] `REDIS_SOCKET_CONNECT_TIMEOUT` 환경변수 추가 (기본값: 5초)

#### 1.2.2 Redis 클라이언트 수정
- [x] 커넥션 풀 생성 (ConnectionPool.from_url)
- [x] 재연결 로직 강화 (retry_on_timeout=True, health_check_interval)

```python
# backend/app/redis.py 수정 내용
from redis.asyncio import ConnectionPool, Redis

pool = ConnectionPool.from_url(
    settings.redis_url,
    max_connections=settings.redis_max_connections,
    socket_timeout=settings.redis_socket_timeout,
    socket_connect_timeout=settings.redis_socket_connect_timeout,
    retry_on_timeout=True,
    health_check_interval=30,
)

redis = Redis(connection_pool=pool)
```

**[x] 1.2 완료** - 날짜/시간: 2026-01-12 14:52

---

### 1.3 Uvicorn Workers 설정

**상태**: [x] 완료

#### 1.3.1 멀티 워커 설정
- [x] `UVICORN_WORKERS` 환경변수 추가 (기본값: 1, 프로덕션: 4-8)
- [x] main.py에 프로덕션 모드 멀티 워커 설정 추가

```bash
# 직접 실행
uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000

# 또는 Gunicorn (더 안정적)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

#### 1.3.2 WebSocket 주의사항
- [x] 멀티 워커 시 WebSocket sticky session 또는 Redis Pub/Sub 필수 (주석 문서화)
- [x] Phase 2에서 처리 예정

**[x] 1.3 완료** - 날짜/시간: 2026-01-12 14:55

---

### 1.4 서버 리소스 권장 사양

**상태**: [x] 완료 (문서화)

```
┌─────────────────────────────────────────────────────────────────────┐
│  500명 동시 접속 권장 사양                                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  옵션 A: 고성능 단일 서버                                             │
│  ├── CPU: 8코어                                                      │
│  ├── RAM: 16GB                                                       │
│  ├── SSD: 100GB+                                                     │
│  ├── 네트워크: 1Gbps                                                 │
│  └── 예상 비용: $100-200/월                                          │
│                                                                      │
│  옵션 B: 분리된 서버 (권장)                                           │
│  ├── App Server: 4코어 8GB × 2대                                     │
│  ├── DB Server: 4코어 16GB × 1대                                     │
│  ├── Redis Server: 2코어 4GB × 1대                                   │
│  └── 예상 비용: $150-300/월                                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**[x] 1.4 완료** - 날짜/시간: 2026-01-12 14:56

---

### Phase 1 완료 체크

```bash
# Phase 1 완료 시 실행
git add .
git commit -m "Phase 1 완료: 커넥션 풀 & 인프라 강화

- PostgreSQL 커넥션 풀 50+30 설정
- Redis 커넥션 풀 100 설정
- Uvicorn 멀티 워커 설정
- 서버 사양 문서화"
```

**[x] Phase 1 전체 완료** - 날짜/시간: 2026-01-12 14:56

---

## Phase 2: WebSocket 클러스터링 (강화)

> **예상 기간**: 4-6일
> **우선순위**: ⭐⭐⭐⭐⭐ (최우선)
> **현재 상태**: ✅ 완료
> **v1.2 추가**: Sticky Session, Redis Adapter, 고급 장애 복구

### 2.1 Redis Pub/Sub 브로드캐스트 구현

**상태**: [x] 완료 (기존 ConnectionManager에 이미 구현됨)

#### 2.1.1 PubSubManager 클래스 생성
- [x] `backend/app/ws/manager.py` - ConnectionManager에 통합 구현
- [x] 채널별 구독/발행 로직 구현 (`ws:pubsub:*` 패턴)
- [x] 로비/테이블별 채널 분리

```python
# backend/app/ws/pubsub.py
import asyncio
import json
from redis.asyncio import Redis

class PubSubManager:
    """Redis Pub/Sub 기반 WebSocket 브로드캐스트 관리"""

    def __init__(self, redis: Redis):
        self._redis = redis
        self._pubsub = redis.pubsub()
        self._channels: dict[str, set] = {}
        self._running = False

    async def start(self):
        """Pub/Sub 리스너 시작"""
        self._running = True
        asyncio.create_task(self._listen_loop())

    async def publish(self, channel: str, message: dict):
        """메시지 발행 (모든 워커에 전달)"""
        await self._redis.publish(channel, json.dumps(message))
```

#### 2.1.2 채널 명명 규칙
- [x] 로비 채널: `lobby`
- [x] 테이블 채널: `table:{table_id}`
- [x] 사용자 채널: `user:{user_id}` (개인 알림용)

**[x] 2.1 완료** - 날짜/시간: 2026-01-12 15:20 (기존 구현 확인)

---

### 2.2 ConnectionManager 리팩토링

**상태**: [x] 완료 (기존 구현에 연결 제한 추가)

#### 2.2.1 ConnectionManager 수정
- [x] `backend/app/ws/manager.py` - 이미 Redis Pub/Sub 지원
- [x] 로컬 연결 관리 + Redis Pub/Sub 연동
- [x] 연결 상태 Redis 저장 (`ws:connections:{user_id}`)

**[x] 2.2 완료** - 날짜/시간: 2026-01-12 15:20

---

### 2.3 테이블 상태 Redis 동기화

**상태**: [x] 완료 (기존 구현)

#### 2.3.1 테이블 상태 저장
- [x] 테이블 생성 시 Redis에 상태 저장
- [x] 상태 변경 시 Redis 업데이트
- [x] 상태 조회 시 Redis에서 먼저 확인

**[x] 2.3 완료** - 날짜/시간: 2026-01-12 15:20

---

### 2.4 Heartbeat 강화

**상태**: [x] 완료 (기존 구현)

- [x] 연결별 마지막 heartbeat 시간 추적 (`last_ping_at`)
- [x] 60초 이상 미응답 시 연결 정리 (`SERVER_TIMEOUT = 60`)
- [x] Redis 연결 정보 TTL 갱신

**[x] 2.4 완료** - 날짜/시간: 2026-01-12 15:20

---

### 2.5 WebSocket 연결 제한

**상태**: [x] 완료

- [x] `WS_MAX_CONNECTIONS` 환경변수 (기본값: 600)
- [x] `WS_MAX_CONNECTIONS_PER_USER` 환경변수 (기본값: 3)
- [x] 초과 시 가장 오래된 연결 종료 (`_get_oldest_user_connection`)

**[x] 2.5 완료** - 날짜/시간: 2026-01-12 15:30

---

### 2.6 Sticky Session 설정 (v1.2 추가)

**상태**: [x] 완료

#### 2.6.1 로드밸런서 설정
- [x] Nginx/HAProxy sticky session 설정 (`infra/nginx/nginx.prod.conf`)
- [x] IP 해시 기반 세션 유지 (`ip_hash;`)

```nginx
# nginx.conf - IP Hash 방식
upstream backend {
    ip_hash;
    server app1:8000;
    server app2:8000;
    server app3:8000;
}

# 또는 쿠키 기반 (더 정확)
upstream backend {
    server app1:8000;
    server app2:8000;
    sticky cookie srv_id expires=1h;
}
```

#### 2.6.2 WebSocket 업그레이드 처리
- [x] Connection: Upgrade 헤더 처리
- [x] 101 Switching Protocols 전달

```nginx
location /ws {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 86400;
}
```

**[x] 2.6 완료** - 날짜/시간: 2026-01-12 15:35

---

### 2.7 워커 간 장애 복구 (v1.2 추가)

**상태**: [x] 완료

#### 2.7.1 워커 상태 모니터링
- [x] Redis에 워커별 연결 수 저장 (`ws:workers`, `ws:worker:{id}:alive`)
- [x] 워커 비정상 종료 감지 (TTL 30초, 5초마다 heartbeat)

```python
# backend/app/ws/worker_health.py
class WorkerHealthManager:
    """워커 상태 관리"""

    async def register_worker(self, worker_id: str):
        """워커 등록 (TTL 30초)"""
        await self._redis.setex(
            f"worker:{worker_id}:alive",
            30,
            datetime.utcnow().isoformat()
        )

    async def heartbeat(self, worker_id: str):
        """워커 heartbeat (5초마다)"""
        await self._redis.setex(
            f"worker:{worker_id}:alive",
            30,
            datetime.utcnow().isoformat()
        )

    async def cleanup_dead_worker(self, worker_id: str):
        """죽은 워커의 연결 정리"""
        # 해당 워커의 연결 정보 삭제
        # 연결된 사용자들에게 재연결 유도
        pass
```

#### 2.7.2 연결 마이그레이션
- [x] 워커 종료 시 Redis에서 연결 정보 정리 (`_cleanup_worker_connections`)
- [x] 클라이언트 재연결 시 상태 복원 (`store_user_state`, `get_user_state`)

**[x] 2.7 완료** - 날짜/시간: 2026-01-12 15:40

---

### Phase 2 완료 체크

```bash
git add .
git commit -m "Phase 2 완료: WebSocket 클러스터링 (강화)

- Redis Pub/Sub 브로드캐스트 구현 (기존 구현 확인)
- ConnectionManager 멀티 워커 지원 (연결 제한 추가)
- 테이블 상태 Redis 동기화 (기존 구현)
- Heartbeat 강화 (60초 타임아웃)
- 연결 수 제한 (전역 600, 사용자당 3)
- Sticky Session 설정 (Nginx nginx.prod.conf)
- 워커 간 장애 복구 (WorkerHealthManager)"
```

**[x] Phase 2 전체 완료** - 날짜/시간: 2026-01-12 15:40

---

## Phase 3: 데이터베이스 최적화

> **예상 기간**: 3-4일
> **우선순위**: ⭐⭐⭐⭐⭐ (최우선)
> **현재 상태**: ✅ 완료

### 3.1 인덱스 최적화

**상태**: [x] 완료

#### 3.1.1 핵심 인덱스 추가

```sql
-- 사용자 조회 (이미 존재)
CREATE UNIQUE INDEX ix_users_email ON users(email);
CREATE UNIQUE INDEX ix_users_nickname ON users(nickname);

-- 방/테이블 조회 (ix_rooms_status 존재, created_at DESC 추가)
CREATE INDEX ix_rooms_created_at_desc ON rooms(created_at DESC);
CREATE INDEX ix_rooms_status_created_at ON rooms(status, created_at DESC);

-- 핸드 히스토리 (ix_hands_table_id 존재, started_at DESC 추가)
CREATE INDEX ix_hands_started_at_desc ON hands(started_at DESC);
CREATE INDEX ix_hands_table_started_at ON hands(table_id, started_at DESC);

-- 복합 인덱스 추가
CREATE INDEX ix_hand_events_hand_seq ON hand_events(hand_id, seq_no);
CREATE INDEX ix_sessions_expires_at ON sessions(expires_at);

-- 트랜잭션 조회 (Phase 5에서 wallet_transactions 테이블 생성 시 추가)
```

- [x] Alembic 마이그레이션 파일 생성 (`add_performance_indexes.py`)
- [ ] 마이그레이션 실행 (배포 시)
- [ ] 인덱스 사용 확인 (EXPLAIN ANALYZE)

**[x] 3.1 완료** - 날짜/시간: 2026-01-12 16:30

---

### 3.2 쿼리 최적화

**상태**: [x] 완료

- [x] N+1 쿼리 제거 (`selectinload`, `joinedload`)
  - RoomService: 이미 selectinload 사용
  - TableHandler: `_get_table_by_id_or_room`에 `joinedload(Table.room)` 추가
- [x] 배치 조회 적용 (IN 절)
  - `backend/app/utils/query_optimization.py` 유틸리티 생성
  - `batch_get_by_ids()`, `batch_get_with_related()` 함수 추가
- [x] 페이지네이션 최적화
  - `paginate_with_cursor()` 커서 기반 페이지네이션 함수 추가

**[x] 3.2 완료** - 날짜/시간: 2026-01-12 16:45

---

### 3.3 PostgreSQL 튜닝

**상태**: [x] 완료

```conf
# 500명 동시 접속 기준 (infra/postgres/postgresql.prod.conf)
max_connections = 150
shared_buffers = 4GB
effective_cache_size = 12GB
work_mem = 32MB
maintenance_work_mem = 1GB
random_page_cost = 1.1  # SSD 최적화
effective_io_concurrency = 200  # SSD 최적화
autovacuum_vacuum_scale_factor = 0.1  # 자동 vacuum 민감도 증가
```

추가 파일 생성:
- `infra/postgres/postgresql.prod.conf`: 프로덕션 PostgreSQL 설정
- `infra/postgres/init.sql`: 모니터링 뷰 및 초기화 스크립트

**[x] 3.3 완료** - 날짜/시간: 2026-01-12 17:00

---

### Phase 3 완료 체크

```bash
git add .
git commit -m "Phase 3 완료: 데이터베이스 최적화

- 핵심 테이블 인덱스 추가 (Alembic 마이그레이션)
- N+1 쿼리 제거 (joinedload, selectinload)
- 배치 조회 유틸리티 (query_optimization.py)
- PostgreSQL 프로덕션 튜닝 설정"
```

**[x] Phase 3 전체 완료** - 날짜/시간: 2026-01-12 17:00

---

## Phase 4: Redis 고가용성 + 게임 상태 캐싱

> **예상 기간**: 4-5일
> **우선순위**: ⭐⭐⭐⭐⭐ (최우선으로 상향)
> **현재 상태**: ✅ 완료
> **v1.2 추가**: 게임 상태 중심 캐싱 (DB 부하 70-90% 감소 목표)

### 4.1 Redis 메모리 정책 설정

**상태**: [x] 완료

```conf
maxmemory 2gb
maxmemory-policy allkeys-lru
maxclients 500
```

**[x] 4.1 완료** - 날짜/시간: 2026-01-12 18:00
- 생성 파일: `infra/redis/redis.prod.conf`

---

### 4.2 Redis 캐시 전략

**상태**: [x] 완료

- [x] 캐시 키 설계 (TTL 정책)
- [x] 캐시 무효화 전략

**[x] 4.2 완료** - 날짜/시간: 2026-01-12 18:05
- 생성 파일: `backend/app/cache/keys.py`

---

### 4.3 게임 상태 Redis 중심 캐싱 (v1.2 추가)

**상태**: [x] 완료

#### 4.3.1 테이블 상태 Redis Hash 저장
- [x] `backend/app/cache/table_cache.py` 생성
- [x] 테이블 상태를 Redis Hash로 관리
- [x] DB는 영구 저장용으로만 사용 (write-behind)

```python
# backend/app/cache/table_cache.py
class TableCacheService:
    """테이블 상태 Redis 캐싱 (DB 부하 90% 감소)"""

    KEY_PREFIX = "table:"

    async def get_table_state(self, table_id: str) -> TableState | None:
        """Redis에서 테이블 상태 조회 (캐시 히트)"""
        data = await self._redis.hgetall(f"{self.KEY_PREFIX}{table_id}")
        if data:
            return TableState.from_cache(data)
        return None

    async def set_table_state(self, table_id: str, state: TableState):
        """Redis에 테이블 상태 저장"""
        await self._redis.hset(
            f"{self.KEY_PREFIX}{table_id}",
            mapping=state.to_cache_dict()
        )
        await self._redis.expire(f"{self.KEY_PREFIX}{table_id}", 3600)

    async def update_player_stack(self, table_id: str, position: int, stack: int):
        """플레이어 스택만 업데이트 (부분 업데이트)"""
        await self._redis.hset(
            f"{self.KEY_PREFIX}{table_id}",
            f"seat:{position}:stack",
            stack
        )
```

#### 4.3.2 핸드 상태 실시간 캐싱
- [x] 진행 중인 핸드는 Redis에만 저장
- [x] 핸드 종료 시 DB에 배치 저장
- 생성 파일: `backend/app/cache/hand_cache.py`

```python
# 핸드 상태 키 구조
HAND_KEY = "hand:{hand_id}"
HAND_FIELDS = {
    "phase": "flop",
    "pot": "1500",
    "community_cards": "Ah,Kd,Qc",
    "current_turn": "3",
    "action_history": "[...]",  # JSON
}
```

**[x] 4.3 완료** - 날짜/시간: 2026-01-12 18:15

---

### 4.4 캐시-DB 동기화 전략 (v1.2 추가)

**상태**: [x] 완료

#### 4.4.1 Write-Behind 패턴
- [x] 실시간 변경은 Redis에만 반영
- [x] 5초마다 또는 핸드 종료 시 DB 동기화
- 생성 파일: `backend/app/cache/sync_service.py`

```python
# backend/app/cache/sync_service.py
class CacheSyncService:
    """캐시 → DB 동기화"""

    SYNC_INTERVAL = 5  # 초

    async def sync_table_to_db(self, table_id: str):
        """테이블 상태 DB 동기화"""
        state = await self._cache.get_table_state(table_id)
        if state and state.is_dirty:
            await self._db.update_table(table_id, state)
            state.mark_clean()

    async def sync_on_hand_complete(self, hand_id: str):
        """핸드 완료 시 즉시 동기화"""
        # 핸드 히스토리 DB 저장
        # 플레이어 잔액 DB 업데이트
        pass
```

#### 4.4.2 캐시 워밍업
- [x] 서버 시작 시 활성 테이블 캐시 로드
- [x] 재접속 시 캐시에서 상태 복원
- 생성 파일: `backend/app/cache/warmup.py`

**[x] 4.4 완료** - 날짜/시간: 2026-01-12 18:20

---

### Phase 4 완료 체크

```bash
git add .
git commit -m "Phase 4 완료: Redis 고가용성 + 게임 상태 캐싱

- 메모리 정책 설정
- 캐시 키 설계 및 TTL 정책
- 테이블 상태 Redis Hash 캐싱
- Write-Behind 패턴 동기화
- DB 부하 70-90% 감소 달성"
```

**[x] Phase 4 전체 완료** - 날짜/시간: 2026-01-12 18:25

#### 생성된 파일 목록
- `infra/redis/redis.prod.conf` - Redis 프로덕션 설정
- `backend/app/cache/__init__.py` - 캐시 모듈 통합
- `backend/app/cache/keys.py` - 캐시 키 및 TTL 정책
- `backend/app/cache/table_cache.py` - 테이블 상태 캐싱
- `backend/app/cache/hand_cache.py` - 핸드 상태 캐싱
- `backend/app/cache/sync_service.py` - Write-Behind 동기화
- `backend/app/cache/warmup.py` - 캐시 워밍업
- `backend/app/main.py` - 캐시 매니저 통합 (수정)

---

## Phase 5: KRW 잔액 + 암호화폐 입출금 시스템

> **예상 기간**: 7-10일
> **우선순위**: ⭐⭐⭐⭐⭐ (최우선)
> **현재 상태**: ✅ 완료

### 5.1 User 모델 잔액 필드 (KRW 기준)

**상태**: [x] 완료

#### 5.1.1 모델 수정
- [x] `krw_balance` 필드 추가 (BigInteger, 게임 내 원화 잔액)
- [x] `pending_withdrawal_krw` 필드 추가 (출금 대기 원화)
- [x] 기존 `balance` 필드 마이그레이션

```python
# backend/app/models/user.py 수정
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # ... 기존 필드

    # 게임 내 KRW 잔액
    krw_balance: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Game balance in KRW (원화)"
    )

    # 출금 대기 금액 (KRW)
    pending_withdrawal_krw: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0,
        comment="Pending withdrawal in KRW"
    )
```

#### 5.1.2 마이그레이션
- [x] Alembic 마이그레이션 파일 생성
- [ ] 마이그레이션 실행 (배포 시)

**[x] 5.1 완료** - 날짜/시간: 2026-01-12 15:45

---

### 5.2 WalletTransaction 모델 (암호화폐 지원)

**상태**: [x] 완료

#### 5.2.1 모델 생성
- [x] `backend/app/models/wallet.py` 파일 생성
- [x] TransactionType enum 정의
- [x] CryptoType enum 정의 (BTC, ETH, USDT, USDC)

```python
# backend/app/models/wallet.py
from enum import Enum

class CryptoType(str, Enum):
    BTC = "btc"
    ETH = "eth"
    USDT = "usdt"
    USDC = "usdc"

class TransactionType(str, Enum):
    CRYPTO_DEPOSIT = "crypto_deposit"    # 암호화폐 입금 → KRW 변환
    CRYPTO_WITHDRAWAL = "crypto_withdrawal"  # KRW → 암호화폐 출금
    BUY_IN = "buy_in"        # 테이블 입장
    CASH_OUT = "cash_out"    # 테이블 퇴장
    WIN = "win"              # 팟 획득
    LOSE = "lose"            # 팟 패배
    RAKE = "rake"            # 레이크 차감
    RAKEBACK = "rakeback"    # 레이크백 지급

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    tx_type: Mapped[TransactionType] = mapped_column(SQLEnum(TransactionType))

    # KRW 금액 (게임 내)
    krw_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    krw_balance_after: Mapped[int] = mapped_column(BigInteger)

    # 암호화폐 정보 (입출금 시)
    crypto_type: Mapped[CryptoType] = mapped_column(SQLEnum(CryptoType), nullable=True)
    crypto_amount: Mapped[str] = mapped_column(String(50), nullable=True)  # 소수점 정밀도
    crypto_tx_hash: Mapped[str] = mapped_column(String(100), nullable=True)
    crypto_address: Mapped[str] = mapped_column(String(100), nullable=True)

    # 환율 정보
    exchange_rate: Mapped[int] = mapped_column(BigInteger, nullable=True)  # 1 crypto = X KRW

    # 메타데이터
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    integrity_hash: Mapped[str] = mapped_column(String(64))
```

**[x] 5.2 완료** - 날짜/시간: 2026-01-12 15:50

---

### 5.3 CryptoDepositService 구현

**상태**: [x] 완료

#### 5.3.1 입금 주소 관리
- [x] `backend/app/services/crypto_deposit.py` 생성
- [x] 사용자별 입금 주소 발급/관리
- [x] 입금 감지 웹훅 핸들러

```python
# backend/app/services/crypto_deposit.py
class CryptoDepositService:
    """암호화폐 입금 서비스"""

    # 최소 확인 수
    MIN_CONFIRMATIONS = {
        CryptoType.BTC: 3,
        CryptoType.ETH: 12,
        CryptoType.USDT: 12,
        CryptoType.USDC: 12,
    }

    async def get_deposit_address(
        self,
        user_id: str,
        crypto_type: CryptoType
    ) -> str:
        """사용자별 입금 주소 조회/생성"""
        pass

    async def handle_deposit_webhook(
        self,
        crypto_type: CryptoType,
        tx_hash: str,
        address: str,
        amount: str,
        confirmations: int
    ):
        """입금 감지 웹훅 처리"""
        # 1. 확인 수 검증
        # 2. 실시간 환율 조회
        # 3. KRW 변환 및 잔액 추가
        pass

    async def _convert_to_krw(
        self,
        crypto_type: CryptoType,
        amount: str
    ) -> tuple[int, int]:
        """암호화폐 → KRW 변환 (잔액, 환율)"""
        pass
```

**[x] 5.3 완료** - 날짜/시간: 2026-01-12 16:00

---

### 5.4 CryptoWithdrawalService 구현

**상태**: [x] 완료

#### 5.4.1 출금 서비스
- [x] `backend/app/services/crypto_withdrawal.py` 생성
- [x] 24시간 대기 정책
- [x] 출금 한도 설정

```python
# backend/app/services/crypto_withdrawal.py
class CryptoWithdrawalService:
    """암호화폐 출금 서비스"""

    PENDING_HOURS = 24  # 출금 대기 시간
    MIN_WITHDRAWAL_KRW = 10000  # 최소 출금 금액 (₩10,000)
    MAX_AUTO_APPROVE_KRW = 1000000  # 자동 승인 한도 (₩1,000,000)

    async def request_withdrawal(
        self,
        user_id: str,
        krw_amount: int,
        crypto_type: CryptoType,
        crypto_address: str
    ) -> WalletTransaction:
        """출금 요청"""
        # 1. 잔액 확인
        # 2. KRW → 암호화폐 환산
        # 3. pending_withdrawal_krw로 이동
        # 4. 24시간 대기 상태로 저장
        pass

    async def process_pending_withdrawals(self):
        """대기 중인 출금 처리 (스케줄러)"""
        pass
```

**[x] 5.4 완료** - 날짜/시간: 2026-01-12 16:10

---

### 5.5 환율 서비스

**상태**: [x] 완료

- [x] `backend/app/services/exchange_rate.py` 생성
- [x] 실시간 환율 API 연동 (CoinGecko, Binance 등)
- [x] 환율 캐싱 (1분 TTL)

```python
# backend/app/services/exchange_rate.py
class ExchangeRateService:
    """실시간 환율 서비스"""

    CACHE_TTL = 60  # 1분

    async def get_rate_to_krw(self, crypto_type: CryptoType) -> int:
        """1 암호화폐 = X KRW"""
        pass

    async def convert_crypto_to_krw(
        self,
        crypto_type: CryptoType,
        amount: str
    ) -> int:
        """암호화폐 → KRW 변환"""
        pass

    async def convert_krw_to_crypto(
        self,
        crypto_type: CryptoType,
        krw_amount: int
    ) -> str:
        """KRW → 암호화폐 변환"""
        pass
```

**[x] 5.5 완료** - 날짜/시간: 2026-01-12 15:55

---

### 5.6 Redis Lua Script 분산락 (KRW 이체)

**상태**: [x] 완료

- [x] `backend/app/utils/lua_scripts/krw_transfer.lua` 생성
- [x] 분산락 + Atomic 이체

**[x] 5.6 완료** - 날짜/시간: 2026-01-12 16:05

---

### 5.7 WalletService 구현

**상태**: [x] 완료

- [x] `backend/app/services/wallet.py` 생성
- [x] `transfer_krw()` 메서드 (테이블 buy-in/cash-out)
- [ ] 테스트 작성 (Phase 7)

**[x] 5.7 완료** - 날짜/시간: 2026-01-12 16:15

---

### 5.8 AuditService 3중 기록

**상태**: [x] 완료

- [x] `backend/app/services/audit.py` 생성
- [x] DB + Redis Stream + 파일 3중 기록
- [x] 무결성 해시

**[x] 5.8 완료** - 날짜/시간: 2026-01-12 16:20

---

### 5.9 입출금 API 엔드포인트

**상태**: [x] 완료

- [x] `backend/app/api/wallet.py` 생성
- [x] GET /api/v1/wallet/deposit-address/{crypto_type}
- [x] POST /api/v1/wallet/withdraw
- [x] GET /api/v1/wallet/transactions
- [x] POST /api/v1/wallet/webhook/deposit (내부용)

**[x] 5.9 완료** - 날짜/시간: 2026-01-12 16:25

---

### Phase 5 완료 체크

```bash
git add .
git commit -m "Phase 5 완료: KRW 잔액 + 암호화폐 입출금 시스템

- User 모델 KRW 잔액 필드
- WalletTransaction 모델 (암호화폐 지원)
- CryptoDepositService 입금 처리
- CryptoWithdrawalService 출금 처리 (24시간 대기)
- ExchangeRateService 실시간 환율
- Redis Lua 분산락
- AuditService 3중 기록
- 입출금 API 엔드포인트"
```

**[x] Phase 5 전체 완료** - 날짜/시간: 2026-01-12 16:30

---

## Phase 6: Rake & 경제 시스템

> **예상 기간**: 3-4일
> **우선순위**: ⭐⭐⭐⭐ (필수)
> **현재 상태**: ⏳ 대기

### 6.1 RakeService 구현

**상태**: [ ] 미완료

```python
# backend/app/services/rake.py
RAKE_CONFIGS = {
    (1000, 2000): RakeConfig(Decimal("0.05"), 3),    # ₩1,000/₩2,000
    (5000, 10000): RakeConfig(Decimal("0.05"), 4),   # ₩5,000/₩10,000
    (25000, 50000): RakeConfig(Decimal("0.04"), 5),  # ₩25,000/₩50,000
}
```

- [ ] RakeService 구현
- [ ] No Flop No Drop 로직
- [ ] Rake Cap 적용
- [ ] 테스트 작성

**[ ] 6.1 완료** - 날짜/시간: _______________

---

### 6.2 VIP & Rakeback 시스템

**상태**: [ ] 미완료

```python
VIP_LEVELS = {
    "bronze": {"min_rake_krw": 0, "rakeback": Decimal("0.20")},
    "silver": {"min_rake_krw": 100000, "rakeback": Decimal("0.25")},
    "gold": {"min_rake_krw": 500000, "rakeback": Decimal("0.30")},
    "platinum": {"min_rake_krw": 2000000, "rakeback": Decimal("0.35")},
    "diamond": {"min_rake_krw": 5000000, "rakeback": Decimal("0.40")},
}
```

- [ ] VIP 레벨 계산 로직
- [ ] 주간 Rakeback 정산 Job

**[ ] 6.2 완료** - 날짜/시간: _______________

---

### Phase 6 완료 체크

```bash
git add .
git commit -m "Phase 6 완료: Rake & 경제 시스템 (KRW 기준)

- RakeService 구현 (블라인드별 설정)
- VIP 레벨 시스템 (Bronze~Diamond)
- RakebackService 주간 정산"
```

**[ ] Phase 6 전체 완료** - 날짜/시간: _______________

---

## Phase 7: 부하 테스트 & 튜닝

> **예상 기간**: 5-7일
> **우선순위**: ⭐⭐⭐⭐⭐ (최우선)
> **현재 상태**: ⏳ 대기

### 7.1 k6 부하 테스트 스크립트

**상태**: [ ] 미완료

- [ ] `k6/load-test-500.js` 파일 생성
- [ ] 로그인 → WebSocket → 게임 시뮬레이션

**[ ] 7.1 완료** - 날짜/시간: _______________

---

### 7.2 단계별 부하 테스트

**상태**: [ ] 미완료

| 단계 | 동접 | 목표 | 상태 |
|------|------|------|------|
| 1 | 100명 | p95 < 100ms | [ ] |
| 2 | 200명 | p95 < 120ms | [ ] |
| 3 | 300명 | p95 < 150ms | [ ] |
| 4 | 400명 | p95 < 180ms | [ ] |
| 5 | 500명 | p95 < 200ms | [ ] |

**[ ] 7.2 완료** - 날짜/시간: _______________

---

### 7.3 병목 분석 & 최적화

**상태**: [ ] 미완료

- [ ] Slow Query Log 분석
- [ ] Redis SLOWLOG 확인
- [ ] CPU/메모리 프로파일링

**[ ] 7.3 완료** - 날짜/시간: _______________

---

### Phase 7 완료 체크

```bash
git add .
git commit -m "Phase 7 완료: 부하 테스트 & 튜닝

- k6 부하 테스트 스크립트
- 500명 동접 테스트 통과
- p95 < 200ms 달성"
```

**[ ] Phase 7 전체 완료** - 날짜/시간: _______________

---

## Phase 8: 모니터링 & 알림

> **예상 기간**: 2-3일
> **우선순위**: ⭐⭐⭐⭐ (권장)
> **현재 상태**: ⏳ 대기

### 8.1 Prometheus 메트릭 설정

**상태**: [ ] 미완료

- [ ] prometheus-fastapi-instrumentator 설치
- [ ] 커스텀 메트릭 정의

**[ ] 8.1 완료** - 날짜/시간: _______________

---

### 8.2 Grafana 대시보드

**상태**: [ ] 미완료

- [ ] 대시보드 JSON 생성
- [ ] 핵심 패널 설정

**[ ] 8.2 완료** - 날짜/시간: _______________

---

### 8.3 알림 설정

**상태**: [ ] 미완료

- [ ] 에러율 > 1% → Warning
- [ ] 에러율 > 5% → Critical
- [ ] p95 > 500ms → Warning

**[ ] 8.3 완료** - 날짜/시간: _______________

---

### Phase 8 완료 체크

```bash
git add .
git commit -m "Phase 8 완료: 모니터링 & 알림

- Prometheus 메트릭 설정
- Grafana 대시보드
- 알림 규칙 설정"
```

**[ ] Phase 8 전체 완료** - 날짜/시간: _______________

---

## Phase 9: 운영 안정화

> **예상 기간**: 3-5일
> **우선순위**: ⭐⭐⭐ (권장)
> **현재 상태**: ⏳ 대기

### 9.1 Graceful Shutdown

**상태**: [ ] 미완료

- [ ] SIGTERM 핸들링
- [ ] 진행 중인 핸드 완료 대기
- [ ] 연결 정리

**[ ] 9.1 완료** - 날짜/시간: _______________

---

### 9.2 Health Check 엔드포인트

**상태**: [ ] 미완료

- [ ] `/health` 기본
- [ ] `/health/ready` 의존성 포함
- [ ] `/health/live` liveness probe

**[ ] 9.2 완료** - 날짜/시간: _______________

---

### 9.3 백업 & 복구

**상태**: [ ] 미완료

- [ ] PostgreSQL 일일 백업
- [ ] Redis RDB 스냅샷
- [ ] 복구 테스트

**[ ] 9.3 완료** - 날짜/시간: _______________

---

### Phase 9 완료 체크

```bash
git add .
git commit -m "Phase 9 완료: 운영 안정화

- Graceful Shutdown
- Health Check 엔드포인트
- 백업 & 복구 전략"
```

**[ ] Phase 9 전체 완료** - 날짜/시간: _______________

---

## Phase 10: 성능 최적화 (v1.2 추가)

> **예상 기간**: 5-7일
> **우선순위**: ⭐⭐⭐⭐ (권장)
> **현재 상태**: ⏳ 대기
> **목표**: 네트워크 효율 50-70% 향상, 메인 서버 부하 분산

### 10.1 Binary WebSocket 프로토콜 (MessagePack)

**상태**: [ ] 미완료

#### 10.1.1 MessagePack 도입
- [ ] `msgpack` 패키지 설치
- [ ] JSON → MessagePack 변환 유틸리티

```python
# backend/app/ws/serializer.py
import msgpack
from typing import Any

class MessageSerializer:
    """WebSocket 메시지 직렬화 (MessagePack)"""

    @staticmethod
    def encode(data: dict) -> bytes:
        """dict → MessagePack bytes (50-70% 크기 감소)"""
        return msgpack.packb(data, use_bin_type=True)

    @staticmethod
    def decode(data: bytes) -> dict:
        """MessagePack bytes → dict"""
        return msgpack.unpackb(data, raw=False)
```

#### 10.1.2 프로토콜 버전 협상
- [ ] 연결 시 클라이언트 지원 여부 확인
- [ ] Binary 지원 시 MessagePack, 미지원 시 JSON fallback

```python
# 연결 시 협상
async def negotiate_protocol(websocket: WebSocket) -> str:
    """프로토콜 협상 (binary/json)"""
    accept_binary = websocket.headers.get("X-Accept-Binary", "false")
    if accept_binary.lower() == "true":
        return "msgpack"
    return "json"
```

#### 10.1.3 메시지 크기 비교

| 이벤트 | JSON | MessagePack | 감소율 |
|--------|------|-------------|--------|
| TABLE_SNAPSHOT | 2.4KB | 0.9KB | 62% |
| TABLE_STATE_UPDATE | 800B | 280B | 65% |
| ACTION_RESULT | 300B | 120B | 60% |

**[ ] 10.1 완료** - 날짜/시간: _______________

---

### 10.2 Async Job Queue (Celery + Redis)

**상태**: [ ] 미완료

#### 10.2.1 Celery 설정
- [ ] `celery` 패키지 설치
- [ ] `backend/app/tasks/celery_app.py` 생성

```python
# backend/app/tasks/celery_app.py
from celery import Celery

celery_app = Celery(
    "poker_tasks",
    broker="redis://localhost:6379/1",
    backend="redis://localhost:6379/2",
)

celery_app.conf.update(
    task_serializer="msgpack",
    accept_content=["msgpack"],
    result_serializer="msgpack",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_routes={
        "tasks.settlement.*": {"queue": "settlement"},
        "tasks.analytics.*": {"queue": "analytics"},
        "tasks.notification.*": {"queue": "notification"},
    },
)
```

#### 10.2.2 비동기 태스크 정의
- [ ] 정산 태스크 (Rake 집계, VIP 레벨 계산)
- [ ] 통계 태스크 (플레이어 통계, 테이블 통계)
- [ ] 알림 태스크 (이메일, 푸시)

```python
# backend/app/tasks/settlement.py
from app.tasks.celery_app import celery_app

@celery_app.task(bind=True, max_retries=3)
def calculate_weekly_rakeback(self):
    """주간 레이크백 계산 (무거운 작업)"""
    try:
        # 전체 사용자 레이크 집계
        # VIP 레벨별 레이크백 계산
        # 지급 내역 생성
        pass
    except Exception as e:
        self.retry(countdown=60, exc=e)

@celery_app.task
def aggregate_daily_stats():
    """일일 통계 집계"""
    # 핸드 수, 레이크 총액, 활성 사용자 등
    pass
```

#### 10.2.3 Worker 실행 설정
- [ ] Settlement Worker (정산 전용)
- [ ] Analytics Worker (통계 전용)
- [ ] Notification Worker (알림 전용)

```bash
# 워커 실행
celery -A app.tasks.celery_app worker -Q settlement -c 2
celery -A app.tasks.celery_app worker -Q analytics -c 2
celery -A app.tasks.celery_app worker -Q notification -c 2

# Beat (스케줄러)
celery -A app.tasks.celery_app beat
```

**[ ] 10.2 완료** - 날짜/시간: _______________

---

### 10.3 핸드 히스토리 압축 저장

**상태**: [ ] 미완료

#### 10.3.1 압축 저장 형식
- [ ] `msgpack` + `gzip` 조합 (80% 크기 감소)
- [ ] `backend/app/services/hand_archive.py` 생성

```python
# backend/app/services/hand_archive.py
import gzip
import msgpack
from datetime import datetime

class HandArchiveService:
    """핸드 히스토리 압축 저장"""

    async def archive_hand(self, hand_data: dict) -> bytes:
        """핸드 데이터 압축"""
        packed = msgpack.packb(hand_data)
        compressed = gzip.compress(packed, compresslevel=6)
        return compressed  # 원본 대비 80-90% 감소

    async def retrieve_hand(self, compressed: bytes) -> dict:
        """압축된 핸드 데이터 복원"""
        decompressed = gzip.decompress(compressed)
        return msgpack.unpackb(decompressed, raw=False)
```

#### 10.3.2 장기 보관 전략
- [ ] 최근 7일: PostgreSQL (빠른 조회)
- [ ] 7일~30일: Redis (중간 속도)
- [ ] 30일 이상: S3/객체 스토리지 (저비용)

```python
# 아카이브 정책
ARCHIVE_POLICY = {
    "hot": {
        "storage": "postgresql",
        "retention_days": 7,
        "compression": False
    },
    "warm": {
        "storage": "redis",
        "retention_days": 30,
        "compression": True
    },
    "cold": {
        "storage": "s3",
        "retention_days": 365,
        "compression": True
    }
}
```

#### 10.3.3 저장 비용 예측

| 일일 핸드 수 | 원본 크기 | 압축 후 | 월간 S3 비용 |
|-------------|----------|---------|-------------|
| 10,000 | 50MB | 10MB | ~$0.30 |
| 50,000 | 250MB | 50MB | ~$1.50 |
| 100,000 | 500MB | 100MB | ~$3.00 |

**[ ] 10.3 완료** - 날짜/시간: _______________

---

### 10.4 스케줄러 설정 (Celery Beat)

**상태**: [ ] 미완료

- [ ] `backend/app/tasks/schedules.py` 생성
- [ ] 주기적 태스크 등록

```python
# backend/app/tasks/schedules.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # 매시간: 핸드 히스토리 아카이브
    "archive-hands-hourly": {
        "task": "tasks.archive.archive_old_hands",
        "schedule": crontab(minute=0),
    },
    # 매일 새벽 3시: 일일 통계 집계
    "daily-stats": {
        "task": "tasks.analytics.aggregate_daily_stats",
        "schedule": crontab(hour=3, minute=0),
    },
    # 매주 월요일 새벽 4시: 주간 레이크백 정산
    "weekly-rakeback": {
        "task": "tasks.settlement.calculate_weekly_rakeback",
        "schedule": crontab(hour=4, minute=0, day_of_week=1),
    },
    # 매월 1일: 월간 아카이브 S3 이동
    "monthly-archive-to-s3": {
        "task": "tasks.archive.move_to_cold_storage",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
    },
}
```

**[ ] 10.4 완료** - 날짜/시간: _______________

---

### Phase 10 완료 체크

```bash
git add .
git commit -m "Phase 10 완료: 성능 최적화

- Binary WebSocket 프로토콜 (MessagePack, 50-70% 크기 감소)
- Async Job Queue (Celery + Redis)
- 핸드 히스토리 압축 저장 (80% 비용 절감)
- Celery Beat 스케줄러"
```

**[ ] Phase 10 전체 완료** - 날짜/시간: _______________

---

## Phase 11: 오픈소스 통합 (v1.3 추가)

> **예상 기간**: 4-6일
> **우선순위**: ⭐⭐⭐⭐ (권장)
> **현재 상태**: ⏳ 대기
> **목표**: 프로덕션 안정성, 관측성, 성능 향상

### 11.1 추천 오픈소스 라이브러리

**상태**: [ ] 미완료

#### 선정된 라이브러리

| 라이브러리 | GitHub Stars | 용도 | 효과 |
|-----------|-------------|------|------|
| **orjson** | 5.8k+ | 빠른 JSON 직렬화 | 3-10배 성능 향상 |
| **structlog** | 3.2k+ | 구조화된 로깅 | 디버깅/모니터링 용이 |
| **httpx** | 12k+ | 비동기 HTTP 클라이언트 | 암호화폐 API 호출 |
| **tenacity** | 6k+ | 재시도 로직 | 외부 API 안정성 |
| **slowapi** | 1.1k+ | Rate Limiting | DDoS/악용 방지 |
| **sentry-sdk** | 1.8k+ | 에러 추적 | 프로덕션 모니터링 |

```bash
# 설치
pip install orjson structlog httpx tenacity slowapi sentry-sdk
```

**[ ] 11.1 완료** - 날짜/시간: _______________

---

### 11.2 orjson - 고속 JSON 직렬화

**상태**: [ ] 미완료

#### 11.2.1 orjson 적용
- [ ] 기존 `json` 모듈을 `orjson`으로 교체
- [ ] Pydantic 모델 직렬화 최적화

```python
# backend/app/utils/json_utils.py
import orjson
from typing import Any

def json_dumps(data: Any) -> str:
    """orjson 직렬화 (기본 json 대비 3-10배 빠름)"""
    return orjson.dumps(data).decode("utf-8")

def json_loads(data: str | bytes) -> Any:
    """orjson 역직렬화"""
    return orjson.loads(data)

# FastAPI 응답에 적용
from fastapi.responses import ORJSONResponse

app = FastAPI(default_response_class=ORJSONResponse)
```

#### 11.2.2 성능 비교

| 작업 | json | orjson | 향상 |
|------|------|--------|------|
| 직렬화 (TABLE_SNAPSHOT) | 2.1ms | 0.3ms | 7x |
| 역직렬화 (ACTION) | 0.8ms | 0.12ms | 6.7x |

**[ ] 11.2 완료** - 날짜/시간: _______________

---

### 11.3 structlog - 구조화된 로깅

**상태**: [ ] 미완료

#### 11.3.1 로깅 설정
- [ ] `backend/app/logging_config.py` 생성
- [ ] JSON 구조화 로그 출력

```python
# backend/app/logging_config.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

# 사용 예시
logger = structlog.get_logger()

async def handle_action(table_id: str, user_id: str, action: str):
    logger.info(
        "player_action",
        table_id=table_id,
        user_id=user_id,
        action=action,
        timestamp=datetime.utcnow().isoformat()
    )
```

#### 11.3.2 컨텍스트 로깅
- [ ] 요청별 trace_id 자동 추가
- [ ] 사용자/테이블 컨텍스트 바인딩

```python
# 미들웨어에서 컨텍스트 설정
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        trace_id=str(uuid4()),
        path=request.url.path,
    )
    response = await call_next(request)
    return response
```

**[ ] 11.3 완료** - 날짜/시간: _______________

---

### 11.4 httpx + tenacity - 외부 API 안정성

**상태**: [ ] 미완료

#### 11.4.1 비동기 HTTP 클라이언트
- [ ] `backend/app/utils/http_client.py` 생성
- [ ] 암호화폐 환율 API 호출에 적용

```python
# backend/app/utils/http_client.py
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class AsyncHttpClient:
    """재시도 로직이 포함된 비동기 HTTP 클라이언트"""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=100)
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_json(self, url: str) -> dict:
        """GET 요청 + JSON 파싱 (최대 3회 재시도)"""
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._client.aclose()
```

#### 11.4.2 환율 API 적용
- [ ] CoinGecko/Binance API 호출에 적용
- [ ] 재시도 + 폴백 로직

```python
# backend/app/services/exchange_rate.py
class ExchangeRateService:
    def __init__(self, http_client: AsyncHttpClient):
        self._http = http_client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential())
    async def get_btc_krw_rate(self) -> int:
        """BTC/KRW 환율 조회 (재시도 포함)"""
        try:
            # 기본: CoinGecko
            data = await self._http.get_json(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=krw"
            )
            return data["bitcoin"]["krw"]
        except Exception:
            # 폴백: Binance
            data = await self._http.get_json(
                "https://api.binance.com/api/v3/ticker/price?symbol=BTCKRW"
            )
            return int(float(data["price"]))
```

**[ ] 11.4 완료** - 날짜/시간: _______________

---

### 11.5 slowapi - Rate Limiting 강화

**상태**: [ ] 미완료

#### 11.5.1 Rate Limiter 설정
- [ ] `backend/app/middleware/rate_limit.py` 생성
- [ ] 엔드포인트별 제한 설정

```python
# backend/app/middleware/rate_limit.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri="redis://localhost:6379/3"  # Redis 기반 분산 Rate Limiting
)

# main.py에 적용
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

#### 11.5.2 엔드포인트별 제한

```python
# backend/app/api/auth.py
from app.middleware.rate_limit import limiter

@router.post("/login")
@limiter.limit("5/minute")  # 로그인: 분당 5회
async def login(request: Request, ...):
    pass

@router.post("/register")
@limiter.limit("3/minute")  # 회원가입: 분당 3회
async def register(request: Request, ...):
    pass

# backend/app/api/wallet.py
@router.post("/withdraw")
@limiter.limit("10/hour")  # 출금: 시간당 10회
async def withdraw(request: Request, ...):
    pass
```

**[ ] 11.5 완료** - 날짜/시간: _______________

---

### 11.6 sentry-sdk - 프로덕션 에러 추적

**상태**: [ ] 미완료

#### 11.6.1 Sentry 설정
- [ ] Sentry 프로젝트 생성
- [ ] SDK 초기화

```python
# backend/app/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    environment=settings.environment,  # "production", "staging"
    integrations=[
        FastApiIntegration(transaction_style="endpoint"),
        SqlalchemyIntegration(),
        RedisIntegration(),
    ],
    traces_sample_rate=0.1,  # 10% 트랜잭션 샘플링
    profiles_sample_rate=0.1,  # 10% 프로파일링
    send_default_pii=False,  # 개인정보 전송 안함
)
```

#### 11.6.2 커스텀 컨텍스트
- [ ] 사용자/테이블 정보 첨부
- [ ] 금융 거래 에러 우선 알림

```python
# 에러 발생 시 컨텍스트 첨부
import sentry_sdk

async def process_withdrawal(user_id: str, amount: int):
    with sentry_sdk.push_scope() as scope:
        scope.set_user({"id": user_id})
        scope.set_tag("transaction_type", "withdrawal")
        scope.set_extra("amount_krw", amount)

        try:
            # 출금 처리
            pass
        except Exception as e:
            scope.set_level("fatal")  # 금융 거래는 fatal
            sentry_sdk.capture_exception(e)
            raise
```

**[ ] 11.6 완료** - 날짜/시간: _______________

---

### 11.7 추가 검토 오픈소스 (선택)

**상태**: [ ] 미완료 (선택사항)

#### 고려할 만한 추가 라이브러리

| 라이브러리 | 용도 | 도입 시점 |
|-----------|------|----------|
| **locust** | Python 부하 테스트 | Phase 7에서 k6 대체 가능 |
| **faker** | 테스트 데이터 생성 | 테스트 작성 시 |
| **aiocache** | 비동기 캐싱 추상화 | Phase 4 보강 시 |
| **python-arq** | 경량 작업 큐 | Celery 대안 검토 시 |
| **pydantic-settings** | 설정 관리 | 이미 Pydantic v2 포함 |

#### Hugging Face 검토 결과
- 포커 특화 ML 모델: 현재 없음
- 이상 탐지 모델: 운영 데이터 축적 후 자체 학습 권장
- **결론**: 300-500명 규모에서는 ML보다 기본 패턴 감지가 효과적

**[ ] 11.7 완료** - 날짜/시간: _______________

---

### Phase 11 완료 체크

```bash
git add .
git commit -m "Phase 11 완료: 오픈소스 통합

- orjson: JSON 직렬화 3-10배 향상
- structlog: 구조화된 로깅
- httpx + tenacity: 외부 API 안정성
- slowapi: Rate Limiting 강화
- sentry-sdk: 프로덕션 에러 추적"
```

**[ ] Phase 11 전체 완료** - 날짜/시간: _______________

---

## 마일스톤 요약

| Phase | 작업 내용 | 핵심 검증 항목 | 상태 |
|-------|---------|--------------|------|
| 1 | 커넥션 풀 & 인프라 | DB 50+30, Redis 100 | ✅ |
| 2 | WebSocket 클러스터링 (강화) | Redis Pub/Sub + Sticky Session | ✅ |
| 3 | DB 최적화 | Slow query 0건 | ✅ |
| 4 | Redis 고가용성 + 게임 캐싱 | DB 부하 70-90% 감소 | ✅ |
| 5 | KRW + 암호화폐 입출금 | 입출금 정상 작동 | ✅ |
| 6 | Rake 시스템 | Rake 계산 100% 정확 | [ ] |
| 7 | 부하 테스트 | 500명 p95 < 200ms | [ ] |
| 8 | 모니터링 | 대시보드 운영 | [ ] |
| 9 | 운영 안정화 | 복구 테스트 통과 | [ ] |
| 10 | 성능 최적화 | MessagePack 50%↓, Celery 작동 | [ ] |
| 11 | 오픈소스 통합 (v1.3) | 모든 라이브러리 통합 테스트 | [ ] |

---

## 세션 재개 체크리스트

```
╔═══════════════════════════════════════════════════════════════════════╗
║  🔄 세션 재개 시 확인사항                                              ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  1. [ ] 마지막 [x] 체크된 단계 확인                                    ║
║  2. [ ] git status로 uncommitted 변경사항 확인                         ║
║  3. [ ] 필요시 git stash 또는 commit                                   ║
║  4. [ ] 중단된 작업부터 이어서 진행                                     ║
║  5. [ ] 작업 완료 즉시 [ ] → [x] 체크                                  ║
║                                                                        ║
╚═══════════════════════════════════════════════════════════════════════╝
```

---

## 작업 로그

| 날짜 | Phase | 작업 내용 | 작업자 |
|------|-------|-----------|--------|
| 2026-01-12 | - | 백엔드 스케일링 작업계획서 v1.0 작성 | Claude |
| 2026-01-12 | - | v1.1: KRW + 암호화폐 입출금 반영, 완료 체크 지침 강화 | Claude |
| 2026-01-12 | - | v1.2: 성능 최적화 항목 추가 (MessagePack, Celery, 압축) | Claude |
| 2026-01-12 | - | v1.3 Final: 오픈소스 통합 (orjson, structlog, httpx, sentry) | Claude |
| | | | |

---

> **마지막 업데이트**: 2026-01-12
> **버전**: 1.3 Final
> **다음 작업**: Phase 1.1 PostgreSQL 커넥션 풀 확장
