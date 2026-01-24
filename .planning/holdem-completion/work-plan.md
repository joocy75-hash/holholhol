# Holdem 프로젝트 완성 작업 계획서

> **버전**: 1.0.0
> **작성일**: 2026-01-24
> **목표**: 홀덤 게임 90% → 100% 완성도 달성

---

## 📊 현재 상태 분석 (Current State)

### 기존 인프라
| 구성요소 | 현재 상태 | 비고 |
|---------|----------|------|
| User 모델 | `email` + `nickname` 기반 | UUID 사용 |
| AdminUser 모델 | `email` + `username` 기반 | 이메일 로그인 |
| 회원가입 | email/nickname/password/partnerCode | USDT 주소 없음 |
| 로그인 | email + password | 일반 ID 미지원 |
| 이벤트 시스템 | 미구현 | 출석/추천 없음 |
| 쪽지/공지 | 미구현 | 팝업 없음 |

### DB 스키마 현황
```
users:
  - id: UUID (해시)
  - email: String(255) UNIQUE
  - nickname: String(50) UNIQUE
  - password_hash: String(255)
  - partner_id: UUID (nullable)
  - [USDT 주소 필드 없음]
  - [일반 username 필드 없음]
```

---

## 🎯 작업 우선순위 (Priority Matrix)

```
P0 (Critical) ─────────────────────────────────────
│ 1. 로그인 방식 변경: 이메일 → 일반 ID
│ 2. DB 스키마 마이그레이션
│ 3. 백엔드/프론트엔드 인증 로직 수정
└──────────────────────────────────────────────────

P1 (High) ─────────────────────────────────────────
│ 1. User ID 매핑: UUID → 가독성 있는 ID 표시
│ 2. 어드민 유저 상세 페이지 확장
│ 3. 추천인/입출금/USDT 주소 필드 추가
└──────────────────────────────────────────────────

P2 (Medium) ───────────────────────────────────────
│ 1. 회원가입 양식 확장 (USDT 지갑 필수)
│ 2. 공지 팝업 시스템
│ 3. 관리자 쪽지 발송 기능
└──────────────────────────────────────────────────

P3 (Low) ──────────────────────────────────────────
│ 1. 출석체크 이벤트
│ 2. 친구추천 이벤트
│ 3. 이벤트 관리 UI
└──────────────────────────────────────────────────
```

---

## 📋 Phase 0: Core Auth (P0)

### Step 0.1: DB 스키마 마이그레이션
**예상 시간**: 1시간
**담당**: DB Migration Sub-Agent

#### 체크리스트
- [ ] 0.1.1 `users` 테이블에 `username` 컬럼 추가 (String(50), UNIQUE, NOT NULL)
- [ ] 0.1.2 기존 유저 username 자동 생성 (nickname 기반 또는 랜덤)
- [ ] 0.1.3 `admin_users` 테이블 email → username 로그인 전환 확인
- [ ] 0.1.4 Alembic 마이그레이션 파일 생성 및 테스트
- [ ] 0.1.5 Downgrade 스크립트 검증

#### 작업 내용
```sql
-- Migration: Add username column
ALTER TABLE users ADD COLUMN username VARCHAR(50) UNIQUE;

-- Populate existing users
UPDATE users SET username =
  LOWER(REGEXP_REPLACE(nickname, '[^a-zA-Z0-9]', '', 'g')) || '_' || SUBSTRING(id::text, 1, 6);

-- Make NOT NULL after population
ALTER TABLE users ALTER COLUMN username SET NOT NULL;
```

### Step 0.2: Backend Auth 수정
**예상 시간**: 2시간
**담당**: Backend Sub-Agent

#### 체크리스트
- [ ] 0.2.1 `backend/app/models/user.py` - username 필드 추가
- [ ] 0.2.2 `backend/app/schemas/requests.py` - LoginRequest 수정 (email → username)
- [ ] 0.2.3 `backend/app/services/auth.py` - login() 메서드 수정
- [ ] 0.2.4 `backend/app/api/auth.py` - 엔드포인트 수정
- [ ] 0.2.5 단위 테스트 작성 및 통과 확인

#### 주요 변경 파일
```
backend/
├── app/
│   ├── models/user.py          # username 필드 추가
│   ├── schemas/requests.py     # LoginRequest 수정
│   ├── services/auth.py        # 로그인 로직 수정
│   └── api/auth.py             # 엔드포인트 수정
└── tests/
    └── api/test_auth.py        # 테스트 업데이트
```

### Step 0.3: Frontend Auth 수정
**예상 시간**: 1.5시간
**담당**: Frontend Sub-Agent

#### 체크리스트
- [ ] 0.3.1 `frontend/src/app/login/page.tsx` - 이메일 → 아이디 필드 변경
- [ ] 0.3.2 `frontend/src/stores/auth.ts` - login 함수 수정
- [ ] 0.3.3 `frontend/src/lib/api.ts` - 요청 형식 수정
- [ ] 0.3.4 UI 렌더링 테스트
- [ ] 0.3.5 E2E 테스트 통과

### Step 0.4: Admin Auth 수정
**예상 시간**: 1시간
**담당**: Admin Sub-Agent

#### 체크리스트
- [ ] 0.4.1 `admin-backend/app/api/auth.py` - LoginRequest 수정
- [ ] 0.4.2 `admin-frontend/src/app/(auth)/login/page.tsx` - 이메일 → 아이디
- [ ] 0.4.3 기존 admin 계정 마이그레이션
- [ ] 0.4.4 로그인 테스트

---

## 📋 Phase 1: User/Admin Mapping (P1)

### Step 1.1: 사용자 ID 표시 변경
**예상 시간**: 1시간

#### 체크리스트
- [ ] 1.1.1 UUID 대신 username 또는 display_id 표시
- [ ] 1.1.2 어드민 대시보드 유저 목록 수정
- [ ] 1.1.3 유저 상세 페이지 ID 표시 방식 변경

### Step 1.2: 유저 상세 정보 확장
**예상 시간**: 2시간

#### 체크리스트
- [ ] 1.2.1 추천인 정보 표시 (partner_id → partner_name)
- [ ] 1.2.2 입금 내역 테이블 추가
- [ ] 1.2.3 출금 내역 테이블 추가
- [ ] 1.2.4 USDT 지갑 주소 표시

### Step 1.3: DB 필드 추가
**예상 시간**: 1시간

#### 체크리스트
- [ ] 1.3.1 `users.usdt_wallet_address` 컬럼 추가 (String, nullable)
- [ ] 1.3.2 `users.referrer_id` 컬럼 추가 (자기 추천인, partner와 별개)
- [ ] 1.3.3 마이그레이션 실행

---

## 📋 Phase 2: UI/UX Extension (P2)

### Step 2.1: 회원가입 양식 확장
**예상 시간**: 1.5시간

#### 체크리스트
- [ ] 2.1.1 USDT 지갑 주소 입력란 추가 (필수)
- [ ] 2.1.2 TRC20/ERC20 주소 유효성 검증
- [ ] 2.1.3 추천인 코드 (선택) 유지
- [ ] 2.1.4 백엔드 RegisterRequest 스키마 수정
- [ ] 2.1.5 회원가입 API 수정

### Step 2.2: 공지 팝업 시스템
**예상 시간**: 3시간

#### 체크리스트
- [ ] 2.2.1 `announcements` 테이블 생성 (admin-backend에 이미 있음 확인)
- [ ] 2.2.2 팝업 타입 추가 (login_popup, notice, event)
- [ ] 2.2.3 프론트엔드 팝업 컴포넌트 생성
- [ ] 2.2.4 로그인 시 팝업 공지 조회 API
- [ ] 2.2.5 어드민 공지 관리 UI

### Step 2.3: 쪽지 시스템
**예상 시간**: 3시간

#### 체크리스트
- [ ] 2.3.1 `messages` 테이블 설계 및 생성
- [ ] 2.3.2 쪽지 발송 API (admin → user)
- [ ] 2.3.3 쪽지 조회 API (user)
- [ ] 2.3.4 읽음 표시 기능
- [ ] 2.3.5 어드민 쪽지 발송 UI
- [ ] 2.3.6 유저 쪽지함 UI

---

## 📋 Phase 3: Event System (P3)

### Step 3.1: 출석체크 이벤트
**예상 시간**: 3시간

#### 체크리스트
- [ ] 3.1.1 `daily_checkins` 테이블 생성
- [ ] 3.1.2 출석체크 API 엔드포인트
- [ ] 3.1.3 연속 출석 보상 로직
- [ ] 3.1.4 프론트엔드 출석체크 UI
- [ ] 3.1.5 어드민 출석 현황 통계

### Step 3.2: 친구추천 이벤트
**예상 시간**: 2시간

#### 체크리스트
- [ ] 3.2.1 추천 보상 로직 구현 (추천인/피추천인 양방향)
- [ ] 3.2.2 추천 코드 생성 API
- [ ] 3.2.3 추천 현황 조회 API
- [ ] 3.2.4 프론트엔드 추천 페이지
- [ ] 3.2.5 어드민 추천 통계

### Step 3.3: 이벤트 관리 UI
**예상 시간**: 2시간

#### 체크리스트
- [ ] 3.3.1 이벤트 목록/상세 페이지
- [ ] 3.3.2 이벤트 생성/수정/삭제 기능
- [ ] 3.3.3 이벤트 참여자 목록
- [ ] 3.3.4 보상 지급 내역

---

## 📊 예상 총 작업 시간

| Phase | 예상 시간 | 우선순위 |
|-------|----------|---------|
| P0: Core Auth | 5.5시간 | Critical |
| P1: User/Admin Mapping | 4시간 | High |
| P2: UI/UX Extension | 7.5시간 | Medium |
| P3: Event System | 7시간 | Low |
| **Total** | **24시간** | - |

---

## 🔄 작업 진행 추적

### Current State Summary Template
```markdown
## Current State Summary (작업 중단 시 작성)

### 완료된 작업
- [x] Step X.X.X: 설명

### 진행 중인 작업
- [ ] Step X.X.X: 설명
  - 현재 상태: [상세 설명]
  - 다음 단계: [해야 할 일]
  - 관련 파일: [파일 경로]

### 블로커/이슈
- Issue #X: [설명]

### 다음 세션 시작 시
1. [첫 번째 할 일]
2. [두 번째 할 일]

### 관련 커밋
- [commit hash]: [메시지]
```

---

## ✅ 최종 검증 체크리스트

### 기능 테스트
- [ ] 일반 ID로 로그인 가능
- [ ] 회원가입 시 USDT 주소 저장
- [ ] 어드민에서 유저 상세 정보 확인
- [ ] 공지 팝업 정상 표시
- [ ] 쪽지 발송/수신 정상
- [ ] 출석체크 보상 지급
- [ ] 친구추천 보상 지급

### 보안 테스트
- [ ] SQL Injection 방지
- [ ] XSS 방지
- [ ] CSRF 토큰 검증
- [ ] Rate Limiting 적용

### 성능 테스트
- [ ] 로그인 응답 < 200ms
- [ ] 대시보드 로딩 < 1s
- [ ] DB 쿼리 최적화 확인

---

**마지막 업데이트**: 2026-01-24 12:00 KST
