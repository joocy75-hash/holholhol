# 홀덤 프로젝트 작업 계획서 (2026)

> **작성일**: 2026-01-19
> **목적**: 백엔드/프론트엔드/관리자 페이지 작업 체계화 및 중단 없는 개발 진행

---

## 📋 목차

1. [작업 원칙](#작업-원칙)
2. [백엔드 작업](#백엔드-작업)
3. [프론트엔드 작업](#프론트엔드-작업)
4. [관리자 페이지 작업](#관리자-페이지-작업)
5. [단계별 검증 프로세스](#단계별-검증-프로세스)
6. [서브에이전트 활용 가이드](#서브에이전트-활용-가이드)
7. [작업 중단 대처 방안](#작업-중단-대처-방안)
8. [완료 체크리스트](#완료-체크리스트)

---

## 🎯 작업 원칙

### 핵심 원칙
1. **단계별 진행**: 한 번에 최대 3-5개 파일만 수정
2. **즉시 검증**: 각 단계 완료 시 즉시 테스트
3. **전문 에이전트**: 복잡한 작업은 반드시 서브에이전트 활용
4. **상태 기록**: 작업 완료 시 이 문서에 ✅ 체크
5. **토큰 관리**: 대규모 작업 전 토큰 사용량 확인

### 토큰 관리 전략
- 각 단계는 **10,000 토큰 이내**로 설계
- 서브에이전트 사용으로 컨텍스트 분리
- 작업 중 **30,000 토큰 초과 시** 즉시 상태 저장 후 계정 전환

### 계정 전환 시 체크리스트
```markdown
[ ] 현재 단계 번호 기록
[ ] 수정 중인 파일 목록 기록
[ ] 다음 작업 내용 간단히 메모
[ ] 테스트 미완료 항목 기록
[ ] WORK_PLAN_2026.md에 진행 상황 업데이트
```

---

## 🔧 백엔드 작업

### Phase 1: 핵심 게임 로직 완성 (P0 - 최우선)

#### 1.1 헤즈업(2인) 게임 규칙 구현
**예상 토큰**: ~8,000
**서브에이전트**: `feature-dev:code-architect` → `Bash` (테스트)

**작업 내용**:
- [ ] 1.1.1 헤즈업 감지 로직 (`backend/app/game/poker_table.py`)
  - `_is_heads_up()` 메서드 추가
  - 2명 감지 시 특수 모드 전환
- [ ] 1.1.2 헤즈업 블라인드 포스팅
  - 딜러가 스몰 블라인드 포스팅
  - `_post_blinds()` 메서드 수정
- [ ] 1.1.3 헤즈업 액션 순서
  - 프리플랍: 딜러(SB) 먼저 행동
  - 포스트플랍: 딜러 마지막 행동
  - `_get_next_acting_player()` 수정
- [ ] 1.1.4 헤즈업 ↔ 멀티 전환 처리
  - 3명 → 2명, 2명 → 3명 전환 시 블라인드 재조정
- [ ] 1.1.5 단위 테스트 작성
  - `tests/unit/game/test_heads_up.py` 생성
  - 최소 10개 테스트 케이스

**검증**:
```bash
pytest tests/unit/game/test_heads_up.py -v
```

**완료 조건**: 모든 헤즈업 테스트 통과 ✅

---

#### 1.2 언더 레이즈 규칙 구현
**예상 토큰**: ~6,000
**서브에이전트**: `feature-dev:code-explorer` → `Edit`

**작업 내용**:
- [ ] 1.2.1 올인 레이즈 크기 추적
  - `_last_full_raise` 변수 추가
  - `_current_bet` vs `_last_full_raise` 비교
- [ ] 1.2.2 언더 레이즈 감지
  - 올인 금액이 최소 레이즈 미만인지 체크
  - `_is_under_raise()` 메서드 추가
- [ ] 1.2.3 베팅 재개 방지
  - 언더 레이즈 시 이미 행동한 플레이어 리레이즈 차단
  - `get_available_actions()` 수정
- [ ] 1.2.4 단위 테스트
  - `tests/unit/game/test_under_raise.py`

**검증**:
```bash
pytest tests/unit/game/test_under_raise.py -v
```

**완료 조건**: 언더 레이즈 시나리오 모두 통과 ✅

---

#### 1.3 환불 로직 구현
**예상 토큰**: ~5,000
**서브에이전트**: `Edit` 직접

**작업 내용**:
- [ ] 1.3.1 콜되지 않은 베팅 환불
  - `_refund_uncalled_bets()` 메서드 추가
  - 모든 플레이어 폴드 시 자동 호출
- [ ] 1.3.2 환불 이벤트 발송
  - `REFUND` 이벤트 타입 추가 (`ws/events.py`)
  - WebSocket으로 환불 금액 전송
- [ ] 1.3.3 단위 테스트
  - `tests/unit/game/test_refund.py`

**검증**:
```bash
pytest tests/unit/game/test_refund.py -v
```

**완료 조건**: 환불 로직 테스트 통과 ✅

---

#### 1.4 홀수 칩 분배 로직
**예상 토큰**: ~4,000
**서브에이전트**: `Edit` 직접

**작업 내용**:
- [ ] 1.4.1 버튼 기준 좌석 거리 계산
  - `_distance_from_button()` 메서드 추가
- [ ] 1.4.2 스플릿 팟 홀수 칩 처리
  - `_distribute_pot()` 메서드 수정
  - 홀수 칩은 버튼 왼쪽에 가장 가까운 플레이어에게
- [ ] 1.4.3 단위 테스트
  - `tests/unit/game/test_odd_chips.py`

**검증**:
```bash
pytest tests/unit/game/test_odd_chips.py -v
```

**완료 조건**: 홀수 칩 분배 테스트 통과 ✅

---

### Phase 2: 블라인드 & 좌석 관리 (P1)

#### 2.1 미스드 블라인드 처리
**예상 토큰**: ~7,000
**서브에이전트**: `feature-dev:code-architect`

**작업 내용**:
- [ ] 2.1.1 미스드 블라인드 추적
  - 플레이어별 `missed_blinds` 카운터
  - `_track_missed_blinds()` 메서드
- [ ] 2.1.2 Wait for BB 옵션
  - 플레이어 상태에 `waiting_for_bb` 플래그
  - BB 도달 시 자동 참여
- [ ] 2.1.3 Post Dead Blind 옵션
  - 즉시 블라인드 지불 후 참여
  - `_post_dead_blind()` 메서드
- [ ] 2.1.4 API 엔드포인트
  - `POST /api/v1/table/{id}/rejoin` (옵션: wait_bb or post_dead)
- [ ] 2.1.5 단위 + 통합 테스트

**검증**:
```bash
pytest tests/unit/game/test_missed_blinds.py -v
pytest tests/integration/test_rejoin_api.py -v
```

**완료 조건**: 미스드 블라인드 처리 완료 ✅

---

#### 2.2 데드 버튼 규칙
**예상 토큰**: ~5,000
**서브에이전트**: `Edit` 직접

**작업 내용**:
- [ ] 2.2.1 플레이어 탈락 시 버튼 이동 로직
  - SB/BB 탈락 시 데드 버튼 처리
  - `_handle_player_leave()` 수정
- [ ] 2.2.2 다음 핸드 블라인드 위치 조정
- [ ] 2.2.3 단위 테스트

**검증**:
```bash
pytest tests/unit/game/test_dead_button.py -v
```

**완료 조건**: 데드 버튼 로직 테스트 통과 ✅

---

### Phase 3: 레이크 시스템 (P2)

#### 3.1 레이크 징수 로직
**예상 토큰**: ~8,000
**서브에이전트**: `feature-dev:code-architect`

**작업 내용**:
- [ ] 3.1.1 레이크 설정 추가
  - 테이블 설정에 `rake_percentage`, `rake_cap` 추가
  - 데이터베이스 마이그레이션
- [ ] 3.1.2 노 플랍, 노 드롭
  - 플랍 도달 시에만 레이크 징수
  - `_saw_flop` 플래그 활용
- [ ] 3.1.3 레이크 계산
  - `_calculate_rake()` 메서드
  - 팟 분배 전에 레이크 차감
- [ ] 3.1.4 레이크 기록
  - `hand_history` 테이블에 레이크 금액 저장
- [ ] 3.1.5 단위 테스트

**검증**:
```bash
pytest tests/unit/game/test_rake.py -v
```

**완료 조건**: 레이크 시스템 테스트 통과 ✅

---

### Phase 4: 보안 & RNG (P2)

#### 4.1 암호학적 CSPRNG 적용
**예상 토큰**: ~4,000
**서브에이전트**: `Edit` 직접

**작업 내용**:
- [ ] 4.1.1 PokerKit 내부 RNG 검증
  - 현재 사용 중인 랜덤 알고리즘 확인
- [ ] 4.1.2 필요 시 `secrets.SystemRandom()` 적용
- [ ] 4.1.3 셔플 알고리즘 검증 테스트

**검증**:
```bash
pytest tests/unit/game/test_rng.py -v
```

**완료 조건**: RNG 검증 완료 ✅

---

### Phase 5: E2E 테스트 인프라 (P0)

#### 5.1 Playwright E2E 테스트 설정
**예상 토큰**: ~10,000
**서브에이전트**: `feature-dev:code-architect`

**작업 내용**:
- [ ] 5.1.1 Playwright 설치 및 설정
  - `frontend/package.json`에 추가
  - `playwright.config.ts` 생성
- [ ] 5.1.2 테스트 헬퍼 유틸리티
  - `tests/e2e/helpers/auth.ts` (로그인)
  - `tests/e2e/helpers/table.ts` (테이블 조작)
- [ ] 5.1.3 기본 시나리오 1개 작성
  - `tests/e2e/basic-game-flow.spec.ts`

**검증**:
```bash
cd frontend
pnpm test:e2e
```

**완료 조건**: E2E 테스트 인프라 구축 완료 ✅

---

## 🎨 프론트엔드 작업

### Phase 6: UX 개선 - Pre-Action 버튼 (P1)

#### 6.1 Pre-Action 버튼 UI 구현
**예상 토큰**: ~9,000
**서브에이전트**: `frontend-design:frontend-design`

**작업 내용**:
- [ ] 6.1.1 PreActionPanel 컴포넌트 생성
  - `frontend/src/components/table/PreActionPanel.tsx`
  - 체크박스 스타일 버튼 (Check/Fold, Check, Call Any)
- [ ] 6.1.2 상태 관리
  - `usePreAction` 훅 생성
  - 선택된 Pre-Action 저장
- [ ] 6.1.3 조건부 렌더링
  - 내 턴이 아닐 때만 표시
  - 선택 시 시각적 피드백
- [ ] 6.1.4 스타일링
  - Tailwind CSS로 반응형 디자인

**검증**:
```bash
cd frontend
pnpm dev
# 수동 테스트: Pre-Action 버튼 클릭 → 시각적 확인
```

**완료 조건**: Pre-Action 버튼 표시 ✅

---

#### 6.2 Pre-Action 서버 로직 연동
**예상 토큰**: ~7,000
**서브에이전트**: `feature-dev:code-explorer`

**작업 내용**:
- [ ] 6.2.1 WebSocket 이벤트 추가
  - `PRE_ACTION_SET` (클라 → 서버)
  - `PRE_ACTION_EXECUTED` (서버 → 클라)
- [ ] 6.2.2 백엔드 핸들러
  - `backend/app/ws/handlers/pre_action.py` 생성
  - 플레이어별 Pre-Action 저장
- [ ] 6.2.3 자동 실행 로직
  - 턴 도달 시 Pre-Action 자동 실행
  - `poker_table.py`에 `_execute_pre_action()` 추가
- [ ] 6.2.4 Cancel 로직
  - 베팅 상황 변경 시 Pre-Action 자동 취소

**검증**:
```bash
# 백엔드 테스트
pytest tests/unit/ws/test_pre_action.py -v

# E2E 테스트
cd frontend
pnpm test:e2e -- tests/e2e/pre-action.spec.ts
```

**완료 조건**: Pre-Action 자동 실행 동작 ✅

---

### Phase 7: Sit Out 기능 (P1)

#### 7.1 Sit Out UI 구현
**예상 토큰**: ~6,000
**서브에이전트**: `Edit` 직접

**작업 내용**:
- [ ] 7.1.1 Sit Out 버튼 추가
  - `ActionPanel.tsx`에 "자리 비움" 버튼
  - 드롭다운: "다음 핸드부터" / "다음 BB 전"
- [ ] 7.1.2 상태 표시
  - 자리비움 상태 아이콘
  - "Sitting Out" 라벨 표시
- [ ] 7.1.3 Sit Back In 버튼
  - 자리비움 중 복귀 버튼

**검증**:
```bash
cd frontend
pnpm dev
# 수동 테스트: Sit Out 버튼 클릭 → 상태 변경 확인
```

**완료 조건**: Sit Out UI 완성 ✅

---

#### 7.2 Sit Out 서버 로직
**예상 토큰**: ~7,000
**서브에이전트**: `feature-dev:code-architect`

**작업 내용**:
- [ ] 7.2.1 플레이어 상태 확장
  - `sitting_out_next_hand`, `sitting_out_next_bb` 플래그
- [ ] 7.2.2 API 엔드포인트
  - `POST /api/v1/table/{id}/sit-out` (옵션: next_hand or next_bb)
  - `POST /api/v1/table/{id}/sit-in`
- [ ] 7.2.3 자동 처리 로직
  - 핸드 시작 시 `sitting_out_next_hand` 체크 → `sitting_out` 전환
  - BB 도달 시 `sitting_out_next_bb` 체크 → `sitting_out` 전환
- [ ] 7.2.4 타임아웃 자동 퇴장
  - 10분간 Sit Out 상태 시 자동 퇴장

**검증**:
```bash
pytest tests/unit/game/test_sit_out.py -v
pytest tests/integration/test_sit_out_api.py -v
```

**완료 조건**: Sit Out 로직 완성 ✅

---

### Phase 8: 오토 머크 기능 (P2)

#### 8.1 오토 머크 UI + 로직
**예상 토큰**: ~5,000
**서브에이전트**: `Edit` 직접

**작업 내용**:
- [ ] 8.1.1 설정 토글 버튼
  - 테이블 설정 패널에 "Auto Muck" 토글
  - localStorage에 설정 저장
- [ ] 8.1.2 쇼다운 시 카드 숨김
  - 패배 시 카드 뒷면 유지
  - 승자는 반드시 공개
- [ ] 8.1.3 서버 통신
  - `SHOWDOWN_RESULT` 응답에 `should_muck` 플래그

**검증**:
```bash
# E2E 테스트
pnpm test:e2e -- tests/e2e/auto-muck.spec.ts
```

**완료 조건**: 오토 머크 동작 ✅

---

### Phase 9: 환불 애니메이션 (P2)

#### 9.1 칩 환불 애니메이션
**예상 토큰**: ~4,000
**서브에이전트**: `Edit` 직접

**작업 내용**:
- [ ] 9.1.1 REFUND 이벤트 수신
  - `useTableWebSocket`에 `REFUND` 핸들러 추가
- [ ] 9.1.2 애니메이션 컴포넌트
  - Framer Motion으로 칩이 팟 → 플레이어 이동
  - `ChipRefundAnimation.tsx` 생성
- [ ] 9.1.3 사운드 효과 (선택)
  - 환불 시 사운드 재생

**검증**:
```bash
pnpm dev
# 수동 테스트: 환불 시나리오 → 애니메이션 확인
```

**완료 조건**: 환불 애니메이션 완성 ✅

---

## 👨‍💼 관리자 페이지 작업

### Phase 10: 게임 모니터링 대시보드 (P1)

#### 10.1 실시간 테이블 모니터링
**예상 토큰**: ~12,000
**서브에이전트**: `feature-dev:code-architect` + `frontend-design`

**작업 내용**:
- [ ] 10.1.1 관리자 API 엔드포인트
  - `GET /api/v1/admin/tables/live` (활성 테이블 목록)
  - `GET /api/v1/admin/tables/{id}/snapshot` (테이블 상세)
  - 인증: 관리자 권한 필요 (`is_admin` 체크)
- [ ] 10.1.2 프론트엔드 페이지
  - `frontend/src/app/admin/tables/page.tsx` 생성
  - 실시간 테이블 목록 (WebSocket 자동 갱신)
- [ ] 10.1.3 테이블 상세 모달
  - 플레이어 목록, 스택, 팟 크기
  - 현재 페이즈, 커뮤니티 카드
  - 핸드 히스토리 (최근 10개)
- [ ] 10.1.4 관리자 액션
  - 테이블 강제 종료
  - 플레이어 킥

**검증**:
```bash
# API 테스트
pytest tests/integration/test_admin_api.py -v

# 프론트엔드
pnpm dev
# http://localhost:3000/admin/tables 접속 확인
```

**완료 조건**: 실시간 모니터링 대시보드 완성 ✅

---

#### 10.2 플레이어 관리
**예상 토큰**: ~8,000
**서브에이전트**: `feature-dev:code-architect`

**작업 내용**:
- [ ] 10.2.1 플레이어 검색 API
  - `GET /api/v1/admin/players/search?q={nickname}`
- [ ] 10.2.2 플레이어 상세 정보
  - `GET /api/v1/admin/players/{id}`
  - 총 플레이 핸드 수, 승률, 총 수익
- [ ] 10.2.3 플레이어 제재
  - `POST /api/v1/admin/players/{id}/ban` (계정 정지)
  - `POST /api/v1/admin/players/{id}/unban` (정지 해제)
- [ ] 10.2.4 프론트엔드 페이지
  - `frontend/src/app/admin/players/page.tsx`

**검증**:
```bash
pytest tests/integration/test_admin_players.py -v
```

**완료 조건**: 플레이어 관리 기능 완성 ✅

---

#### 10.3 핸드 히스토리 뷰어
**예상 토큰**: ~10,000
**서브에이전트**: `feature-dev:code-architect`

**작업 내용**:
- [ ] 10.3.1 핸드 히스토리 저장 로직
  - `_save_hand_history()` 메서드 (백엔드)
  - PostgreSQL `hand_histories` 테이블에 저장
  - 액션 기록, 시작/종료 스택, 승자, 팟 크기
- [ ] 10.3.2 조회 API
  - `GET /api/v1/admin/hands?player_id={id}&limit=50`
  - `GET /api/v1/admin/hands/{hand_id}`
- [ ] 10.3.3 리플레이 UI
  - `frontend/src/app/admin/hands/[id]/page.tsx`
  - 액션 타임라인 표시
  - 재생/일시정지 버튼
  - 각 스트리트별 이동

**검증**:
```bash
pytest tests/integration/test_hand_history.py -v
pnpm dev
# 핸드 히스토리 페이지에서 리플레이 동작 확인
```

**완료 조건**: 핸드 히스토리 뷰어 완성 ✅

---

#### 10.4 통계 대시보드
**예상 토큰**: ~7,000
**서브에이전트**: `feature-dev:code-architect`

**작업 내용**:
- [ ] 10.4.1 통계 API
  - `GET /api/v1/admin/stats/daily` (일일 통계)
  - `GET /api/v1/admin/stats/overview` (전체 개요)
  - 활성 사용자 수, 완료된 핸드 수, 총 레이크, 평균 팟 크기
- [ ] 10.4.2 차트 라이브러리
  - Recharts 설치 및 설정
- [ ] 10.4.3 대시보드 페이지
  - `frontend/src/app/admin/dashboard/page.tsx`
  - 라인 차트: 일일 활성 사용자 추이
  - 바 차트: 시간대별 트래픽
  - 파이 차트: 게임 타입별 비율

**검증**:
```bash
pytest tests/integration/test_admin_stats.py -v
pnpm dev
# 대시보드 차트 표시 확인
```

**완료 조건**: 통계 대시보드 완성 ✅

---

## ✅ 단계별 검증 프로세스

### 검증 레벨

#### Level 1: 유닛 테스트 (필수)
```bash
# 백엔드
cd backend
pytest tests/unit/ -v --cov=app

# 프론트엔드
cd frontend
pnpm test
```

#### Level 2: 통합 테스트 (필수)
```bash
cd backend
pytest tests/integration/ -v
```

#### Level 3: E2E 테스트 (권장)
```bash
cd frontend
pnpm test:e2e
```

#### Level 4: 수동 테스트 (Phase 완료 시)
```markdown
[ ] 로컬 환경에서 전체 플로우 테스트
[ ] 크롬 개발자 도구로 네트워크 에러 확인
[ ] 콘솔 에러 0개 확인
[ ] WebSocket 메시지 정상 송수신 확인
```

---

## 🤖 서브에이전트 활용 가이드

### 에이전트 선택 기준

| 작업 유형 | 추천 에이전트 | 사용 시기 |
|----------|-------------|----------|
| 아키텍처 설계 | `feature-dev:code-architect` | 새 기능 설계 필요 시 |
| 코드 탐색 | `feature-dev:code-explorer` | 기존 코드 분석 필요 시 |
| 코드 리뷰 | `feature-dev:code-reviewer` | Phase 완료 후 코드 품질 체크 |
| 프론트엔드 디자인 | `frontend-design:frontend-design` | UI 컴포넌트 생성 시 |
| 테스트 분석 | `pr-review-toolkit:pr-test-analyzer` | 테스트 커버리지 검토 시 |

### 에이전트 호출 예시

```bash
# Phase 1.1 시작 전 (아키텍처 설계)
/feature-dev:code-architect "헤즈업 게임 규칙을 poker_table.py에 구현하는 아키텍처 설계"

# Phase 1.2 작업 중 (기존 코드 탐색)
/feature-dev:code-explorer "현재 베팅 로직에서 레이즈 금액을 어떻게 추적하는지 조사"

# Phase 6.1 완료 후 (코드 리뷰)
/feature-dev:code-reviewer "PreActionPanel.tsx의 코드 품질 검토"
```

### 복잡도별 에이전트 사용 전략

| 복잡도 | 파일 수 | 예상 토큰 | 에이전트 사용 |
|-------|---------|----------|------------|
| 낮음 | 1-2개 | <3,000 | 직접 `Edit` 도구 사용 |
| 중간 | 3-5개 | 3,000-7,000 | `code-explorer` → 직접 수정 |
| 높음 | 6개 이상 | 7,000+ | `code-architect` → 단계별 분할 |

---

## 🚨 작업 중단 대처 방안

### 중단 감지 신호
1. "Token limit approaching" 경고
2. 응답 속도 느려짐
3. 컨텍스트 창 30,000 토큰 초과

### 중단 전 필수 작업 (5분 이내)

#### 1. 진행 상황 기록
```bash
# WORK_PLAN_2026.md 업데이트
# 현재 Phase와 완료된 항목에 ✅ 표시
```

#### 2. 상태 파일 생성
```bash
# .planning/current_state.md 생성
```

파일 내용 예시:
```markdown
# 현재 작업 상태 (2026-01-19 14:30)

## 진행 중인 Phase
- Phase 1.1 헤즈업 게임 규칙 구현
- 진행률: 60% (1.1.1 ~ 1.1.3 완료, 1.1.4 작업 중)

## 수정 중인 파일
- backend/app/game/poker_table.py (Line 450-520)
- tests/unit/game/test_heads_up.py (새 파일)

## 다음 작업
- [ ] 1.1.4 헤즈업 ↔ 멀티 전환 처리 완료
- [ ] 1.1.5 단위 테스트 추가 (7개 더 필요)
- [ ] pytest 실행하여 검증

## 주의사항
- `_get_next_acting_player()` 메서드 수정 시 기존 로직 유지 필요
- 헤즈업 모드 플래그: `self._is_heads_up_mode`
```

#### 3. Git 커밋 (중요!)
```bash
cd /Users/mr.joo/Desktop/holdem
git add .
git commit -m "WIP: Phase 1.1 헤즈업 규칙 구현 중 (60%)"
git push origin develop
```

#### 4. 계정 전환 체크리스트 확인
```markdown
[✓] WORK_PLAN_2026.md 업데이트
[✓] .planning/current_state.md 생성
[✓] Git 커밋 및 푸시
[✓] 다음 계정에서 "/resume-work" 명령어로 복구
```

### 복구 프로세스 (새 계정)

```bash
# 1. 저장소 업데이트
cd /Users/mr.joo/Desktop/holdem
git pull origin develop

# 2. 상태 파일 확인
cat .planning/current_state.md

# 3. Skills 사용하여 복구
/resume-work

# 4. 작업 재개
# Phase에 따라 적절한 명령 실행
```

---

## 📝 완료 체크리스트

### Phase 완료 시 체크리스트

```markdown
## Phase [번호] 완료 체크리스트

### 코드 품질
[ ] 린트 에러 0개 (ESLint/Pylint)
[ ] 타입 에러 0개 (TypeScript/mypy)
[ ] 주석 및 문서화 완료
[ ] 코드 리뷰 에이전트 통과

### 테스트
[ ] 유닛 테스트 작성 및 통과
[ ] 통합 테스트 통과 (해당 시)
[ ] E2E 테스트 통과 (해당 시)
[ ] 커버리지 목표 달성 (80%+)

### 문서화
[ ] WORK_PLAN_2026.md에 ✅ 표시
[ ] 변경 사항 CHANGELOG.md에 기록
[ ] API 변경 시 API_REFERENCE.md 업데이트

### 배포 준비
[ ] 로컬 환경 전체 테스트
[ ] Git 커밋 및 푸시
[ ] PR 생성 (develop → main)
```

### 전체 작업 완료 체크리스트

```markdown
## 전체 프로젝트 완료

### 백엔드
[ ] Phase 1-4 모두 완료
[ ] 모든 유닛/통합 테스트 통과
[ ] PostgreSQL 마이그레이션 완료
[ ] API 문서 최신화

### 프론트엔드
[ ] Phase 6-9 모두 완료
[ ] E2E 테스트 전체 통과
[ ] 빌드 에러 없음
[ ] 성능 최적화 완료

### 관리자 페이지
[ ] Phase 10 모두 완료
[ ] 관리자 권한 검증 완료
[ ] 대시보드 차트 정상 표시

### 최종 배포
[ ] 스테이징 배포 완료
[ ] 스모크 테스트 통과
[ ] 프로덕션 배포 준비
```

---

## 🎯 우선순위 요약

### P0 (최우선 - 2주 이내)
1. Phase 1: 핵심 게임 로직 (1.1 ~ 1.4)
2. Phase 5: E2E 테스트 인프라

### P1 (중요 - 4주 이내)
3. Phase 2: 블라인드 & 좌석 관리
4. Phase 6: Pre-Action 버튼
5. Phase 7: Sit Out 기능
6. Phase 10: 관리자 모니터링

### P2 (추가 기능 - 8주 이내)
7. Phase 3: 레이크 시스템
8. Phase 4: 보안 & RNG
9. Phase 8: 오토 머크
10. Phase 9: 환불 애니메이션

---

## 📞 비상 연락 체계

### 작업 중단 시
1. `.planning/current_state.md` 확인
2. `WORK_PLAN_2026.md`에서 마지막 ✅ 위치 확인
3. `/resume-work` Skills 실행

### 에러 발생 시
1. `git status`로 변경 파일 확인
2. `git diff`로 변경 내용 검토
3. 문제 파일만 `git restore`로 복구
4. 해당 Phase 재시작

---

**문서 버전**: v1.0
**최종 업데이트**: 2026-01-19
**담당자**: Development Team
