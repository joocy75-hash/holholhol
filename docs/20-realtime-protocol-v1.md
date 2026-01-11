# 실시간 이벤트 프로토콜 v1

> WebSocket 기반 실시간 통신 프로토콜 명세

---

## 1. 개요

### 1.1 목적

클라이언트-서버 간 실시간 양방향 통신을 위한 이벤트 프로토콜을 정의한다.

### 1.2 설계 원칙

| 원칙 | 설명 |
|------|------|
| **서버 Authoritative** | 모든 게임 상태 결정은 서버에서 수행 |
| **멱등성** | 동일 요청은 동일 결과 보장 |
| **순서 보장** | stateVersion으로 이벤트 순서 검증 |
| **재접속 복구** | 끊김 후 완전한 상태 복구 지원 |

---

## 2. 연결 관리

### 2.1 WebSocket 엔드포인트

```
ws://{host}/ws?token={access_token}
wss://{host}/ws?token={access_token}  # Production
```

### 2.2 연결 흐름

```
1. Client → WebSocket 연결 요청 (token 포함)
2. Server → 토큰 검증
3. Server → CONNECTION_STATE (connected)
4. Client → 채널 구독 (SUBSCRIBE_LOBBY / SUBSCRIBE_TABLE)
5. Server → 초기 스냅샷 전송
```

### 2.3 Heartbeat

```
Client → PING (매 15초)
Server → PONG
```

- 30초 내 PONG 미수신 시 연결 끊김으로 간주
- 서버는 60초 내 PING 미수신 시 연결 종료

---

## 3. 메시지 Envelope

### 3.1 공통 구조

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

### 3.2 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `type` | string | Y | 이벤트 타입 |
| `ts` | number | Y | Unix timestamp (ms) |
| `traceId` | string | Y | 분산 추적 ID |
| `requestId` | string | N | 클라이언트 요청 ID (요청 시 필수) |
| `payload` | object | Y | 이벤트 데이터 |
| `version` | string | Y | 프로토콜 버전 |

---

## 4. 이벤트 목록

### 4.1 시스템 이벤트

| 이벤트 | 방향 | 설명 |
|--------|------|------|
| `PING` | C→S | 클라이언트 heartbeat |
| `PONG` | S→C | 서버 heartbeat 응답 |
| `CONNECTION_STATE` | S→C | 연결 상태 변경 |
| `ERROR` | S→C | 에러 응답 |

### 4.2 로비 이벤트

| 이벤트 | 방향 | 설명 |
|--------|------|------|
| `SUBSCRIBE_LOBBY` | C→S | 로비 채널 구독 |
| `UNSUBSCRIBE_LOBBY` | C→S | 로비 채널 구독 해제 |
| `LOBBY_SNAPSHOT` | S→C | 로비 전체 상태 |
| `LOBBY_UPDATE` | S→C | 로비 상태 변경 |
| `ROOM_CREATE_REQUEST` | C→S | 방 생성 요청 |
| `ROOM_CREATE_RESULT` | S→C | 방 생성 결과 |
| `ROOM_JOIN_REQUEST` | C→S | 방 입장 요청 |
| `ROOM_JOIN_RESULT` | S→C | 방 입장 결과 |

### 4.3 테이블 이벤트

| 이벤트 | 방향 | 설명 |
|--------|------|------|
| `SUBSCRIBE_TABLE` | C→S | 테이블 채널 구독 |
| `UNSUBSCRIBE_TABLE` | C→S | 테이블 채널 구독 해제 |
| `TABLE_SNAPSHOT` | S→C | 테이블 전체 상태 |
| `TABLE_STATE_UPDATE` | S→C | 테이블 상태 변경 |
| `TURN_PROMPT` | S→C | 턴 알림 (가능 액션, 타이머) |
| `SEAT_REQUEST` | C→S | 착석 요청 |
| `SEAT_RESULT` | S→C | 착석 결과 |
| `LEAVE_REQUEST` | C→S | 퇴장 요청 |
| `LEAVE_RESULT` | S→C | 퇴장 결과 |

### 4.4 액션 이벤트

| 이벤트 | 방향 | 설명 |
|--------|------|------|
| `ACTION_REQUEST` | C→S | 게임 액션 요청 |
| `ACTION_RESULT` | S→C | 액션 처리 결과 |
| `SHOWDOWN_RESULT` | S→C | 쇼다운 결과 |
| `HAND_RESULT` | S→C | 핸드 종료 결과 |

### 4.5 채팅 이벤트

| 이벤트 | 방향 | 설명 |
|--------|------|------|
| `CHAT_MESSAGE` | C→S/S→C | 채팅 메시지 |
| `CHAT_HISTORY` | S→C | 채팅 히스토리 |

---

## 5. Payload 스키마

### 5.1 CONNECTION_STATE

```json
{
  "state": "connected",
  "userId": "user-123",
  "sessionId": "session-456"
}
```

| state | 설명 |
|-------|------|
| `connected` | 연결 완료 |
| `reconnecting` | 재연결 중 |
| `recovered` | 재연결 후 복구 완료 |
| `disconnected` | 연결 종료 |

### 5.2 LOBBY_SNAPSHOT

```json
{
  "rooms": [
    {
      "roomId": "room-1",
      "name": "초보자 테이블",
      "blinds": "10/20",
      "maxSeats": 6,
      "playerCount": 4,
      "status": "active"
    }
  ],
  "announcements": [],
  "stateVersion": 1
}
```

### 5.3 TABLE_SNAPSHOT

```json
{
  "tableId": "table-123",
  "config": {
    "maxSeats": 6,
    "smallBlind": 10,
    "bigBlind": 20,
    "minBuyIn": 400,
    "maxBuyIn": 2000,
    "turnTimeoutSeconds": 30
  },
  "seats": [
    {
      "position": 0,
      "player": {
        "userId": "user-1",
        "nickname": "Player1",
        "avatarUrl": null
      },
      "stack": 1500,
      "status": "active",
      "betAmount": 20
    }
  ],
  "hand": {
    "handId": "hand-456",
    "handNumber": 1,
    "phase": "flop",
    "communityCards": ["Ah", "Kd", "Qc"],
    "pot": {
      "mainPot": 100,
      "sidePots": []
    },
    "currentTurn": 2,
    "minRaise": 40
  },
  "dealerPosition": 0,
  "myPosition": 2,
  "myHoleCards": ["As", "Ks"],
  "stateVersion": 15,
  "updatedAt": "2026-01-11T10:30:00Z"
}
```

### 5.4 TABLE_STATE_UPDATE

```json
{
  "tableId": "table-123",
  "changes": {
    "phase": "turn",
    "communityCards": ["Ah", "Kd", "Qc", "7h"],
    "pot": {
      "mainPot": 200,
      "sidePots": []
    },
    "currentTurn": 3,
    "seats": [
      {
        "position": 2,
        "stack": 1400,
        "betAmount": 0,
        "lastAction": {
          "type": "call",
          "amount": 20
        }
      }
    ]
  },
  "stateVersion": 16,
  "previousVersion": 15
}
```

### 5.5 TURN_PROMPT

```json
{
  "tableId": "table-123",
  "position": 2,
  "allowedActions": [
    { "type": "fold" },
    { "type": "check" },
    { "type": "bet", "minAmount": 20, "maxAmount": 1400 },
    { "type": "all_in", "amount": 1400 }
  ],
  "turnDeadlineAt": "2026-01-11T10:30:30Z",
  "stateVersion": 16
}
```

### 5.6 ACTION_REQUEST

```json
{
  "tableId": "table-123",
  "actionType": "raise",
  "amount": 100
}
```

### 5.7 ACTION_RESULT

```json
{
  "success": true,
  "tableId": "table-123",
  "action": {
    "type": "raise",
    "amount": 100,
    "position": 2
  },
  "newStateVersion": 17
}
```

실패 시:
```json
{
  "success": false,
  "tableId": "table-123",
  "errorCode": "INVALID_ACTION",
  "errorMessage": "Raise amount below minimum"
}
```

### 5.8 SHOWDOWN_RESULT

```json
{
  "tableId": "table-123",
  "handId": "hand-456",
  "showdownHands": [
    {
      "position": 0,
      "holeCards": ["Ah", "Kh"],
      "handRank": "flush",
      "handDescription": "Ace-high Flush"
    },
    {
      "position": 2,
      "holeCards": ["As", "Ks"],
      "handRank": "two_pair",
      "handDescription": "Two Pair, Aces and Kings"
    }
  ],
  "winners": [
    {
      "position": 0,
      "amount": 200,
      "potType": "main"
    }
  ],
  "stateVersion": 20
}
```

### 5.9 ERROR

```json
{
  "errorCode": "AUTH_REQUIRED",
  "errorMessage": "Authentication required",
  "details": {}
}
```

---

## 6. 채널 구독

### 6.1 로비 채널

```json
// 구독
{ "type": "SUBSCRIBE_LOBBY" }

// 구독 해제
{ "type": "UNSUBSCRIBE_LOBBY" }
```

### 6.2 테이블 채널

```json
// 구독 (플레이어 또는 관전자)
{
  "type": "SUBSCRIBE_TABLE",
  "payload": {
    "tableId": "table-123",
    "mode": "player"  // "player" | "spectator"
  }
}

// 구독 해제
{
  "type": "UNSUBSCRIBE_TABLE",
  "payload": {
    "tableId": "table-123"
  }
}
```

---

## 7. 재접속 프로토콜

### 7.1 재접속 흐름

```
1. 연결 끊김 감지
2. Client → 재연결 시도 (exponential backoff)
3. Server → CONNECTION_STATE (reconnecting)
4. Client → 이전 구독 채널 재구독
5. Server → TABLE_SNAPSHOT (전체 상태)
6. Server → CONNECTION_STATE (recovered)
7. Client → 정상 플레이 재개
```

### 7.2 재접속 중 클라이언트 동작

- 액션 버튼 비활성화
- "재연결 중..." 배너 표시
- 로컬 상태 유지 (낙관적 UI)

### 7.3 재접속 타임아웃

| 항목 | 값 |
|------|-----|
| 최대 재시도 횟수 | 10회 |
| 초기 대기 시간 | 1초 |
| 최대 대기 시간 | 30초 |
| 총 타임아웃 | 60초 |

---

## 8. 관련 문서

- [21-error-codes-v1.md](./21-error-codes-v1.md) - 에러 코드 명세
- [22-idempotency-ordering.md](./22-idempotency-ordering.md) - 멱등성/순서 규칙
- [10-engine-architecture.md](./10-engine-architecture.md) - 엔진 아키텍처
