# 홀덤 프로젝트 수정 작업 실행

메인 수정 작업을 서브에이전트를 활용하여 단계별로 실행합니다.

## 사용법
```
/holdem-fix [phase] [step]
```

예시:
- `/holdem-fix` - 전체 작업 상태 확인 후 다음 작업 자동 시작
- `/holdem-fix P0-1` - P0-1 (패킷 보안) 전체 실행
- `/holdem-fix P0-1 3` - P0-1의 Step 3부터 실행

---

## 작업 시작 전 필수 프로토콜

### 1. 상태 파일 확인
먼저 `.planning/WORK_STATE.md` 파일을 읽어서 현재 상태를 파악하세요.

### 2. 계정 식별자 기록
작업 시작 시 WORK_STATE.md의 "현재 작업자" 필드를 업데이트하세요.

### 3. 진행 중인 작업 확인
다른 계정이 작업 중이었다면 해당 체크포인트부터 재개하세요.

---

## Phase별 작업 지침

### P0-1: 패킷 보안 (HAND_RESULT 필터링)

**목표**: 모든 플레이어 카드가 브로드캐스트되는 보안 취약점 수정

**서브에이전트 사용 지침**:
```
각 Step마다 Task 도구로 전문 서브에이전트를 호출하세요:
- Step 1-3: subagent_type="general-purpose" (코드 작성)
- Step 4-5: subagent_type="feature-dev:code-reviewer" (코드 리뷰)
```

**Step 1: broadcast.py 파일 생성**
```
Task 도구 호출:
- description: "PersonalizedBroadcaster 클래스 생성"
- subagent_type: "general-purpose"
- prompt: |
    backend/app/ws/broadcast.py 파일을 생성하세요.

    요구사항:
    1. PersonalizedBroadcaster 클래스 구현
    2. broadcast_hand_result 메서드: 플레이어별 showdown 필터링
    3. 관전자는 승자 카드만, 플레이어는 자신+승자 카드만 표시

    참고 파일: backend/app/ws/handlers/action.py (라인 1097-1113)
```

**완료 후 체크**: WORK_STATE.md에서 P0-1 Step 1 체크박스 표시

**Step 2: PersonalizedBroadcaster 테스트**
```
Task 도구 호출:
- description: "broadcast.py 단위 테스트 작성"
- subagent_type: "general-purpose"
- prompt: |
    backend/tests/ws/test_broadcast.py 파일을 생성하세요.

    테스트 케이스:
    1. 플레이어가 자신의 카드와 승자 카드를 볼 수 있는지
    2. 관전자가 승자 카드만 볼 수 있는지
    3. 마스킹된 카드가 None인지
```

**완료 후 체크**: WORK_STATE.md에서 P0-1 Step 2 체크박스 표시

**Step 3: action.py 수정**
```
Task 도구 호출:
- description: "action.py _broadcast_hand_result 메서드 수정"
- subagent_type: "general-purpose"
- prompt: |
    backend/app/ws/handlers/action.py 파일의
    _broadcast_hand_result 메서드 (라인 1097-1113)를 수정하세요.

    변경사항:
    1. PersonalizedBroadcaster import 추가
    2. 기존 broadcast_to_channel 대신 PersonalizedBroadcaster 사용
    3. player_seats 매핑 생성 후 전달
```

**완료 후 체크**: WORK_STATE.md에서 P0-1 Step 3 체크박스 표시

**Step 4: 테스트 실행**
```bash
cd backend && pytest tests/ws/test_broadcast.py -v
```

**완료 후 체크**: WORK_STATE.md에서 P0-1 Step 4 체크박스 표시

**Step 5: 코드 리뷰**
```
Task 도구 호출:
- description: "P0-1 코드 리뷰"
- subagent_type: "feature-dev:code-reviewer"
- prompt: |
    다음 파일들의 코드 리뷰를 수행하세요:
    - backend/app/ws/broadcast.py
    - backend/app/ws/handlers/action.py (수정된 부분)
    - backend/tests/ws/test_broadcast.py

    검토 항목:
    1. 보안 취약점 없는지
    2. 모든 엣지 케이스 처리되는지
    3. 성능 이슈 없는지
```

**완료 후 체크**: WORK_STATE.md에서 P0-1 Step 5-6 체크박스 표시

---

### P0-2: Side Pot eligible_positions

**목표**: Side Pot에서 eligible_positions가 비어있는 문제 수정

**Step 1: core.py 수정**
```
Task 도구 호출:
- description: "core.py _extract_pot_state 수정"
- subagent_type: "general-purpose"
- prompt: |
    backend/app/engine/core.py 파일의
    _extract_pot_state 메서드 (라인 747-764)를 수정하세요.

    변경사항:
    1. pot.player_indices에서 eligible players 추출
    2. pk_index를 position으로 변환
    3. eligible_positions 튜플로 설정
```

**Step 2-4**: 테스트 및 리뷰 (P0-1과 동일 패턴)

---

### P0-3: TTL 연장

**Step 1-2**: manager.py 수정 (간단한 상수 변경)

---

### P1-1: 레이크 설정 UI

**Step 1: Backend API**
```
Task 도구 호출:
- description: "레이크 설정 API 생성"
- subagent_type: "general-purpose"
- prompt: |
    admin-backend/app/api/rake_settings.py 파일을 생성하세요.

    엔드포인트:
    - GET /rake-settings/: 설정 목록
    - PUT /rake-settings/{id}: 설정 업데이트
```

**Step 2: Frontend 페이지** (별도 서브에이전트)

---

## 작업 완료 시 프로토콜

### 1. 체크포인트 기록
```
WORK_STATE.md에서:
1. 해당 Step 체크박스 [x] 표시
2. "마지막 완료 작업" 섹션 업데이트
3. "진행 중인 작업" 섹션 초기화 또는 다음 작업으로 업데이트
```

### 2. Git 커밋 (선택적)
```bash
git add -A
git commit -m "fix(P0-1): 패킷 보안 - Step N 완료"
```

### 3. 다음 작업자 인계 준비
토큰 소진이 임박하면:
1. 현재 작업 상태를 WORK_STATE.md에 상세히 기록
2. 진행 중인 파일 저장
3. "계정 전환 로그" 섹션에 기록

---

## 토큰 소진 대비

### 토큰 경고 시 즉시 실행
1. 현재 작업 중단점 기록
2. WORK_STATE.md 업데이트
3. 작업 중인 파일 저장
4. 다음 명령어로 상태 저장:
   ```
   /holdem-checkpoint "P0-1 Step 3 진행 중, action.py 50% 수정 완료"
   ```

### 새 계정으로 재개 시
```
/holdem-resume
```
