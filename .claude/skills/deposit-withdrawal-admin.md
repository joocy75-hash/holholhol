# 입금/출금 관리 기능 구현 Skills

## 개요
관리자 페이지의 입금/출금 관리 기능 구현을 위한 작업 가이드입니다.
여러 계정에서 작업 시 일관된 방식으로 작업을 진행할 수 있도록 합니다.

---

## 현재 구현 상황 (2026-01-19 기준)

### 입금 (Deposit) - 100% 완료 ✅
| 항목 | 상태 | 파일 |
|------|------|------|
| Admin API | ✅ 완료 | `admin-backend/app/api/admin_ton_deposit.py` |
| Admin Service | ✅ 완료 | `admin-backend/app/services/crypto/deposit_processor.py` |
| Admin Model | ✅ 완료 | `admin-backend/app/models/deposit_request.py` |
| Admin Frontend | ✅ 완료 | `admin-frontend/src/app/(dashboard)/deposits/page.tsx` |
| Frontend API | ✅ 완료 | `admin-frontend/src/lib/deposits-api.ts` |

### 출금 (Withdrawal) - 100% 완료 ✅
| 항목 | 상태 | 파일 |
|------|------|------|
| Admin API | ✅ 완료 | `admin-backend/app/api/crypto.py` |
| Admin Service | ✅ 완료 | `admin-backend/app/services/crypto/withdrawal_service.py` |
| Admin Model | ✅ 완료 | `admin-backend/app/models/crypto.py` |
| Admin Frontend | ✅ 완료 | `admin-frontend/src/app/(dashboard)/withdrawals/page.tsx` |
| Frontend API | ✅ 완료 | `admin-frontend/src/lib/withdrawals-api.ts` |
| Main Backend | ✅ 완료 | `backend/app/services/crypto_withdrawal.py` |

---

## 작업 진행 규칙

### 1. 단계별 작업 흐름
```
1. TODO 체크리스트 확인 → DEPOSIT_WITHDRAWAL_PROGRESS.md
2. 현재 단계 확인
3. 서브에이전트로 작업 진행
4. 테스트 실행 및 검증
5. 완료 체크 표시
6. 다음 단계 진행
```

### 2. 서브에이전트 사용 지침
| 작업 유형 | 서브에이전트 | 용도 |
|-----------|-------------|------|
| 코드 탐색 | `Explore` | 기존 코드 패턴 분석 |
| 코드 아키텍처 | `code-architect` | 구현 설계 |
| 코드 리뷰 | `code-reviewer` | 구현 후 검증 |
| 테스트 분석 | `pr-test-analyzer` | 테스트 커버리지 확인 |

### 3. 중단 대비 규칙
- **매 단계 완료 시**: `DEPOSIT_WITHDRAWAL_PROGRESS.md` 업데이트
- **작업 시작 시**: 이 파일 읽고 현재 진행 상황 확인
- **복잡한 작업 시**: 작은 단위로 분할하여 커밋

---

## 관련 파일 경로

### Admin Backend
```
admin-backend/
├── app/
│   ├── api/
│   │   ├── admin_ton_deposit.py    # 입금 관리 API (참고용)
│   │   ├── crypto.py               # 출금 API (TODO 구현)
│   │   └── admin_withdrawal.py     # 새로 생성
│   ├── models/
│   │   ├── deposit_request.py      # 입금 모델 (참고용)
│   │   └── crypto.py               # 출금 모델 (이미 있음)
│   └── services/
│       └── crypto/
│           ├── deposit_processor.py # 입금 서비스 (참고용)
│           └── withdrawal_service.py # 새로 생성
└── tests/
    └── api/
        └── test_withdrawal.py       # 새로 생성
```

### Admin Frontend
```
admin-frontend/src/
├── app/(dashboard)/
│   ├── deposits/page.tsx           # 입금 페이지 (참고용)
│   └── withdrawals/page.tsx        # 새로 생성
├── components/
│   └── withdrawals/                # 새로 생성
│       ├── WithdrawalList.tsx
│       ├── WithdrawalDetail.tsx
│       └── WithdrawalStats.tsx
└── lib/
    ├── deposits-api.ts             # 입금 API (참고용)
    └── withdrawals-api.ts          # 새로 생성
```

---

## 데이터 모델 참조

### CryptoWithdrawal (이미 구현됨)
```python
# admin-backend/app/models/crypto.py
class CryptoWithdrawal:
    id: str (UUID)
    user_id: str
    to_address: str           # 출금 주소
    amount_usdt: Decimal
    amount_krw: Decimal
    exchange_rate: Decimal
    network_fee_usdt: Decimal
    network_fee_krw: Decimal
    tx_hash: str | None       # 블록체인 TX
    status: TransactionStatus # PENDING → PROCESSING → COMPLETED/FAILED/REJECTED
    requested_at: datetime
    approved_by: str | None
    approved_at: datetime | None
    processed_at: datetime | None
    rejection_reason: str | None
```

### TransactionStatus
```python
class TransactionStatus(str, Enum):
    PENDING = "pending"       # 24시간 대기
    PROCESSING = "processing" # 처리 중
    COMPLETED = "completed"   # 완료
    FAILED = "failed"         # 실패
    CANCELLED = "cancelled"   # 취소
    REJECTED = "rejected"     # 거부
```

---

## API 설계 참조

### 출금 관리 API (구현 예정)
```
GET  /api/admin/withdrawals                    # 출금 목록
GET  /api/admin/withdrawals/stats              # 출금 통계
GET  /api/admin/withdrawals/{id}               # 출금 상세
POST /api/admin/withdrawals/{id}/approve       # 출금 승인
POST /api/admin/withdrawals/{id}/reject        # 출금 거부
GET  /api/admin/withdrawals/pending/count      # 대기중 건수
```

### 응답 스키마 (입금 참고)
```typescript
interface WithdrawalListItem {
  id: string;
  userId: string;
  userNickname: string;
  toAddress: string;
  amountUsdt: number;
  amountKrw: number;
  networkFee: number;
  status: string;
  requestedAt: string;
  approvedAt?: string;
  processedAt?: string;
}

interface WithdrawalStats {
  pendingCount: number;
  pendingAmountKrw: number;
  todayCompletedCount: number;
  todayCompletedAmountKrw: number;
  totalCompletedCount: number;
  totalCompletedAmountKrw: number;
}
```

---

## 테스트 명령어

### Admin Backend
```bash
cd admin-backend
pytest tests/api/test_withdrawal.py -v
pytest tests/services/test_withdrawal_service.py -v
```

### Admin Frontend
```bash
cd admin-frontend
npm run type-check
npm run lint
```

---

## 코딩 컨벤션

### Python (Backend)
- snake_case 변수명
- 비동기 함수는 `async def`
- 타입 힌트 필수
- 주석/에러메시지 한글 OK
- Pydantic v2 스키마 사용

### TypeScript (Frontend)
- camelCase 변수명
- interface 사용 (type보다)
- shadcn/ui 컴포넌트 활용
- Tailwind CSS 스타일링

---

## 작업 완료 기준

각 단계는 다음 조건 충족 시 완료:
1. ✅ 코드 구현 완료
2. ✅ 테스트 통과 (pytest/type-check)
3. ✅ 진행 상황 파일 업데이트
4. ✅ 코드 리뷰 (code-reviewer 에이전트)
