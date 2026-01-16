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
