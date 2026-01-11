# PokerKit 텍사스 홀덤 웹서비스 - 구현 작업계획서

> 최종 업데이트: 2026-01-11
> 스펙 문서 완료 → 구현 단계 진입

---

## 1. 현재 상태 요약

### 완료된 작업

| 구분 | 상태 | 비고 |
|------|------|------|
| 스펙 문서 (P0~P6) | ✅ 완료 | 22개 문서 |
| PokerKit 설치 | ✅ 완료 | v0.7.2 |
| 가상환경 설정 | ✅ 완료 | backend/.venv |
| 의존성 설치 | ✅ 완료 | FastAPI, SQLAlchemy 등 |

### 미완료 작업

- [ ] Docker 인프라 (PostgreSQL, Redis)
- [ ] 백엔드 코드 구현
- [ ] 프론트엔드 코드 구현
- [ ] 통합 테스트
- [ ] 배포

---

## 2. 구현 단계별 작업 순서

### I1: 백엔드 인프라 구축

**목표**: Docker 환경에서 PostgreSQL, Redis 실행

**산출물**:
- [ ] `infra/docker/docker-compose.dev.yml`
- [ ] `backend/alembic/` 마이그레이션 설정
- [ ] `.env.example` 파일
- [ ] DB 스키마 마이그레이션

**작업 내용**:
```bash
1. infra/docker 폴더 생성
2. docker-compose.dev.yml 작성 (PostgreSQL 16, Redis 7)
3. .env.example 작성
4. Alembic 초기화 및 마이그레이션 작성
5. 테스트 연결 확인
```

**참고 문서**: [01-setup-local.md](docs/01-setup-local.md), [02-env-vars.md](docs/02-env-vars.md)

---

### I2: 게임 엔진 래퍼 구현

**목표**: PokerKit을 래핑한 게임 엔진 레이어 구현

**산출물**:
- [ ] `backend/app/engine/core.py` - PokerKit 래퍼
- [ ] `backend/app/engine/state.py` - 상태 모델
- [ ] `backend/app/engine/actions.py` - 액션 처리
- [ ] `backend/app/engine/snapshot.py` - 직렬화
- [ ] 유닛 테스트 (90%+ 커버리지)

**작업 내용**:
```python
# 핵심 클래스
class PokerKitWrapper:      # PokerKit 직접 호출 캡슐화
class StateManager:         # 상태 생성/전이/버전 관리
class ActionProcessor:      # 액션 검증/처리
class SnapshotSerializer:   # JSON 직렬화/역직렬화
```

**참고 문서**: [10-engine-architecture.md](docs/10-engine-architecture.md), [11-engine-state-model.md](docs/11-engine-state-model.md)

---

### I3: REST API 구현

**목표**: 인증, 방 관리, 히스토리 API 구현

**산출물**:
- [ ] `backend/app/api/auth.py` - 로그인/회원가입
- [ ] `backend/app/api/rooms.py` - 방 CRUD
- [ ] `backend/app/api/users.py` - 프로필 관리
- [ ] `backend/app/models/` - DB 모델
- [ ] `backend/app/schemas/` - Pydantic 스키마

**작업 내용**:
```
POST /api/auth/register    # 회원가입
POST /api/auth/login       # 로그인
POST /api/auth/refresh     # 토큰 갱신
GET  /api/rooms            # 방 목록
POST /api/rooms            # 방 생성
GET  /api/rooms/:id        # 방 상세
POST /api/rooms/:id/join   # 방 입장
```

**참고 문서**: [04-folder-structure.md](docs/04-folder-structure.md)

---

### I4: WebSocket 게이트웨이 구현

**목표**: 실시간 게임 통신 구현

**산출물**:
- [ ] `backend/app/ws/gateway.py` - WS 연결 관리
- [ ] `backend/app/ws/lobby.py` - 로비 채널
- [ ] `backend/app/ws/table.py` - 테이블 채널
- [ ] `backend/app/orchestrator/` - 테이블 오케스트레이터

**작업 내용**:
```
이벤트 구현:
- SUBSCRIBE_LOBBY / LOBBY_SNAPSHOT
- SUBSCRIBE_TABLE / TABLE_SNAPSHOT
- ACTION_REQUEST / ACTION_RESULT
- TURN_PROMPT / SHOWDOWN_RESULT
- PING / PONG (하트비트)
```

**참고 문서**: [20-realtime-protocol-v1.md](docs/20-realtime-protocol-v1.md), [21-error-codes-v1.md](docs/21-error-codes-v1.md)

---

### I5: 프론트엔드 UI 구현

**목표**: Next.js 기반 게임 UI 구현

**산출물**:
- [ ] `frontend/` 폴더 전체
- [ ] 로비 페이지 (방 목록, 생성, 입장)
- [ ] 테이블 페이지 (게임 플레이)
- [ ] 프로필 페이지

**작업 내용**:
```
1. Next.js 14 + TypeScript 프로젝트 생성
2. Tailwind CSS 설정
3. 공통 컴포넌트 (Button, Modal, Toast)
4. 로비 컴포넌트 (RoomList, RoomCard)
5. 테이블 컴포넌트 (Table, Seat, ActionPanel)
6. WebSocket 훅 (useWebSocket, useTable)
7. Zustand 상태 관리
```

**참고 문서**: [30-ui-ia.md](docs/30-ui-ia.md), [31-table-ui-spec.md](docs/31-table-ui-spec.md), [33-ui-components.md](docs/33-ui-components.md)

---

### I6: 통합 테스트

**목표**: E2E 시나리오 테스트 통과

**산출물**:
- [ ] `backend/tests/integration/` - API 통합 테스트
- [ ] `frontend/tests/e2e/` - E2E 테스트
- [ ] MVP 체크리스트 100% 통과

**필수 시나리오**:
```
[ ] 방 생성 → 입장 → 착석 → 핸드 시작
[ ] 2~6명 턴 이동 정상
[ ] 콜/레이즈/폴드 기본 액션
[ ] 핸드 종료/쇼다운 결과
[ ] 재접속 후 상태 복구
[ ] 중복 클릭 방지 (멱등성)
[ ] 관전 모드
```

**참고 문서**: [50-test-plan.md](docs/50-test-plan.md)

---

### I7: 스테이징 배포

**목표**: 스테이징 환경 배포 완료

**산출물**:
- [ ] `infra/docker/docker-compose.prod.yml`
- [ ] Dockerfile (backend, frontend)
- [ ] 배포 스크립트
- [ ] 스모크 테스트 통과

**참고 문서**: [52-deploy-staging.md](docs/52-deploy-staging.md)

---

## 3. 의존성 그래프

```
I0 (환경설정) ✅
    │
    ▼
I1 (인프라) ─────────────────────┐
    │                           │
    ▼                           ▼
I2 (엔진)                    I5 (프론트)
    │                           │
    ▼                           │
I3 (REST API)                   │
    │                           │
    ▼                           │
I4 (WebSocket) ◄────────────────┘
    │
    ▼
I6 (통합테스트)
    │
    ▼
I7 (배포)
```

---

## 4. 핵심 기술 스택

| 구분 | 기술 | 버전 |
|------|------|------|
| 게임 엔진 | PokerKit | 0.7.2 |
| 백엔드 | FastAPI | 0.128+ |
| ORM | SQLAlchemy | 2.0+ |
| DB | PostgreSQL | 16 |
| 캐시/Pub-Sub | Redis | 7 |
| 프론트엔드 | Next.js | 14 |
| 상태관리 | Zustand | 4+ |
| 스타일 | Tailwind CSS | 3+ |

---

## 5. 품질 기준

| 항목 | 기준 |
|------|------|
| 엔진 테스트 커버리지 | 90%+ |
| API 테스트 커버리지 | 80%+ |
| E2E 시나리오 | 100% 통과 |
| 린트 에러 | 0개 |
| 타입 에러 | 0개 |

---

## 6. 세션 재개 가이드

```bash
# 1. 체크포인트 확인
cat PROGRESS_CHECKPOINT.md

# 2. 가상환경 활성화
cd backend && source .venv/bin/activate

# 3. 현재 단계 확인 후 작업 재개
```

---

## 관련 문서

- [PROGRESS_CHECKPOINT.md](PROGRESS_CHECKPOINT.md) - 진행 상황 추적
- [WORKPLAN_PokerKit_Commercial_ClaudeCode_v2.md](WORKPLAN_PokerKit_Commercial_ClaudeCode_v2.md) - 원본 작업계획서
- [docs/](docs/) - 전체 스펙 문서

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-01-11 | 최초 작성 (스펙 완료 후 구현 단계 정의) |
