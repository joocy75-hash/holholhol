# 에러 코드 명세 v1

> WebSocket 및 REST API 에러 코드 정의

---

## 1. 에러 응답 형식

### 1.1 WebSocket 에러

```json
{
  "type": "ERROR",
  "ts": 1704067200000,
  "traceId": "abc-123-def",
  "requestId": "client-req-001",
  "payload": {
    "errorCode": "INVALID_ACTION",
    "errorMessage": "Raise amount below minimum",
    "details": {
      "minRaise": 40,
      "requestedAmount": 20
    }
  },
  "version": "v1"
}
```

### 1.2 REST API 에러

```json
{
  "error": {
    "code": "AUTH_REQUIRED",
    "message": "Authentication required",
    "details": {}
  },
  "traceId": "abc-123-def"
}
```

---

## 2. 에러 코드 체계

### 2.1 코드 네이밍 규칙

```
{CATEGORY}_{SPECIFIC_ERROR}
```

| 카테고리 | 설명 |
|---------|------|
| `AUTH_` | 인증 관련 |
| `ROOM_` | 방 관련 |
| `TABLE_` | 테이블 관련 |
| `ACTION_` | 게임 액션 관련 |
| `STATE_` | 상태 관련 |
| `RATE_` | 레이트 리밋 관련 |
| `SYSTEM_` | 시스템 에러 |

---

## 3. 인증 에러 (AUTH_)

| 코드 | HTTP | 설명 | 클라이언트 처리 |
|------|------|------|----------------|
| `AUTH_REQUIRED` | 401 | 인증 필요 | 로그인 페이지로 이동 |
| `AUTH_INVALID_TOKEN` | 401 | 유효하지 않은 토큰 | 토큰 갱신 시도 |
| `AUTH_TOKEN_EXPIRED` | 401 | 토큰 만료 | 리프레시 토큰으로 갱신 |
| `AUTH_REFRESH_FAILED` | 401 | 리프레시 실패 | 재로그인 필요 |
| `AUTH_SESSION_EXPIRED` | 401 | 세션 만료 | 재로그인 필요 |

---

## 4. 방 에러 (ROOM_)

| 코드 | HTTP | 설명 | 클라이언트 처리 |
|------|------|------|----------------|
| `ROOM_NOT_FOUND` | 404 | 방을 찾을 수 없음 | 로비로 이동 |
| `ROOM_FULL` | 409 | 방이 가득 참 | 다른 방 선택 안내 |
| `ROOM_CLOSED` | 410 | 방이 닫힘 | 로비로 이동 |
| `ROOM_CREATE_FAILED` | 500 | 방 생성 실패 | 재시도 안내 |
| `ROOM_ALREADY_JOINED` | 409 | 이미 입장한 방 | 해당 방으로 이동 |

---

## 5. 테이블 에러 (TABLE_)

| 코드 | HTTP | 설명 | 클라이언트 처리 |
|------|------|------|----------------|
| `TABLE_NOT_FOUND` | 404 | 테이블을 찾을 수 없음 | 로비로 이동 |
| `TABLE_FULL` | 409 | 테이블이 가득 참 | 관전 모드 제안 |
| `TABLE_SEAT_TAKEN` | 409 | 좌석이 이미 점유됨 | 다른 좌석 선택 |
| `TABLE_NOT_SEATED` | 403 | 착석하지 않은 상태 | 착석 필요 안내 |
| `TABLE_ALREADY_SEATED` | 409 | 이미 착석한 상태 | 현재 좌석 정보 표시 |

---

## 6. 액션 에러 (ACTION_)

| 코드 | HTTP | 설명 | 클라이언트 처리 |
|------|------|------|----------------|
| `ACTION_NOT_YOUR_TURN` | 403 | 본인 턴이 아님 | 턴 대기 안내 |
| `ACTION_INVALID` | 400 | 유효하지 않은 액션 | 가능 액션 재확인 |
| `ACTION_INVALID_AMOUNT` | 400 | 유효하지 않은 금액 | 최소/최대 금액 안내 |
| `ACTION_INSUFFICIENT_STACK` | 400 | 스택 부족 | 올인 또는 콜 제안 |
| `ACTION_TIMEOUT` | 408 | 액션 타임아웃 | 자동 폴드 알림 |
| `ACTION_HAND_FINISHED` | 409 | 핸드가 이미 종료됨 | 다음 핸드 대기 |

### 6.1 액션 에러 상세

#### ACTION_INVALID_AMOUNT

```json
{
  "errorCode": "ACTION_INVALID_AMOUNT",
  "errorMessage": "Raise amount must be between 40 and 1500",
  "details": {
    "minAmount": 40,
    "maxAmount": 1500,
    "requestedAmount": 20
  }
}
```

#### ACTION_INSUFFICIENT_STACK

```json
{
  "errorCode": "ACTION_INSUFFICIENT_STACK",
  "errorMessage": "Insufficient stack for this action",
  "details": {
    "currentStack": 100,
    "requiredAmount": 200,
    "suggestedAction": "all_in"
  }
}
```

---

## 7. 상태 에러 (STATE_)

| 코드 | HTTP | 설명 | 클라이언트 처리 |
|------|------|------|----------------|
| `STATE_STALE_VERSION` | 409 | 클라이언트 상태가 오래됨 | 스냅샷 재요청 |
| `STATE_SYNC_FAILED` | 500 | 상태 동기화 실패 | 재연결 시도 |
| `STATE_INVALID` | 500 | 서버 상태 오류 | 에러 리포트 |

### 7.1 STATE_STALE_VERSION

```json
{
  "errorCode": "STATE_STALE_VERSION",
  "errorMessage": "Client state is outdated",
  "details": {
    "clientVersion": 10,
    "serverVersion": 15,
    "action": "request_snapshot"
  }
}
```

---

## 8. 레이트 리밋 에러 (RATE_)

| 코드 | HTTP | 설명 | 클라이언트 처리 |
|------|------|------|----------------|
| `RATE_LIMIT_EXCEEDED` | 429 | 요청 한도 초과 | 대기 후 재시도 |
| `RATE_ACTION_TOO_FAST` | 429 | 액션이 너무 빠름 | 잠시 대기 안내 |

### 8.1 RATE_LIMIT_EXCEEDED

```json
{
  "errorCode": "RATE_LIMIT_EXCEEDED",
  "errorMessage": "Too many requests",
  "details": {
    "retryAfterSeconds": 30,
    "limit": 100,
    "window": 60
  }
}
```

---

## 9. 시스템 에러 (SYSTEM_)

| 코드 | HTTP | 설명 | 클라이언트 처리 |
|------|------|------|----------------|
| `SYSTEM_INTERNAL_ERROR` | 500 | 내부 서버 오류 | 재시도 또는 지원 문의 |
| `SYSTEM_MAINTENANCE` | 503 | 점검 중 | 점검 종료 시간 안내 |
| `SYSTEM_UNAVAILABLE` | 503 | 서비스 불가 | 재시도 안내 |

---

## 10. HTTP 상태 코드 매핑

| HTTP | 의미 | 사용 케이스 |
|------|------|-----------|
| 400 | Bad Request | 잘못된 요청 형식, 유효하지 않은 파라미터 |
| 401 | Unauthorized | 인증 필요, 토큰 만료 |
| 403 | Forbidden | 권한 없음, 턴이 아님 |
| 404 | Not Found | 리소스 없음 |
| 408 | Request Timeout | 액션 타임아웃 |
| 409 | Conflict | 상태 충돌, 중복 요청 |
| 410 | Gone | 리소스 삭제됨 |
| 429 | Too Many Requests | 레이트 리밋 |
| 500 | Internal Server Error | 서버 오류 |
| 503 | Service Unavailable | 점검, 과부하 |

---

## 11. 클라이언트 에러 처리 가이드

### 11.1 재시도 가능 에러

```typescript
const RETRYABLE_ERRORS = [
  'SYSTEM_INTERNAL_ERROR',
  'SYSTEM_UNAVAILABLE',
  'STATE_SYNC_FAILED',
];
```

### 11.2 재인증 필요 에러

```typescript
const AUTH_ERRORS = [
  'AUTH_REQUIRED',
  'AUTH_INVALID_TOKEN',
  'AUTH_TOKEN_EXPIRED',
  'AUTH_SESSION_EXPIRED',
];
```

### 11.3 스냅샷 재요청 에러

```typescript
const SNAPSHOT_REQUIRED_ERRORS = [
  'STATE_STALE_VERSION',
];
```

---

## 관련 문서

- [20-realtime-protocol-v1.md](./20-realtime-protocol-v1.md) - 실시간 프로토콜
- [22-idempotency-ordering.md](./22-idempotency-ordering.md) - 멱등성/순서 규칙
