# 🃏 PokerKit - 실시간 텍사스 홀덤 포커 백엔드

실시간 멀티플레이어 텍사스 홀덤 포커 게임을 위한 백엔드 서버입니다.

## 📋 목차

- [프로젝트 개요](#프로젝트-개요)
- [기술 스택](#기술-스택)
- [빠른 시작](#빠른-시작)
- [API 문서](#api-문서)
- [WebSocket 프로토콜](#websocket-프로토콜)
- [프론트엔드 연동 가이드](#프론트엔드-연동-가이드)
- [문서 목록](#문서-목록)

---

## 프로젝트 개요

### 핵심 기능

| 기능 | 설명 |
|------|------|
| 🔐 인증 | JWT 기반 인증, 2FA 지원 |
| 🏠 로비 | 방 목록, 생성, 입장 |
| 🎮 게임 | 실시간 텍사스 홀덤 |
| 💰 지갑 | 칩 관리, 암호화폐 입출금 |
| 📊 VIP | 레이크백, VIP 등급 시스템 |

### 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│  PostgreSQL │
│   (React)   │     │  (FastAPI)  │     │             │
└─────────────┘     └──────┬──────┘     └─────────────┘
                          │
                    ┌─────▼─────┐
                    │   Redis   │
                    │  (Cache)  │
                    └───────────┘
```

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Framework | FastAPI (Python 3.11+) |
| Database | PostgreSQL + SQLAlchemy |
| Cache | Redis |
| WebSocket | FastAPI WebSocket |
| Auth | JWT (PyJWT) |
| Task Queue | Celery |

---

## 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd pokerkit

# 환경변수 설정
cp .env.example .env
# .env 파일 수정
```

### 2. Docker로 실행 (권장)

```bash
docker-compose up -d
```

### 3. 로컬 개발 환경

```bash
cd backend

# 가상환경 생성
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# DB 마이그레이션
alembic upgrade head

# 서버 실행
uvicorn app.main:app --reload --port 8000
```

### 4. 테스트 실행

```bash
cd backend
pytest tests/ -v
```

---

## API 문서

서버 실행 후 아래 URL에서 API 문서 확인:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 주요 엔드포인트

#### 인증 (Auth)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/auth/register` | 회원가입 |
| POST | `/api/v1/auth/login` | 로그인 |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 |
| POST | `/api/v1/auth/logout` | 로그아웃 |
| POST | `/api/v1/auth/2fa/setup` | 2FA 설정 |
| POST | `/api/v1/auth/2fa/verify` | 2FA 인증 |

#### 방 (Rooms)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/rooms` | 방 목록 조회 |
| POST | `/api/v1/rooms` | 방 생성 |
| GET | `/api/v1/rooms/{id}` | 방 상세 조회 |
| POST | `/api/v1/rooms/{id}/join` | 방 입장 |

#### 사용자 (Users)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/users/me` | 내 프로필 |
| PATCH | `/api/v1/users/me` | 프로필 수정 |

---

## WebSocket 프로토콜

### 연결

```javascript
const ws = new WebSocket('ws://localhost:8000/ws?token=<access_token>');
```

### 메시지 형식

모든 메시지는 다음 형식을 따릅니다:

```json
{
  "type": "EVENT_TYPE",
  "ts": 1704067200000,
  "traceId": "abc-123-def",
  "requestId": "client-req-001",
  "payload": {},
  "version": "v1"
}
```

### 주요 이벤트

#### 클라이언트 → 서버

| 이벤트 | 설명 |
|--------|------|
| `PING` | Heartbeat |
| `SUBSCRIBE_LOBBY` | 로비 구독 |
| `SUBSCRIBE_TABLE` | 테이블 구독 |
| `ACTION_REQUEST` | 게임 액션 |
| `CHAT_MESSAGE` | 채팅 |

#### 서버 → 클라이언트

| 이벤트 | 설명 |
|--------|------|
| `PONG` | Heartbeat 응답 |
| `CONNECTION_STATE` | 연결 상태 |
| `LOBBY_SNAPSHOT` | 로비 전체 상태 |
| `TABLE_SNAPSHOT` | 테이블 전체 상태 |
| `TABLE_STATE_UPDATE` | 테이블 상태 변경 |
| `TURN_PROMPT` | 턴 알림 |
| `ACTION_RESULT` | 액션 결과 |
| `SHOWDOWN_RESULT` | 쇼다운 결과 |
| `ERROR` | 에러 |

---

## 프론트엔드 연동 가이드

### 1. 인증 흐름

```typescript
// 1. 로그인
const response = await fetch('/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});
const { tokens, user } = await response.json();

// 2. 토큰 저장
localStorage.setItem('accessToken', tokens.accessToken);
localStorage.setItem('refreshToken', tokens.refreshToken);

// 3. API 요청 시 토큰 포함
const rooms = await fetch('/api/v1/rooms', {
  headers: { 'Authorization': `Bearer ${tokens.accessToken}` }
});
```

### 2. WebSocket 연결

```typescript
class PokerWebSocket {
  private ws: WebSocket;
  private pingInterval: number;

  connect(token: string) {
    this.ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);
    
    this.ws.onopen = () => {
      // 15초마다 PING 전송
      this.pingInterval = setInterval(() => {
        this.send({ type: 'PING', payload: {} });
      }, 15000);
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };
  }

  send(message: any) {
    this.ws.send(JSON.stringify({
      ...message,
      ts: Date.now(),
      traceId: crypto.randomUUID(),
      version: 'v1'
    }));
  }

  // 로비 구독
  subscribeLobby() {
    this.send({ type: 'SUBSCRIBE_LOBBY', payload: {} });
  }

  // 테이블 구독
  subscribeTable(tableId: string) {
    this.send({
      type: 'SUBSCRIBE_TABLE',
      payload: { tableId, mode: 'player' }
    });
  }

  // 게임 액션
  sendAction(tableId: string, actionType: string, amount?: number) {
    this.send({
      type: 'ACTION_REQUEST',
      payload: { tableId, actionType, amount }
    });
  }
}
```

### 3. 상태 관리 (예: Zustand)

```typescript
interface GameState {
  connectionStatus: 'connected' | 'reconnecting' | 'disconnected';
  lobby: Room[];
  currentTable: TableState | null;
  myPosition: number | null;
}

const useGameStore = create<GameState>((set) => ({
  connectionStatus: 'disconnected',
  lobby: [],
  currentTable: null,
  myPosition: null,

  handleMessage: (message: any) => {
    switch (message.type) {
      case 'CONNECTION_STATE':
        set({ connectionStatus: message.payload.state });
        break;
      case 'LOBBY_SNAPSHOT':
        set({ lobby: message.payload.rooms });
        break;
      case 'TABLE_SNAPSHOT':
        set({
          currentTable: message.payload,
          myPosition: message.payload.myPosition
        });
        break;
      case 'TABLE_STATE_UPDATE':
        set((state) => ({
          currentTable: applyChanges(state.currentTable, message.payload.changes)
        }));
        break;
    }
  }
}));
```

### 4. 재연결 처리

```typescript
class ReconnectManager {
  private maxRetries = 10;
  private retryCount = 0;
  private baseDelay = 1000;

  async reconnect(connect: () => Promise<void>) {
    while (this.retryCount < this.maxRetries) {
      try {
        await connect();
        this.retryCount = 0;
        return;
      } catch (error) {
        this.retryCount++;
        const delay = Math.min(
          this.baseDelay * Math.pow(2, this.retryCount),
          30000
        );
        await new Promise(r => setTimeout(r, delay));
      }
    }
    throw new Error('Max reconnection attempts reached');
  }
}
```

### 5. 에러 처리

```typescript
const ERROR_HANDLERS: Record<string, () => void> = {
  'AUTH_TOKEN_EXPIRED': () => refreshToken(),
  'AUTH_SESSION_EXPIRED': () => redirectToLogin(),
  'STATE_STALE_VERSION': () => requestSnapshot(),
  'RATE_LIMIT_EXCEEDED': () => showRateLimitWarning(),
};

function handleError(error: { errorCode: string; errorMessage: string }) {
  const handler = ERROR_HANDLERS[error.errorCode];
  if (handler) {
    handler();
  } else {
    showToast(error.errorMessage);
  }
}
```

---

## 문서 목록

### 설정 및 개발

| 문서 | 설명 |
|------|------|
| [01-setup-local.md](docs/01-setup-local.md) | 로컬 환경 설정 |
| [02-env-vars.md](docs/02-env-vars.md) | 환경변수 설명 |
| [03-dev-workflow.md](docs/03-dev-workflow.md) | 개발 워크플로 |
| [04-folder-structure.md](docs/04-folder-structure.md) | 폴더 구조 |

### 게임 엔진

| 문서 | 설명 |
|------|------|
| [10-engine-architecture.md](docs/10-engine-architecture.md) | 엔진 아키텍처 |
| [11-engine-state-model.md](docs/11-engine-state-model.md) | 상태 모델 |

### 실시간 통신

| 문서 | 설명 |
|------|------|
| [20-realtime-protocol-v1.md](docs/20-realtime-protocol-v1.md) | WebSocket 프로토콜 |
| [21-error-codes-v1.md](docs/21-error-codes-v1.md) | 에러 코드 |
| [22-idempotency-ordering.md](docs/22-idempotency-ordering.md) | 멱등성/순서 규칙 |

### UI 스펙

| 문서 | 설명 |
|------|------|
| [30-ui-ia.md](docs/30-ui-ia.md) | UI 정보 아키텍처 |
| [31-table-ui-spec.md](docs/31-table-ui-spec.md) | 테이블 UI 스펙 |
| [32-lobby-ui-spec.md](docs/32-lobby-ui-spec.md) | 로비 UI 스펙 |
| [33-ui-components.md](docs/33-ui-components.md) | UI 컴포넌트 |

### 게임 로직

| 문서 | 설명 |
|------|------|
| [40-reconnect-recovery.md](docs/40-reconnect-recovery.md) | 재연결 복구 |
| [41-state-consistency.md](docs/41-state-consistency.md) | 상태 일관성 |
| [42-timer-turn-rules.md](docs/42-timer-turn-rules.md) | 타이머/턴 규칙 |

### 운영

| 문서 | 설명 |
|------|------|
| [50-test-plan.md](docs/50-test-plan.md) | 테스트 계획 |
| [51-observability.md](docs/51-observability.md) | 모니터링 |
| [52-deploy-staging.md](docs/52-deploy-staging.md) | 배포 가이드 |

---

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

서드파티 라이선스는 [LICENSES](LICENSES/) 폴더와 [NOTICE](NOTICE) 파일을 참조하세요.
