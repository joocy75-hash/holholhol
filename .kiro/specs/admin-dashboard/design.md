# Design Document: Admin Dashboard

## Overview

관리자 대시보드는 메인 홀덤 게임 애플리케이션과 **완전히 분리된 독립 애플리케이션**으로 설계됩니다. 별도의 프론트엔드(Next.js), 백엔드(FastAPI), 배포 파이프라인을 가지며, 메인 시스템과는 API 및 데이터베이스 연결을 통해서만 통신합니다.

### Project Goals
1. 실시간 서비스 모니터링 및 운영 관리
2. 사용자/게임 관리 및 CS 지원
3. 부정 행위 탐지 및 제재 관리
4. 메인 서비스와 완전 분리된 독립 운영

### Scope
- 실시간 대시보드 (CCU, DAU, 매출)
- 사용자 관리 (검색, 조회, 제재)
- 게임 관리 (방 관리, 핸드 리플레이)
- 시스템 관리 (점검, 공지)
- 감사 로그 및 보안

## Architecture

### System Separation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ADMIN SYSTEM (Standalone)                     │
│  ┌─────────────────┐    ┌─────────────────┐                     │
│  │  Admin Frontend │───▶│  Admin Backend  │                     │
│  │  (Next.js)      │    │  (FastAPI)      │                     │
│  │  admin.holdem.com    │  :8001          │                     │
│  └─────────────────┘    └────────┬────────┘                     │
└──────────────────────────────────┼──────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐
│ PostgreSQL  │  │   Redis     │  │      MAIN GAME SYSTEM       │
│ (Read       │  │ (Metrics    │  │  ┌─────────┐  ┌─────────┐   │
│  Replica)   │  │  Cache)     │  │  │ Game API│  │   WS    │   │
└─────────────┘  └─────────────┘  │  │  :8000  │  │ Gateway │   │
                                  │  └─────────┘  └─────────┘   │
                                  └─────────────────────────────┘
```

### Key Separation Principles

1. **독립 배포**: Admin 시스템은 메인 게임 서버와 별도로 배포/스케일링
2. **읽기 전용 DB 접근**: PostgreSQL Read Replica 사용으로 메인 DB 부하 분리
3. **제한된 쓰기**: 쓰기 작업은 메인 백엔드의 Admin API 엔드포인트를 통해서만 수행
4. **별도 인증**: 관리자 전용 인증 시스템 (2FA 필수)
5. **네트워크 분리**: 내부 네트워크에서만 접근 가능 (VPN 필수)

## Components and Interfaces

### Admin Frontend (Next.js 14)

```
admin-frontend/
├── src/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── 2fa/page.tsx
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # 메인 대시보드
│   │   │   ├── users/
│   │   │   │   ├── page.tsx          # 사용자 목록
│   │   │   │   └── [id]/page.tsx     # 사용자 상세
│   │   │   ├── rooms/
│   │   │   │   ├── page.tsx          # 방 목록
│   │   │   │   └── [id]/page.tsx     # 방 상세
│   │   │   ├── hands/
│   │   │   │   ├── page.tsx          # 핸드 검색
│   │   │   │   └── [id]/page.tsx     # 핸드 리플레이
│   │   │   ├── bans/page.tsx         # 제재 관리
│   │   │   ├── suspicious/page.tsx   # 의심 사용자
│   │   │   ├── announcements/page.tsx
│   │   │   ├── maintenance/page.tsx
│   │   │   └── settings/page.tsx
│   │   └── api/                      # BFF API routes
│   ├── components/
│   │   ├── dashboard/
│   │   │   ├── CCUChart.tsx
│   │   │   ├── DAUChart.tsx
│   │   │   ├── RevenueCard.tsx
│   │   │   └── ServerHealth.tsx
│   │   ├── users/
│   │   │   ├── UserTable.tsx
│   │   │   ├── UserDetail.tsx
│   │   │   └── BanDialog.tsx
│   │   ├── rooms/
│   │   │   ├── RoomTable.tsx
│   │   │   └── RoomDetail.tsx
│   │   ├── hands/
│   │   │   ├── HandSearch.tsx
│   │   │   └── HandReplay.tsx
│   │   └── common/
│   │       ├── DataTable.tsx
│   │       ├── SearchInput.tsx
│   │       └── ConfirmDialog.tsx
│   ├── lib/
│   │   ├── api.ts                    # Admin API client
│   │   ├── auth.ts                   # Auth utilities
│   │   └── permissions.ts            # RBAC helpers
│   └── stores/
│       ├── authStore.ts
│       └── dashboardStore.ts
```

### Admin Backend (FastAPI)

```
admin-backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── auth.py                   # 관리자 인증
│   │   ├── dashboard.py              # 대시보드 메트릭
│   │   ├── users.py                  # 사용자 관리
│   │   ├── rooms.py                  # 방 관리
│   │   ├── hands.py                  # 핸드 조회
│   │   ├── bans.py                   # 제재 관리
│   │   ├── announcements.py          # 공지 관리
│   │   └── audit.py                  # 감사 로그
│   ├── services/
│   │   ├── metrics_service.py        # CCU/DAU 집계
│   │   ├── user_service.py
│   │   ├── room_service.py
│   │   ├── hand_service.py
│   │   ├── ban_service.py
│   │   └── audit_service.py
│   ├── models/
│   │   ├── admin_user.py             # 관리자 계정
│   │   ├── audit_log.py              # 감사 로그
│   │   └── announcement.py           # 공지사항
│   ├── schemas/
│   │   ├── requests.py
│   │   └── responses.py
│   └── utils/
│       ├── main_api_client.py        # 메인 백엔드 API 클라이언트
│       ├── permissions.py            # RBAC
│       └── two_factor.py             # 2FA
```

### API Interfaces

#### Admin Backend → Main Backend (Write Operations)

```python
# Admin Backend calls Main Backend for write operations
class MainAPIClient:
    """메인 백엔드 Admin API 호출 클라이언트"""
    
    async def ban_user(self, user_id: str, ban_type: str, reason: str) -> BanResult:
        """POST /admin/users/{user_id}/ban"""
        
    async def unban_user(self, user_id: str) -> bool:
        """DELETE /admin/users/{user_id}/ban"""
        
    async def adjust_balance(self, user_id: str, amount: int, reason: str) -> Transaction:
        """POST /admin/users/{user_id}/balance"""
        
    async def force_close_room(self, room_id: str, reason: str) -> CloseResult:
        """POST /admin/rooms/{room_id}/force-close"""
        
    async def broadcast_announcement(self, message: str, target: str) -> bool:
        """POST /admin/announcements/broadcast"""
        
    async def set_maintenance_mode(self, enabled: bool, message: str) -> bool:
        """POST /admin/maintenance"""
```

#### Admin Backend REST API

```yaml
# Dashboard
GET  /api/dashboard/metrics          # CCU, DAU, 서버 상태
GET  /api/dashboard/revenue          # 매출 통계
GET  /api/dashboard/rooms-summary    # 방 현황 요약

# Users
GET  /api/users                      # 사용자 목록 (검색, 필터)
GET  /api/users/{id}                 # 사용자 상세
GET  /api/users/{id}/transactions    # 거래 내역
GET  /api/users/{id}/login-history   # 로그인 기록
GET  /api/users/{id}/hands           # 플레이한 핸드 목록

# Rooms
GET  /api/rooms                      # 활성 방 목록
GET  /api/rooms/{id}                 # 방 상세 (현재 상태 포함)
POST /api/rooms/{id}/message         # 시스템 메시지 전송
POST /api/rooms/{id}/force-close     # 강제 종료

# Hands
GET  /api/hands                      # 핸드 검색
GET  /api/hands/{id}                 # 핸드 상세 (리플레이 데이터)
GET  /api/hands/{id}/export          # 핸드 내보내기

# Bans
GET  /api/bans                       # 제재 목록
POST /api/bans                       # 제재 생성
DELETE /api/bans/{id}                # 제재 해제

# Suspicious
GET  /api/suspicious                 # 의심 사용자 큐
GET  /api/suspicious/{id}            # 케이스 상세
POST /api/suspicious/{id}/resolve    # 케이스 해결

# Announcements
GET  /api/announcements              # 공지 목록
POST /api/announcements              # 공지 생성
POST /api/announcements/broadcast    # 즉시 브로드캐스트

# Maintenance
GET  /api/maintenance/status         # 점검 상태
POST /api/maintenance/schedule       # 점검 예약
POST /api/maintenance/activate       # 점검 모드 활성화

# Audit
GET  /api/audit                      # 감사 로그 조회

# Auth
POST /api/auth/login                 # 로그인
POST /api/auth/2fa/verify            # 2FA 검증
POST /api/auth/logout                # 로그아웃
GET  /api/auth/me                    # 현재 사용자 정보
```

## Data Models

### Admin-Specific Tables (Admin DB)

```python
# 관리자 계정 (Admin DB에 저장)
class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id: UUID
    username: str
    email: str
    password_hash: str
    role: AdminRole  # viewer, operator, supervisor, admin
    two_factor_secret: str
    is_active: bool
    last_login: datetime
    created_at: datetime

class AdminRole(Enum):
    VIEWER = "viewer"           # 조회만 가능
    OPERATOR = "operator"       # 기본 운영 작업
    SUPERVISOR = "supervisor"   # 고액 조정 승인
    ADMIN = "admin"             # 전체 권한

# 감사 로그 (Admin DB에 저장)
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: UUID
    admin_user_id: UUID
    action: str                 # ban_user, adjust_balance, etc.
    target_type: str            # user, room, announcement
    target_id: str
    details: dict               # JSON 상세 정보
    ip_address: str
    created_at: datetime

# 공지사항 (Admin DB에 저장)
class Announcement(Base):
    __tablename__ = "announcements"
    
    id: UUID
    title: str
    content: str
    target: str                 # all, vip, specific_room
    scheduled_at: datetime | None
    broadcasted_at: datetime | None
    created_by: UUID
    created_at: datetime

# 의심 사용자 케이스 (Admin DB에 저장)
class SuspiciousCase(Base):
    __tablename__ = "suspicious_cases"
    
    id: UUID
    user_id: UUID               # 메인 DB의 user_id 참조
    flag_type: str              # same_ip, chip_dumping, bot_pattern
    flag_details: dict
    status: CaseStatus          # pending, cleared, escalated
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
```

### Read Access to Main DB (Read Replica)

```python
# 메인 DB에서 읽기 전용으로 접근하는 테이블들
# - users: 사용자 정보
# - transactions: 거래 내역
# - rooms: 방 정보
# - hands: 핸드 기록
# - hand_actions: 핸드 액션 상세
# - login_logs: 로그인 기록
# - bans: 제재 정보
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Dashboard Metrics Accuracy
*For any* time period, the CCU, DAU, and room counts displayed on the dashboard SHALL match the actual counts derived from the underlying data sources.
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Statistics Calculation Accuracy
*For any* date range filter, the revenue totals, hand counts, and averages SHALL be mathematically correct based on the transaction and hand records.
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

### Property 3: Audit Logging Completeness
*For any* admin action (ban, unban, balance adjustment, room close, announcement, maintenance), an audit log entry SHALL be created with the operator ID, timestamp, and action details.
**Validates: Requirements 3.5, 4.4, 6.5, 7.4, 10.4**

### Property 4: Search and Filter Accuracy
*For any* search query or filter criteria, the returned results SHALL include all and only the records that match the criteria.
**Validates: Requirements 5.1, 5.5, 8.1**

### Property 5: Ban Enforcement Correctness
*For any* banned user, login attempts SHALL be rejected, and *for any* unbanned user, login attempts SHALL be allowed (assuming valid credentials).
**Validates: Requirements 6.2, 6.4**

### Property 6: Chat Ban Partial Restriction
*For any* chat-banned user, chat messages SHALL be blocked while game actions (bet, fold, etc.) SHALL be allowed.
**Validates: Requirements 6.6**

### Property 7: Balance Adjustment Transaction Integrity
*For any* balance adjustment, a corresponding transaction record SHALL be created, and the user's balance SHALL reflect the adjustment amount.
**Validates: Requirements 7.2, 7.3**

### Property 8: Hand Replay Data Completeness
*For any* hand ID, the replay data SHALL include all actions, all cards (hole cards and community), and all pot amounts matching the original hand record.
**Validates: Requirements 8.2, 8.3, 8.4**

### Property 9: Role-Based Access Control
*For any* operator with a given role, access to endpoints and actions SHALL be restricted according to the role's permissions.
**Validates: Requirements 10.2, 10.3**

### Property 10: Session Timeout Enforcement
*For any* operator session inactive for 30+ minutes, subsequent requests SHALL be rejected and require re-authentication.
**Validates: Requirements 10.5**

### Property 11: System Separation Independence
*For any* deployment of the Admin Dashboard, it SHALL function independently of the main game application's deployment state (except for data access).
**Validates: Requirements 11.1, 11.5, 11.7**

## Error Handling

### API Error Responses

```python
class AdminErrorCode(Enum):
    # Auth errors (1xxx)
    INVALID_CREDENTIALS = 1001
    TWO_FACTOR_REQUIRED = 1002
    TWO_FACTOR_INVALID = 1003
    SESSION_EXPIRED = 1004
    INSUFFICIENT_PERMISSIONS = 1005
    
    # User errors (2xxx)
    USER_NOT_FOUND = 2001
    USER_ALREADY_BANNED = 2002
    USER_NOT_BANNED = 2003
    
    # Room errors (3xxx)
    ROOM_NOT_FOUND = 3001
    ROOM_ALREADY_CLOSED = 3002
    
    # Balance errors (4xxx)
    ADJUSTMENT_REQUIRES_APPROVAL = 4001
    ADJUSTMENT_REJECTED = 4002
    
    # System errors (5xxx)
    MAIN_API_UNAVAILABLE = 5001
    DATABASE_ERROR = 5002
    MAINTENANCE_MODE_ACTIVE = 5003
```

### Graceful Degradation

1. **메인 API 불가**: 읽기 전용 모드로 전환, 쓰기 작업 비활성화
2. **Read Replica 지연**: 캐시된 데이터 표시, 지연 경고 표시
3. **Redis 불가**: 실시간 메트릭 대신 DB 직접 조회 (성능 저하 허용)

## Testing Strategy

### Unit Tests
- 각 서비스 함수의 비즈니스 로직 테스트
- RBAC 권한 검증 로직 테스트
- 메트릭 계산 로직 테스트

### Property-Based Tests (Hypothesis)
- Property 1-11에 대한 속성 기반 테스트
- 최소 100회 반복 실행

### Integration Tests
- Admin Backend ↔ Main Backend API 통신 테스트
- Admin Backend ↔ Read Replica 연결 테스트
- 2FA 인증 플로우 테스트

### E2E Tests (Playwright)
- 로그인 → 2FA → 대시보드 접근 플로우
- 사용자 검색 → 상세 조회 → 제재 적용 플로우
- 핸드 검색 → 리플레이 플로우

## Technology Stack

### Admin Frontend
- **Framework**: Next.js 14 (App Router)
- **UI Library**: shadcn/ui + Tailwind CSS
- **State**: Zustand
- **Charts**: Recharts
- **Tables**: TanStack Table
- **Forms**: React Hook Form + Zod

### Admin Backend
- **Framework**: FastAPI
- **ORM**: SQLAlchemy 2.0 (async)
- **Auth**: python-jose (JWT) + pyotp (2FA)
- **Validation**: Pydantic v2
- **HTTP Client**: httpx (async)

### Database
- **Admin DB**: PostgreSQL (관리자 계정, 감사 로그, 공지)
- **Main DB Access**: PostgreSQL Read Replica
- **Cache**: Redis (메트릭 캐싱)

### Infrastructure
- **Deployment**: Docker + Kubernetes
- **Domain**: admin.holdem.com (별도 서브도메인)
- **Network**: VPN 필수, 내부 네트워크만 접근
- **Monitoring**: Prometheus + Grafana

## Cryptocurrency (USDT TRC-20) Integration

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    CRYPTO TRANSACTION FLOW                       │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────┐   │
│  │  Admin   │───▶│ Admin Backend │───▶│  Crypto Service     │   │
│  │ Frontend │    │              │    │  (Isolated Module)  │   │
│  └──────────┘    └──────────────┘    └──────────┬──────────┘   │
│                                                  │              │
└──────────────────────────────────────────────────┼──────────────┘
                                                   │
                    ┌──────────────────────────────┼───────────────┐
                    │                              │               │
                    ▼                              ▼               ▼
           ┌───────────────┐            ┌─────────────────┐  ┌──────────┐
           │ TRON Network  │            │ Exchange Rate   │  │   HSM    │
           │ (TRC-20 USDT) │            │ API (Upbit/     │  │ (Key     │
           │               │            │ Binance)        │  │ Storage) │
           └───────────────┘            └─────────────────┘  └──────────┘
```

### Crypto Service Components

```python
# admin-backend/app/services/crypto/

crypto/
├── __init__.py
├── tron_client.py          # TRON 네트워크 연동
├── wallet_manager.py       # 지갑 관리 (HSM 연동)
├── deposit_monitor.py      # 입금 모니터링
├── withdrawal_processor.py # 출금 처리
├── exchange_rate.py        # 환율 조회
└── models.py               # 암호화폐 관련 모델
```

### TRON Network Integration

```python
from tronpy import Tron
from tronpy.keys import PrivateKey

class TronClient:
    """TRON 네트워크 TRC-20 USDT 연동 클라이언트"""
    
    USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # USDT TRC-20
    
    def __init__(self, network: str = "mainnet"):
        self.client = Tron(network=network)
        self.usdt = self.client.get_contract(self.USDT_CONTRACT)
    
    async def get_balance(self, address: str) -> Decimal:
        """지갑 USDT 잔액 조회"""
        balance = self.usdt.functions.balanceOf(address)
        return Decimal(balance) / Decimal(10**6)  # USDT는 6 decimals
    
    async def get_transaction(self, tx_hash: str) -> TronTransaction:
        """트랜잭션 상세 조회"""
        tx = self.client.get_transaction(tx_hash)
        return TronTransaction.from_raw(tx)
    
    async def get_confirmations(self, tx_hash: str) -> int:
        """트랜잭션 확인 수 조회"""
        tx = self.client.get_transaction_info(tx_hash)
        current_block = self.client.get_latest_block_number()
        return current_block - tx.get("blockNumber", current_block)
    
    async def transfer_usdt(
        self, 
        to_address: str, 
        amount: Decimal,
        private_key: str  # HSM에서 가져옴
    ) -> str:
        """USDT 전송 (출금 처리)"""
        amount_raw = int(amount * Decimal(10**6))
        txn = (
            self.usdt.functions.transfer(to_address, amount_raw)
            .with_owner(self.hot_wallet_address)
            .fee_limit(10_000_000)  # 10 TRX fee limit
            .build()
            .sign(PrivateKey(bytes.fromhex(private_key)))
        )
        result = txn.broadcast()
        return result["txid"]
```

### Exchange Rate Service

```python
import httpx
from decimal import Decimal
from datetime import datetime, timedelta

class ExchangeRateService:
    """USDT/KRW 환율 조회 서비스"""
    
    UPBIT_API = "https://api.upbit.com/v1/ticker"
    BINANCE_API = "https://api.binance.com/api/v3/ticker/price"
    CACHE_TTL = timedelta(seconds=30)
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self._cached_rate: Decimal | None = None
        self._cached_at: datetime | None = None
    
    async def get_usdt_krw_rate(self) -> ExchangeRate:
        """현재 USDT/KRW 환율 조회"""
        # 캐시 확인
        cached = await self.redis.get("exchange_rate:usdt_krw")
        if cached:
            return ExchangeRate.parse_raw(cached)
        
        # Upbit API 우선 시도
        try:
            rate = await self._fetch_upbit_rate()
        except Exception:
            # Fallback to Binance USDT/BUSD + USD/KRW
            rate = await self._fetch_binance_rate()
        
        # 캐시 저장
        exchange_rate = ExchangeRate(
            rate=rate,
            source="upbit",
            timestamp=datetime.utcnow()
        )
        await self.redis.setex(
            "exchange_rate:usdt_krw",
            self.CACHE_TTL.seconds,
            exchange_rate.json()
        )
        return exchange_rate
    
    async def _fetch_upbit_rate(self) -> Decimal:
        """Upbit에서 USDT/KRW 환율 조회"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.UPBIT_API,
                params={"markets": "KRW-USDT"}
            )
            data = resp.json()[0]
            return Decimal(str(data["trade_price"]))
    
    def convert_to_krw(self, usdt_amount: Decimal, rate: Decimal) -> Decimal:
        """USDT를 KRW로 변환"""
        return (usdt_amount * rate).quantize(Decimal("1"))
    
    def convert_to_usdt(self, krw_amount: Decimal, rate: Decimal) -> Decimal:
        """KRW를 USDT로 변환"""
        return (krw_amount / rate).quantize(Decimal("0.000001"))
```

### Crypto Data Models

```python
from enum import Enum
from decimal import Decimal
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, Enum as SQLEnum

class TransactionStatus(Enum):
    PENDING = "pending"           # 대기 중
    CONFIRMING = "confirming"     # 확인 중 (1-19 confirmations)
    CONFIRMED = "confirmed"       # 확인 완료 (20+ confirmations)
    PROCESSING = "processing"     # 처리 중 (출금)
    COMPLETED = "completed"       # 완료
    FAILED = "failed"             # 실패
    REJECTED = "rejected"         # 거부됨

class CryptoDeposit(Base):
    """USDT 입금 기록"""
    __tablename__ = "crypto_deposits"
    
    id: UUID
    user_id: UUID
    tx_hash: str                  # TRON 트랜잭션 해시
    from_address: str             # 송금자 지갑 주소
    to_address: str               # 시스템 입금 주소
    amount_usdt: Decimal          # USDT 금액
    amount_krw: Decimal           # 입금 시점 KRW 환산액
    exchange_rate: Decimal        # 적용 환율
    confirmations: int            # 확인 수
    status: TransactionStatus
    detected_at: datetime         # 트랜잭션 감지 시각
    confirmed_at: datetime | None # 확인 완료 시각
    credited_at: datetime | None  # 잔액 반영 시각

class CryptoWithdrawal(Base):
    """USDT 출금 기록"""
    __tablename__ = "crypto_withdrawals"
    
    id: UUID
    user_id: UUID
    to_address: str               # 출금 대상 지갑 주소
    amount_usdt: Decimal          # 출금 USDT 금액
    amount_krw: Decimal           # 요청 시점 KRW 환산액
    exchange_rate: Decimal        # 적용 환율
    network_fee_usdt: Decimal     # 네트워크 수수료
    network_fee_krw: Decimal      # 수수료 KRW 환산
    tx_hash: str | None           # 전송 후 트랜잭션 해시
    status: TransactionStatus
    requested_at: datetime
    approved_by: UUID | None      # 승인 관리자
    approved_at: datetime | None
    processed_at: datetime | None # 전송 완료 시각
    rejection_reason: str | None

class HotWalletBalance(Base):
    """핫월렛 잔액 스냅샷"""
    __tablename__ = "hot_wallet_balances"
    
    id: UUID
    address: str
    balance_usdt: Decimal
    balance_krw: Decimal
    exchange_rate: Decimal
    recorded_at: datetime
```

### Crypto API Endpoints

```yaml
# Deposits
GET  /api/crypto/deposits                    # 입금 목록
GET  /api/crypto/deposits/{id}               # 입금 상세
POST /api/crypto/deposits/{id}/approve       # 수동 승인 (필요시)
POST /api/crypto/deposits/{id}/reject        # 거부

# Withdrawals
GET  /api/crypto/withdrawals                 # 출금 목록
GET  /api/crypto/withdrawals/{id}            # 출금 상세
POST /api/crypto/withdrawals/{id}/approve    # 출금 승인
POST /api/crypto/withdrawals/{id}/reject     # 출금 거부

# Wallet
GET  /api/crypto/wallet/balance              # 핫월렛 잔액
GET  /api/crypto/wallet/transactions         # 지갑 트랜잭션 내역

# Exchange Rate
GET  /api/crypto/exchange-rate               # 현재 환율
GET  /api/crypto/exchange-rate/history       # 환율 히스토리

# Statistics
GET  /api/crypto/stats/summary               # 입출금 통계 요약
GET  /api/crypto/stats/daily                 # 일별 통계
```

### Security Considerations

#### Private Key Management
```
┌─────────────────────────────────────────────────────────────┐
│                    KEY MANAGEMENT                            │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐ │
│  │ Admin       │───▶│ Crypto      │───▶│ HSM / AWS KMS   │ │
│  │ Backend     │    │ Service     │    │ (Private Keys)  │ │
│  └─────────────┘    └─────────────┘    └─────────────────┘ │
│                                                              │
│  - Private keys NEVER stored in application code            │
│  - All signing operations performed in HSM                  │
│  - Multi-signature for large withdrawals                    │
│  - Key rotation policy enforced                             │
└─────────────────────────────────────────────────────────────┘
```

#### Withdrawal Security Flow
```python
async def process_withdrawal(withdrawal_id: UUID, operator: AdminUser):
    """출금 처리 보안 플로우"""
    withdrawal = await get_withdrawal(withdrawal_id)
    
    # 1. 권한 확인
    if withdrawal.amount_usdt > SUPERVISOR_THRESHOLD:
        require_role(operator, AdminRole.SUPERVISOR)
    
    # 2. 2FA 재인증
    await require_reauthentication(operator)
    
    # 3. 주소 화이트리스트 확인 (선택적)
    if not await is_whitelisted_address(withdrawal.to_address):
        await flag_for_manual_review(withdrawal)
        return
    
    # 4. 핫월렛 잔액 확인
    balance = await tron_client.get_balance(HOT_WALLET_ADDRESS)
    if balance < withdrawal.amount_usdt + withdrawal.network_fee_usdt:
        raise InsufficientHotWalletBalance()
    
    # 5. HSM에서 서명 및 전송
    tx_hash = await crypto_service.execute_withdrawal(withdrawal)
    
    # 6. 감사 로그 기록
    await audit_log.record(
        action="withdrawal_processed",
        operator_id=operator.id,
        details={
            "withdrawal_id": withdrawal_id,
            "amount_usdt": withdrawal.amount_usdt,
            "to_address": withdrawal.to_address,
            "tx_hash": tx_hash
        }
    )
```

### Additional Correctness Properties

### Property 12: Deposit Detection Accuracy
*For any* USDT TRC-20 transaction to the system's deposit address, the deposit SHALL be detected and recorded with correct amount and transaction hash.
**Validates: Requirements 12.1, 12.4, 12.5**

### Property 13: KRW Conversion Accuracy
*For any* USDT amount and exchange rate, the KRW equivalent SHALL be calculated as `USDT * rate` rounded to the nearest won.
**Validates: Requirements 12.2, 13.2, 15.1**

### Property 14: Withdrawal Balance Integrity
*For any* approved withdrawal, the user's game balance SHALL be deducted by the withdrawal amount, and the hot wallet balance SHALL decrease by the same amount plus network fee.
**Validates: Requirements 13.3, 13.4, 13.8**

### Property 15: Withdrawal Approval Workflow
*For any* withdrawal exceeding the threshold, supervisor approval SHALL be required before processing.
**Validates: Requirements 13.6, 13.7**

### Property 16: Hot Wallet Alert Threshold
*For any* hot wallet balance below the configured threshold, an alert SHALL be displayed to operators.
**Validates: Requirements 14.3, 14.4**

### Property 17: Exchange Rate Fallback
*For any* exchange rate API failure, the system SHALL use the most recent cached rate and display a warning indicator.
**Validates: Requirements 15.5**

### Crypto-Specific Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Private key compromise | Critical | HSM/KMS storage, multi-sig for large amounts |
| Incorrect deposit detection | High | Multiple confirmation requirement (20+), manual review option |
| Exchange rate manipulation | Medium | Multiple API sources, rate change alerts |
| Network congestion | Medium | Dynamic fee estimation, retry mechanism |
| Regulatory compliance | High | KYC integration, transaction limits, AML monitoring |
| Hot wallet depletion | High | Balance alerts, automatic cold→hot transfers |
