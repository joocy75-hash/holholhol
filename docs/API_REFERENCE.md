# API Reference

> REST API 및 WebSocket 이벤트 상세 명세

---

## REST API

### Base URL

```
Development: http://localhost:8000/api/v1
Production:  https://api.example.com/api/v1
```

### 공통 헤더

```
Authorization: Bearer <access_token>
Content-Type: application/json
```

### 공통 에러 응답

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  },
  "traceId": "abc-123-def"
}
```

---

## 인증 API

### POST /auth/register

회원가입

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "Password123",
  "nickname": "player1"
}
```

**Response (201):**
```json
{
  "user": {
    "id": "uuid",
    "nickname": "player1",
    "avatarUrl": null,
    "balance": 0
  },
  "tokens": {
    "accessToken": "eyJ...",
    "refreshToken": "eyJ...",
    "tokenType": "Bearer",
    "expiresIn": 1800
  }
}
```

**Errors:**
- `409` EMAIL_EXISTS - 이메일 중복
- `409` NICKNAME_EXISTS - 닉네임 중복

---

### POST /auth/login

로그인

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "Password123"
}
```

**Response (200):**
```json
{
  "user": {
    "id": "uuid",
    "nickname": "player1",
    "avatarUrl": null,
    "balance": 1000
  },
  "tokens": {
    "accessToken": "eyJ...",
    "refreshToken": "eyJ...",
    "tokenType": "Bearer",
    "expiresIn": 1800
  }
}
```

**Errors:**
- `401` INVALID_CREDENTIALS - 잘못된 이메일/비밀번호
- `403` ACCOUNT_INACTIVE - 비활성 계정

---

### POST /auth/refresh

토큰 갱신

**Request Body:**
```json
{
  "refreshToken": "eyJ..."
}
```

**Response (200):**
```json
{
  "accessToken": "eyJ...",
  "refreshToken": "eyJ...",
  "tokenType": "Bearer",
  "expiresIn": 1800
}
```

**Errors:**
- `401` AUTH_INVALID_TOKEN - 유효하지 않은 토큰
- `401` AUTH_TOKEN_EXPIRED - 만료된 토큰

---

### POST /auth/logout

로그아웃

**Headers:** Authorization 필수

**Response (200):**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

## 방 API

### GET /rooms

방 목록 조회

**Query Parameters:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| page | int | 1 | 페이지 번호 |
| pageSize | int | 20 | 페이지 크기 |
| status | string | - | 필터: waiting, playing |

**Response (200):**
```json
{
  "rooms": [
    {
      "id": "room-uuid",
      "name": "초보자 테이블",
      "blinds": "10/20",
      "maxSeats": 6,
      "playerCount": 4,
      "status": "playing",
      "isPrivate": false
    }
  ],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalItems": 50,
    "totalPages": 3
  }
}
```

---

### POST /rooms

방 생성

**Headers:** Authorization 필수

**Request Body:**
```json
{
  "name": "My Room",
  "description": "Welcome!",
  "maxSeats": 6,
  "smallBlind": 10,
  "bigBlind": 20,
  "buyInMin": 400,
  "buyInMax": 2000,
  "isPrivate": false,
  "password": null
}
```

**Validation Rules:**
- `maxSeats`: 2-9
- `bigBlind`: smallBlind * 2 이상
- `buyInMax`: buyInMin 이상
- `password`: isPrivate=true일 때 필수 (4-20자)

**Response (201):**
```json
{
  "id": "room-uuid",
  "name": "My Room",
  "description": "Welcome!",
  "config": {
    "maxSeats": 6,
    "smallBlind": 10,
    "bigBlind": 20,
    "buyInMin": 400,
    "buyInMax": 2000,
    "turnTimeout": 30,
    "isPrivate": false
  },
  "status": "waiting",
  "currentPlayers": 0,
  "owner": {
    "id": "user-uuid",
    "nickname": "player1",
    "avatarUrl": null
  },
  "createdAt": "2026-01-12T10:00:00Z",
  "updatedAt": "2026-01-12T10:00:00Z"
}
```

---

### GET /rooms/{roomId}

방 상세 조회

**Response (200):** 위와 동일

**Errors:**
- `404` ROOM_NOT_FOUND

---

### POST /rooms/{roomId}/join

방 입장

**Headers:** Authorization 필수

**Request Body:**
```json
{
  "password": "secret",
  "buyIn": 1000
}
```

**Response (200):**
```json
{
  "success": true,
  "roomId": "room-uuid",
  "tableId": "table-uuid",
  "position": 3,
  "message": "Successfully joined room"
}
```

**Errors:**
- `404` ROOM_NOT_FOUND
- `409` ROOM_FULL
- `401` INVALID_PASSWORD

---

## 사용자 API

### GET /users/me

내 프로필 조회

**Headers:** Authorization 필수

**Response (200):**
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "nickname": "player1",
  "avatarUrl": null,
  "status": "active",
  "balance": 5000,
  "totalHands": 150,
  "totalWinnings": 2500,
  "createdAt": "2026-01-01T00:00:00Z"
}
```

---

### PATCH /users/me

프로필 수정

**Headers:** Authorization 필수

**Request Body:**
```json
{
  "nickname": "newname",
  "avatarUrl": "https://..."
}
```

**Response (200):** 위와 동일

---

## WebSocket 이벤트

### 연결

```
ws://localhost:8000/ws?token=<access_token>
```

### 메시지 형식

```json
{
  "type": "EVENT_TYPE",
  "ts": 1704067200000,
  "traceId": "uuid",
  "requestId": "client-uuid",
  "payload": {},
  "version": "v1"
}
```

---

## 클라이언트 → 서버 이벤트

### PING

Heartbeat (15초마다 전송)

```json
{
  "type": "PING",
  "payload": {}
}
```

---

### SUBSCRIBE_LOBBY

로비 구독

```json
{
  "type": "SUBSCRIBE_LOBBY",
  "payload": {}
}
```

---

### UNSUBSCRIBE_LOBBY

로비 구독 해제

```json
{
  "type": "UNSUBSCRIBE_LOBBY",
  "payload": {}
}
```

---

### SUBSCRIBE_TABLE

테이블 구독

```json
{
  "type": "SUBSCRIBE_TABLE",
  "payload": {
    "tableId": "table-uuid",
    "mode": "player"
  }
}
```

| mode | 설명 |
|------|------|
| player | 플레이어로 참여 |
| spectator | 관전자로 참여 |

---

### UNSUBSCRIBE_TABLE

테이블 구독 해제

```json
{
  "type": "UNSUBSCRIBE_TABLE",
  "payload": {
    "tableId": "table-uuid"
  }
}
```

---

### ACTION_REQUEST

게임 액션

```json
{
  "type": "ACTION_REQUEST",
  "payload": {
    "tableId": "table-uuid",
    "actionType": "raise",
    "amount": 100
  }
}
```

| actionType | amount 필요 | 설명 |
|------------|------------|------|
| fold | ❌ | 폴드 |
| check | ❌ | 체크 |
| call | ❌ | 콜 |
| bet | ✅ | 베팅 |
| raise | ✅ | 레이즈 |
| all_in | ❌ | 올인 |

---

### CHAT_MESSAGE

채팅 메시지

```json
{
  "type": "CHAT_MESSAGE",
  "payload": {
    "tableId": "table-uuid",
    "message": "Hello!"
  }
}
```

---

## 서버 → 클라이언트 이벤트

### PONG

Heartbeat 응답

```json
{
  "type": "PONG",
  "payload": {}
}
```

---

### CONNECTION_STATE

연결 상태 변경

```json
{
  "type": "CONNECTION_STATE",
  "payload": {
    "state": "connected",
    "userId": "user-uuid",
    "sessionId": "session-uuid"
  }
}
```

| state | 설명 |
|-------|------|
| connected | 연결 완료 |
| reconnecting | 재연결 중 |
| recovered | 재연결 후 복구 완료 |
| disconnected | 연결 종료 |

---

### LOBBY_SNAPSHOT

로비 전체 상태

```json
{
  "type": "LOBBY_SNAPSHOT",
  "payload": {
    "rooms": [
      {
        "roomId": "room-uuid",
        "name": "초보자 테이블",
        "blinds": "10/20",
        "maxSeats": 6,
        "playerCount": 4,
        "status": "playing"
      }
    ],
    "stateVersion": 1
  }
}
```

---

### TABLE_SNAPSHOT

테이블 전체 상태

```json
{
  "type": "TABLE_SNAPSHOT",
  "payload": {
    "tableId": "table-uuid",
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
          "userId": "user-uuid",
          "nickname": "Player1",
          "avatarUrl": null
        },
        "stack": 1500,
        "status": "active",
        "betAmount": 20
      }
    ],
    "hand": {
      "handId": "hand-uuid",
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
    "updatedAt": "2026-01-12T10:30:00Z"
  }
}
```

---

### TABLE_STATE_UPDATE

테이블 상태 변경 (델타)

```json
{
  "type": "TABLE_STATE_UPDATE",
  "payload": {
    "tableId": "table-uuid",
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
}
```

---

### TURN_PROMPT

턴 알림

```json
{
  "type": "TURN_PROMPT",
  "payload": {
    "tableId": "table-uuid",
    "position": 2,
    "allowedActions": [
      { "type": "fold" },
      { "type": "check" },
      { "type": "bet", "minAmount": 20, "maxAmount": 1400 },
      { "type": "all_in", "amount": 1400 }
    ],
    "turnDeadlineAt": "2026-01-12T10:30:30Z",
    "stateVersion": 16
  }
}
```

---

### ACTION_RESULT

액션 결과

**성공:**
```json
{
  "type": "ACTION_RESULT",
  "payload": {
    "success": true,
    "tableId": "table-uuid",
    "action": {
      "type": "raise",
      "amount": 100,
      "position": 2
    },
    "newStateVersion": 17
  }
}
```

**실패:**
```json
{
  "type": "ACTION_RESULT",
  "payload": {
    "success": false,
    "tableId": "table-uuid",
    "errorCode": "ACTION_INVALID_AMOUNT",
    "errorMessage": "Raise amount below minimum"
  }
}
```

---

### SHOWDOWN_RESULT

쇼다운 결과

```json
{
  "type": "SHOWDOWN_RESULT",
  "payload": {
    "tableId": "table-uuid",
    "handId": "hand-uuid",
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
}
```

---

### ERROR

에러

```json
{
  "type": "ERROR",
  "payload": {
    "errorCode": "ACTION_NOT_YOUR_TURN",
    "errorMessage": "It's not your turn",
    "details": {}
  }
}
```

---

## 에러 코드 목록

### 인증 에러

| 코드 | HTTP | 설명 |
|------|------|------|
| AUTH_REQUIRED | 401 | 인증 필요 |
| AUTH_INVALID_TOKEN | 401 | 유효하지 않은 토큰 |
| AUTH_TOKEN_EXPIRED | 401 | 토큰 만료 |
| AUTH_SESSION_EXPIRED | 401 | 세션 만료 |

### 방 에러

| 코드 | HTTP | 설명 |
|------|------|------|
| ROOM_NOT_FOUND | 404 | 방 없음 |
| ROOM_FULL | 409 | 방 가득 참 |
| ROOM_CLOSED | 410 | 방 닫힘 |

### 액션 에러

| 코드 | HTTP | 설명 |
|------|------|------|
| ACTION_NOT_YOUR_TURN | 403 | 본인 턴 아님 |
| ACTION_INVALID | 400 | 유효하지 않은 액션 |
| ACTION_INVALID_AMOUNT | 400 | 유효하지 않은 금액 |
| ACTION_INSUFFICIENT_STACK | 400 | 스택 부족 |
| ACTION_TIMEOUT | 408 | 타임아웃 |

### 상태 에러

| 코드 | HTTP | 설명 |
|------|------|------|
| STATE_STALE_VERSION | 409 | 클라이언트 상태 오래됨 |

### 레이트 리밋

| 코드 | HTTP | 설명 |
|------|------|------|
| RATE_LIMIT_EXCEEDED | 429 | 요청 한도 초과 |
