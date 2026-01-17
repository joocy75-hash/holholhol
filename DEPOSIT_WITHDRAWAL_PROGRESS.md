# 입금/출금 관리 기능 구현 작업 계획서

> **작성일**: 2026-01-18
> **목표**: 관리자 페이지의 출금 관리 기능 완성 (입금은 95% 완료)
> **예상 총 작업량**: 8단계
> **현재 진행률**: 0%

---

## 🚨 중단 대비 지침

### 작업 재개 시 체크리스트
1. 이 파일(`DEPOSIT_WITHDRAWAL_PROGRESS.md`)을 먼저 읽기
2. 아래 체크박스에서 마지막 완료된 단계 확인
3. `[🔄 진행중]` 표시된 단계부터 이어서 작업
4. Skills 파일 참조: `.claude/skills/deposit-withdrawal-admin.md`

### 작업 완료 시 필수 행동
- [ ] 해당 단계 체크박스 `[x]`로 변경
- [ ] 완료 날짜 기록
- [ ] 테스트 결과 기록
- [ ] 다음 단계를 `[🔄 진행중]`으로 변경

---

## 📊 전체 진행 상황

| 단계 | 작업 내용 | 상태 | 완료일 | 테스트 |
|------|----------|------|--------|--------|
| 1 | Admin Withdrawal Service 구현 | ✅ 완료 | 2026-01-18 | 임포트 테스트 통과 |
| 2 | Admin Withdrawal API 구현 | 🔄 진행중 | - | - |
| 3 | Admin Withdrawal API 테스트 | ⬜ 대기 | - | - |
| 4 | Frontend API 클라이언트 구현 | ⬜ 대기 | - | - |
| 5 | Frontend 출금 목록 페이지 | ⬜ 대기 | - | - |
| 6 | Frontend 출금 상세/승인/거부 모달 | ⬜ 대기 | - | - |
| 7 | Frontend 통합 테스트 | ⬜ 대기 | - | - |
| 8 | 입금/출금 통합 대시보드 | ⬜ 대기 | - | - |

---

## 📋 상세 작업 계획

---

### 🔷 Phase 1: Admin Withdrawal Service 구현

**상태**: ✅ 완료
**우선순위**: P0 (필수)
**완료일**: 2026-01-18
**서브에이전트**: `code-architect` → 코드 작성 → `code-reviewer`

#### 작업 파일
```
admin-backend/app/services/crypto/withdrawal_service.py (생성 완료)
```

#### 상세 태스크
- [x] **1.1** 기존 입금 서비스 패턴 분석 (`deposit_processor.py` 참고)
- [x] **1.2** WithdrawalService 클래스 생성
  - [x] `async list_withdrawals(status, user_id, page, limit)` - 목록 조회
  - [x] `async get_withdrawal_detail(withdrawal_id)` - 상세 조회
  - [x] `async get_withdrawal_stats()` - 통계 조회
  - [x] `async approve_withdrawal(withdrawal_id, admin_id, tx_hash)` - 승인
  - [x] `async reject_withdrawal(withdrawal_id, admin_id, reason)` - 거부
  - [x] `async get_pending_count()` - 대기 건수
- [x] **1.3** 메인 DB 연동 (출금 시 잔액 차감 확인)
- [x] **1.4** 감사 로그 기록 연동
- [x] **1.5** 임포트 테스트 (`python -c "from app.services.crypto.withdrawal_service import ..."`)

#### 완료 조건
- [x] 모든 메서드 구현 완료
- [x] 임포트 에러 없음
- [x] 코드 리뷰 완료 (UUID 비교 수정, 멱등성 키 추가)

#### 참고 코드
```python
# 입금 서비스 패턴 참고
# admin-backend/app/services/crypto/deposit_processor.py:273-327
async def manual_approve(self, deposit_id: str, admin_id: str, tx_hash: str) -> dict:
    ...
```

---

### 🔷 Phase 2: Admin Withdrawal API 구현

**상태**: ⬜ 대기
**우선순위**: P0 (필수)
**예상 시간**: 30분
**서브에이전트**: 코드 작성 → `code-reviewer`

#### 작업 파일
```
admin-backend/app/api/admin_withdrawal.py (새로 생성)
admin-backend/app/main.py (라우터 추가)
```

#### 상세 태스크
- [ ] **2.1** API 라우터 파일 생성 (`admin_withdrawal.py`)
- [ ] **2.2** Pydantic 스키마 정의
  - [ ] `WithdrawalListResponse`
  - [ ] `WithdrawalDetailResponse`
  - [ ] `WithdrawalStatsResponse`
  - [ ] `WithdrawalApproveRequest`
  - [ ] `WithdrawalRejectRequest`
- [ ] **2.3** API 엔드포인트 구현
  - [ ] `GET /api/admin/withdrawals` - 목록 조회
  - [ ] `GET /api/admin/withdrawals/stats` - 통계
  - [ ] `GET /api/admin/withdrawals/{id}` - 상세
  - [ ] `POST /api/admin/withdrawals/{id}/approve` - 승인
  - [ ] `POST /api/admin/withdrawals/{id}/reject` - 거부
  - [ ] `GET /api/admin/withdrawals/pending/count` - 대기 건수
- [ ] **2.4** main.py에 라우터 등록
- [ ] **2.5** 서버 시작 테스트 (`uvicorn app.main:app`)

#### 완료 조건
- [ ] 모든 엔드포인트 구현 완료
- [ ] 서버 시작 에러 없음
- [ ] API 문서 자동 생성 확인 (`/docs`)

---

### 🔷 Phase 3: Admin Withdrawal API 테스트

**상태**: ⬜ 대기
**우선순위**: P0 (필수)
**예상 시간**: 30분
**서브에이전트**: 코드 작성 → `pr-test-analyzer`

#### 작업 파일
```
admin-backend/tests/api/test_withdrawal.py (새로 생성)
admin-backend/tests/services/test_withdrawal_service.py (새로 생성)
```

#### 상세 태스크
- [ ] **3.1** API 테스트 작성
  - [ ] `test_list_withdrawals` - 목록 조회 테스트
  - [ ] `test_list_withdrawals_with_filters` - 필터 테스트
  - [ ] `test_get_withdrawal_detail` - 상세 조회 테스트
  - [ ] `test_get_withdrawal_stats` - 통계 테스트
  - [ ] `test_approve_withdrawal` - 승인 테스트
  - [ ] `test_reject_withdrawal` - 거부 테스트
  - [ ] `test_unauthorized_access` - 인증 없이 접근 테스트
- [ ] **3.2** 서비스 단위 테스트 작성
- [ ] **3.3** 테스트 실행 및 통과 확인

#### 테스트 명령어
```bash
cd admin-backend
pytest tests/api/test_withdrawal.py -v
pytest tests/services/test_withdrawal_service.py -v
```

#### 완료 조건
- [ ] 모든 테스트 통과
- [ ] 테스트 커버리지 80% 이상

---

### 🔷 Phase 4: Frontend API 클라이언트 구현

**상태**: ⬜ 대기
**우선순위**: P1 (중요)
**예상 시간**: 20분
**서브에이전트**: 코드 작성

#### 작업 파일
```
admin-frontend/src/lib/withdrawals-api.ts (새로 생성)
```

#### 상세 태스크
- [ ] **4.1** 기존 입금 API 클라이언트 패턴 분석 (`deposits-api.ts`)
- [ ] **4.2** TypeScript 인터페이스 정의
  - [ ] `WithdrawalListItem`
  - [ ] `WithdrawalDetail`
  - [ ] `WithdrawalStats`
  - [ ] `PaginatedWithdrawals`
- [ ] **4.3** API 함수 구현
  - [ ] `listWithdrawals(params)`
  - [ ] `getWithdrawal(id)`
  - [ ] `getStats()`
  - [ ] `getPendingCount()`
  - [ ] `approveWithdrawal(id, txHash, note)`
  - [ ] `rejectWithdrawal(id, reason)`
- [ ] **4.4** TypeScript 타입 체크

#### 테스트 명령어
```bash
cd admin-frontend
npm run type-check
```

#### 완료 조건
- [ ] 타입 에러 없음
- [ ] 빌드 성공

---

### 🔷 Phase 5: Frontend 출금 목록 페이지

**상태**: ⬜ 대기
**우선순위**: P1 (중요)
**예상 시간**: 40분
**서브에이전트**: 코드 작성 → `code-reviewer`

#### 작업 파일
```
admin-frontend/src/app/(dashboard)/withdrawals/page.tsx (새로 생성)
admin-frontend/src/components/withdrawals/WithdrawalList.tsx (새로 생성)
admin-frontend/src/components/withdrawals/WithdrawalStats.tsx (새로 생성)
```

#### 상세 태스크
- [ ] **5.1** 기존 입금 페이지 패턴 분석 (`deposits/page.tsx`)
- [ ] **5.2** 페이지 레이아웃 구현
  - [ ] 통계 카드 영역 (대기중, 오늘 완료, 총 완료)
  - [ ] 필터 영역 (상태, 날짜)
  - [ ] 테이블 영역
  - [ ] 페이징 영역
- [ ] **5.3** WithdrawalList 컴포넌트
  - [ ] 테이블 헤더 (ID, 사용자, 주소, 금액, 상태, 요청일, 액션)
  - [ ] 테이블 행 렌더링
  - [ ] 상태 배지 (색상 구분)
  - [ ] 액션 버튼 (상세보기, 승인, 거부)
- [ ] **5.4** WithdrawalStats 컴포넌트
  - [ ] 대기중 건수/금액
  - [ ] 오늘 완료 건수/금액
  - [ ] 총 완료 건수/금액
- [ ] **5.5** 자동 새로고침 (30초 간격)
- [ ] **5.6** 타입 체크 및 린트

#### 테스트 명령어
```bash
cd admin-frontend
npm run type-check
npm run lint
npm run dev  # 수동 확인
```

#### 완료 조건
- [ ] 페이지 렌더링 정상
- [ ] 필터 동작 정상
- [ ] 페이징 동작 정상
- [ ] 타입/린트 에러 없음

---

### 🔷 Phase 6: Frontend 출금 상세/승인/거부 모달

**상태**: ⬜ 대기
**우선순위**: P1 (중요)
**예상 시간**: 40분
**서브에이전트**: 코드 작성 → `code-reviewer`

#### 작업 파일
```
admin-frontend/src/components/withdrawals/WithdrawalDetail.tsx (새로 생성)
admin-frontend/src/components/withdrawals/ApproveModal.tsx (새로 생성)
admin-frontend/src/components/withdrawals/RejectModal.tsx (새로 생성)
```

#### 상세 태스크
- [ ] **6.1** WithdrawalDetail 모달
  - [ ] 사용자 정보 표시
  - [ ] 출금 주소 표시 (복사 버튼)
  - [ ] 금액 정보 (USDT, KRW, 수수료)
  - [ ] 상태 히스토리
  - [ ] TX Hash 링크 (블록 익스플로러)
- [ ] **6.2** ApproveModal 구현
  - [ ] TX Hash 입력 필드 (필수)
  - [ ] 메모 입력 필드 (선택)
  - [ ] 확인/취소 버튼
  - [ ] 로딩 상태
- [ ] **6.3** RejectModal 구현
  - [ ] 거부 사유 입력 필드 (필수)
  - [ ] 확인/취소 버튼
  - [ ] 로딩 상태
- [ ] **6.4** Toast 알림 연동
- [ ] **6.5** 타입 체크 및 린트

#### 완료 조건
- [ ] 모달 열기/닫기 정상
- [ ] 승인/거부 API 연동 정상
- [ ] 에러 처리 정상
- [ ] 타입/린트 에러 없음

---

### 🔷 Phase 7: Frontend 통합 테스트

**상태**: ⬜ 대기
**우선순위**: P2 (권장)
**예상 시간**: 20분
**서브에이전트**: `pr-test-analyzer`

#### 상세 태스크
- [ ] **7.1** 빌드 테스트 (`npm run build`)
- [ ] **7.2** 페이지 네비게이션 확인
- [ ] **7.3** API 연동 확인 (dev 서버 연결)
- [ ] **7.4** 반응형 레이아웃 확인

#### 테스트 명령어
```bash
cd admin-frontend
npm run build
npm run dev
```

#### 완료 조건
- [ ] 빌드 성공
- [ ] 모든 페이지 정상 동작
- [ ] 콘솔 에러 없음

---

### 🔷 Phase 8: 입금/출금 통합 대시보드

**상태**: ⬜ 대기
**우선순위**: P3 (선택)
**예상 시간**: 30분

#### 상세 태스크
- [ ] **8.1** 대시보드 메인 페이지에 입금/출금 요약 추가
- [ ] **8.2** 대기중 입금/출금 알림 배지
- [ ] **8.3** 사이드바 네비게이션 업데이트

#### 완료 조건
- [ ] 대시보드에서 입금/출금 현황 확인 가능
- [ ] 빠른 링크로 관리 페이지 이동 가능

---

## 🔧 서브에이전트 사용 가이드

### 각 단계별 권장 서브에이전트

| 단계 | 작업 시작 시 | 작업 완료 후 |
|------|-------------|-------------|
| Phase 1 | `code-architect` (설계) | `code-reviewer` (검토) |
| Phase 2 | - | `code-reviewer` (검토) |
| Phase 3 | - | `pr-test-analyzer` (테스트 분석) |
| Phase 4 | - | - |
| Phase 5 | `Explore` (패턴 분석) | `code-reviewer` (검토) |
| Phase 6 | - | `code-reviewer` (검토) |
| Phase 7 | `pr-test-analyzer` | - |
| Phase 8 | - | - |

### 서브에이전트 호출 예시

```
# 코드 아키텍처 설계
Task(subagent_type="code-architect", prompt="출금 서비스 구현 설계...")

# 코드 리뷰
Task(subagent_type="code-reviewer", prompt="구현된 코드 리뷰...")

# 테스트 분석
Task(subagent_type="pr-test-analyzer", prompt="테스트 커버리지 분석...")
```

---

## 📝 작업 로그

| 날짜 | 단계 | 작업 내용 | 결과 | 비고 |
|------|------|----------|------|------|
| 2026-01-18 | - | 작업 계획서 작성 | ✅ | Skills 파일 생성 완료 |
| 2026-01-18 | 1 | WithdrawalService 구현 | ✅ | code-architect, code-reviewer 활용 |
| - | - | - | - | - |

---

## ⚠️ 주의사항

1. **Hot Wallet 연동**
   - 실제 암호화폐 전송은 별도 시스템 필요
   - 현재는 관리자 수동 승인 후 TX Hash 입력 방식

2. **보안**
   - 출금 승인은 `supervisor` 이상 권한 필요
   - 모든 작업은 감사 로그에 기록

3. **테스트 환경**
   - 테스트 시 실제 블록체인 연동 없음
   - Mock 데이터 사용

---

## 📚 참고 문서

- Skills 파일: `.claude/skills/deposit-withdrawal-admin.md`
- 입금 구현 참고: `admin-backend/app/api/admin_ton_deposit.py`
- 출금 모델: `admin-backend/app/models/crypto.py`
- 메인 백엔드 출금: `backend/app/services/crypto_withdrawal.py`
