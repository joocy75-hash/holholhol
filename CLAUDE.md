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
