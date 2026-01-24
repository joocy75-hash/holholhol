# Claude Code 작업 지침

## 구조
- `backend/app/` - FastAPI (ws/, engine/, bot/, api/, services/)
- `frontend/src/` - Next.js 14 + TypeScript

## 코드 규칙
- 일반 코더가 아닌 온라인 게임 기획 및 개발자의 관점에서 생각하라.
- 기존 패턴 따르기
- 변수명 영어, 주석/에러메시지 한글 OK
- snake_case(백엔드) ↔ camelCase(프론트) Pydantic alias 사용

## WebSocket
- 메시지: `{type, payload}` (클라→서버), `{type, ts, traceId, payload}` (서버→클라)
- 이벤트 정의: `backend/app/ws/events.py`
- **중요**: 메시지 수신은 반드시 `recv()` 직접 호출 (폴링 X)

## 봇 시스템
- URL 설정: `BOT_API_URL`, `BOT_WS_URL` 환경변수
- 봇 API: `/api/v1/bots/*` (인증 미적용 상태)

## 테스트
```bash
cd backend && pytest tests/ -v
```

## 주의
- 수정 전 관련 코드 먼저 읽기
- 과도한 추상화/리팩토링 금지
- 요청한 것만 수정

---

## 아키텍처 방향성 (게임 상태 관리)

### 현재 상태 (프로토타입)
- `GameManager` → 메모리 전용 (OK for now)
- `CacheService` → 사용 안 함 (Cache-Aside 패턴, 게임에 부적합)

### 목표 아키텍처 (업계 표준)
```
GameManager ──▶ Redis (주 저장소) ──▶ DB (영구 백업)
```

1. **GameManager → Redis 직접 저장**
   - 상태 변경 시 Redis에 저장 (플레이어 착석, 스택 변경, 핸드 진행)
   - 서버 재시작 시 Redis에서 복구
   - 키 패턴: `game:table:{id}`

2. **핸드 완료 → DB 히스토리 저장**
   - 핸드 결과, 승자, 팟 등 영구 기록
   - 통계/분석용 데이터

### 구현 시점
- **지금**: 메모리 방식 유지, 기능 개발에 집중
- **베타 테스트 전**: Redis 영속성 구현
- **출시 전**: DB 히스토리 저장 구현

### 참고
- 기존 `backend/app/cache/` 는 Cache-Aside 패턴 (게임 상태용 아님)
- 새로 구현 시 GameManager에 직접 Redis 연동 추가


---

## 데이터베이스 요구사항

### PostgreSQL 필수
이 프로젝트는 PostgreSQL 특화 기능을 사용합니다. 다른 데이터베이스로 마이그레이션 시 주의가 필요합니다.

### 사용 중인 PostgreSQL 특화 문법

| 기능 | 사용 위치 | 설명 |
|------|----------|------|
| `INTERVAL` | statistics_service.py, bot_detector.py | 시간 간격 계산 (`NOW() - INTERVAL '30 days'`) |
| `array_agg()` | anti_collusion.py | 배열 집계 함수 |
| `EXTRACT(EPOCH FROM ...)` | anti_collusion.py, bot_detector.py | 타임스탬프에서 초 추출 |
| `DATE_TRUNC()` | statistics_service.py | 날짜 자르기 (week, month) |
| `COALESCE()` | statistics_service.py | NULL 대체 (표준 SQL이지만 자주 사용) |
| `NOW()` | statistics_service.py | 현재 시간 |

### 마이그레이션 시 대체 방안

- **MySQL**: `INTERVAL` 문법 동일, `array_agg` → `GROUP_CONCAT`, `EXTRACT` → `TIMESTAMPDIFF`
- **SQLite**: 대부분 지원 안 함, 애플리케이션 레벨 처리 필요

### 권장 사항
- PostgreSQL 12+ 사용
- 개발/테스트/프로덕션 모두 PostgreSQL 사용 권장

---

## 어드민 프론트엔드 세션 관리

### 세션 만료 문제 방지
어드민 로그인 후 세션이 자꾸 끊기는 문제가 발생하면:

1. **브라우저 localStorage 확인**
   - `admin-auth` 키에 `tokenExpiry` 값이 있는지 확인
   - 없으면 로그아웃 후 다시 로그인

2. **JWT 만료 시간 설정**
   - `admin-backend/.env`: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440` (24시간)
   - 프론트엔드 로그인 시 `tokenExpiry` 저장 필수

3. **asyncpg UUID 캐스팅**
   - 잘못된 예: `:partner_id::uuid` (파라미터 충돌)
   - 올바른 예: `CAST(:partner_id AS uuid)`

### 개발 중 체크리스트
- [ ] 백엔드 서버 실행 중인지 확인 (`localhost:8001`)
- [ ] 로그인 후 `tokenExpiry`가 localStorage에 저장되는지 확인
- [ ] 401 에러 발생 시 콘솔 로그 확인

---

## 라우트 구조

### 어드민 (`:3001`)
| 라우트 | 설명 |
|--------|------|
| `/login` | 어드민 로그인 |
| `/` | 대시보드 |
| `/users`, `/users/[id]` | 사용자 관리 |
| `/rooms`, `/rooms/[id]` | 방 관리 |
| `/hands`, `/hands/[id]` | 핸드 기록 |
| `/bans` | 제재 관리 |
| `/deposits` | 입금 관리 |
| `/withdrawals` | 출금 관리 |
| `/partners`, `/partners/[id]` | 파트너 관리 |
| `/settlements` | 정산 관리 |
| `/announcements` | 이벤트/공지 |
| `/crypto`, `/crypto/approvals` | 암호화폐 |

### 파트너 포털 (`:3001`)
| 라우트 | 설명 |
|--------|------|
| `/partner-login` | 파트너 로그인 |
| `/partner/dashboard` | 대시보드 |
| `/partner/referrals` | 추천 회원 |
| `/partner/settlements` | 정산 내역 |

### 유저 (`:3000`)
| 라우트 | 설명 |
|--------|------|
| `/login` | 로그인/회원가입 |
| `/`, `/lobby` | 로비 |
| `/table/[id]` | 게임 테이블 |
| `/profile` | 프로필 |
| `/wallet` | 지갑 |
| `/history` | 핸드 기록 |
| `/events` | 이벤트 |
| `/settings` | 설정 |

---

## 파트너 통계 시스템

### 아키텍처
파트너(총판) 통계는 **사전 집계 방식**을 사용하여 조회 성능을 최적화합니다.

```
User 테이블 (원본 데이터)
    ↓ [배치 집계]
partner_daily_stats (사전 집계 테이블)
    ↓ [빠른 조회]
파트너 API (/stats/daily, /stats/monthly)
```

### 주요 컴포넌트

| 컴포넌트 | 파일 | 설명 |
|----------|------|------|
| 모델 | `app/models/partner_stats.py` | `PartnerDailyStats` 테이블 정의 |
| 서비스 | `app/services/partner_stats.py` | `PartnerStatsService` - 집계 및 조회 로직 |
| API | `app/api/partner.py` | `/stats/daily`, `/stats/monthly` 엔드포인트 |
| 마이그레이션 | `alembic/versions/cd8f2579ace8_*.py` | 테이블 생성 마이그레이션 |

### 데이터베이스 스키마

```sql
CREATE TABLE partner_daily_stats (
  id SERIAL PRIMARY KEY,
  partner_id UUID NOT NULL REFERENCES partners(id) ON DELETE CASCADE,
  date DATE NOT NULL,

  -- 신규 가입자 통계
  new_referrals BIGINT DEFAULT 0,

  -- 베팅 통계 (KRW)
  total_bet_amount BIGINT DEFAULT 0,
  total_rake BIGINT DEFAULT 0,
  total_net_loss BIGINT DEFAULT 0,

  -- 수수료 (commission_type에 따라 계산)
  commission_amount BIGINT DEFAULT 0,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (partner_id, date)
);

CREATE INDEX ix_partner_daily_stats_partner_date ON partner_daily_stats(partner_id, date);
```

### 통계 집계 방식

#### 수동 집계 (현재)
```python
from app.services.partner_stats import PartnerStatsService
from datetime import date

# 특정 날짜 집계
service = PartnerStatsService(db)
await service.aggregate_daily_stats(target_date=date(2026, 1, 24))

# 특정 파트너만 집계
await service.aggregate_daily_stats(
    target_date=date(2026, 1, 24),
    partner_id="uuid-here"
)
```

#### 자동 집계 (향후 구현 예정)
Celery Beat를 사용하여 매일 자정에 자동 집계:
```python
# backend/app/tasks/partner_stats.py (예정)
@celery_app.task
def aggregate_partner_daily_stats():
    """매일 자정 KST 실행"""
    yesterday = date.today() - timedelta(days=1)
    # ...
```

### 성능 최적화

| 항목 | Before (실시간 집계) | After (사전 집계) |
|------|---------------------|------------------|
| 90일 통계 조회 | 2-5초 (전체 User 스캔) | <100ms (인덱스 조회) |
| DB 부하 | 높음 (매 요청마다 집계) | 낮음 (조회만) |
| 정확도 | 실시간 | 최대 24시간 지연 |

### 주의사항

1. **실시간 통계 아님**: 일일 통계는 최대 24시간 지연될 수 있음
2. **과거 데이터 수정**: User의 통계 컬럼 수정 시 재집계 필요
3. **초기 데이터**: 신규 파트너는 수동으로 과거 데이터 집계 필요

### API 사용 예시

```bash
# 일별 통계 조회 (최근 30일)
GET /api/v1/partner/stats/daily?days=30

# 월별 통계 조회 (최근 12개월)
GET /api/v1/partner/stats/monthly?months=12
```

### 트러블슈팅

**통계가 비어있음**:
- 원인: 아직 집계가 실행되지 않음
- 해결: `aggregate_daily_stats()` 수동 실행

**통계 수치가 부정확함**:
- 원인: User 테이블 데이터 변경 후 재집계 안 함
- 해결: 해당 날짜 재집계 (UPSERT 방식으로 자동 업데이트)
