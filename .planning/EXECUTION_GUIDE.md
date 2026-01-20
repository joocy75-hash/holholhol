# 홀덤 프로젝트 수정 작업 실행 가이드

> **버전**: 1.0
> **작성일**: 2026-01-20

---

## 📋 작업 개요

이 가이드는 홀덤 프로젝트의 감사 보고서에서 발견된 결함을 수정하기 위한 상세 실행 지침입니다.

---

## 🔴 P0: Critical 수정 (즉시 배포)

### P0-1: 패킷 보안 - HAND_RESULT 카드 노출 차단

**심각도**: 🔴 Critical
**예상 소요**: 6 Steps
**선행 조건**: 없음

#### Step 1: broadcast.py 파일 생성

**파일**: `backend/app/ws/broadcast.py`

**서브에이전트 호출**:
```yaml
Task:
  description: "PersonalizedBroadcaster 클래스 생성"
  subagent_type: "general-purpose"
  prompt: |
    backend/app/ws/broadcast.py 파일을 생성하세요.

    클래스: PersonalizedBroadcaster
    메서드: broadcast_hand_result(room_id, hand_result, player_seats)

    로직:
    1. 테이블의 모든 연결 조회
    2. 각 연결에 대해:
       - 해당 user_id의 seat 확인
       - showdown 데이터 필터링:
         - 자신의 seat: 카드 표시
         - 승자 seat: 카드 표시
         - 나머지: holeCards = None
    3. 개인화된 메시지 전송

    참고 파일:
    - backend/app/ws/handlers/action.py (라인 1097-1113)
    - backend/app/ws/manager.py
```

**완료 체크**:
- [ ] 파일 생성됨
- [ ] PersonalizedBroadcaster 클래스 구현됨
- [ ] broadcast_hand_result 메서드 구현됨
- [ ] 타입 힌트 추가됨
- [ ] 에러 처리 추가됨

**WORK_STATE.md 업데이트**: P0-1 Step 1 체크

---

#### Step 2: 단위 테스트 작성

**파일**: `backend/tests/ws/test_broadcast.py`

**서브에이전트 호출**:
```yaml
Task:
  description: "broadcast.py 단위 테스트 작성"
  subagent_type: "general-purpose"
  prompt: |
    backend/tests/ws/test_broadcast.py 파일을 생성하세요.

    테스트 클래스: TestPersonalizedBroadcaster

    테스트 케이스:
    1. test_player_sees_own_cards_and_winner_cards
       - 플레이어가 자신의 카드와 승자 카드를 볼 수 있는지
    2. test_spectator_sees_only_winner_cards
       - 관전자가 승자 카드만 볼 수 있는지
    3. test_non_winner_cards_are_masked
       - 승자가 아닌 다른 플레이어 카드가 None인지
    4. test_multiple_winners_all_cards_visible
       - 여러 승자가 있을 때 모든 승자 카드가 보이는지

    Mock 필요:
    - ConnectionManager
    - WebSocketConnection
```

**완료 체크**:
- [ ] 테스트 파일 생성됨
- [ ] 4개 테스트 케이스 작성됨
- [ ] Mock 객체 설정됨
- [ ] pytest 실행 가능

**WORK_STATE.md 업데이트**: P0-1 Step 2 체크

---

#### Step 3: action.py 수정

**파일**: `backend/app/ws/handlers/action.py`
**라인**: 1097-1113

**서브에이전트 호출**:
```yaml
Task:
  description: "action.py _broadcast_hand_result 메서드 수정"
  subagent_type: "general-purpose"
  prompt: |
    backend/app/ws/handlers/action.py 파일의
    _broadcast_hand_result 메서드 (라인 1097-1113)를 수정하세요.

    변경사항:
    1. 파일 상단에 import 추가:
       from app.ws.broadcast import PersonalizedBroadcaster

    2. 메서드 내부 수정:
       - game_manager에서 테이블 가져오기
       - player_seats 딕셔너리 생성 (user_id -> seat)
       - PersonalizedBroadcaster 인스턴스 생성
       - broadcast_hand_result 호출

    기존 broadcast_to_channel 호출 제거
```

**완료 체크**:
- [ ] import 문 추가됨
- [ ] player_seats 매핑 생성 로직 추가됨
- [ ] PersonalizedBroadcaster 사용으로 변경됨
- [ ] 기존 broadcast_to_channel 제거됨

**WORK_STATE.md 업데이트**: P0-1 Step 3 체크

---

#### Step 4: 테스트 실행

**명령어**:
```bash
cd backend && pytest tests/ws/test_broadcast.py -v
```

**예상 결과**:
```
tests/ws/test_broadcast.py::TestPersonalizedBroadcaster::test_player_sees_own_cards_and_winner_cards PASSED
tests/ws/test_broadcast.py::TestPersonalizedBroadcaster::test_spectator_sees_only_winner_cards PASSED
tests/ws/test_broadcast.py::TestPersonalizedBroadcaster::test_non_winner_cards_are_masked PASSED
tests/ws/test_broadcast.py::TestPersonalizedBroadcaster::test_multiple_winners_all_cards_visible PASSED
```

**완료 체크**:
- [ ] 모든 테스트 통과
- [ ] 실패 시 디버깅 완료

**WORK_STATE.md 업데이트**: P0-1 Step 4 체크

---

#### Step 5: 통합 테스트

**명령어**:
```bash
cd backend && pytest tests/ws/ -v
cd backend && pytest tests/e2e/ -v -k "hand_result"
```

**완료 체크**:
- [ ] 기존 테스트 영향 없음
- [ ] E2E 테스트 통과 (있다면)

**WORK_STATE.md 업데이트**: P0-1 Step 5 체크

---

#### Step 6: 코드 리뷰

**서브에이전트 호출**:
```yaml
Task:
  description: "P0-1 코드 리뷰"
  subagent_type: "feature-dev:code-reviewer"
  prompt: |
    다음 파일들의 코드 리뷰를 수행하세요:
    - backend/app/ws/broadcast.py
    - backend/app/ws/handlers/action.py (수정된 부분)
    - backend/tests/ws/test_broadcast.py

    검토 항목:
    1. 보안: 카드 정보가 의도치 않게 노출되는 경로 없는지
    2. 성능: 연결 수에 따른 성능 영향
    3. 에러 처리: 예외 상황 처리
    4. 코드 품질: 타입 힌트, 문서화, 네이밍
```

**완료 체크**:
- [ ] 보안 검토 완료
- [ ] 성능 검토 완료
- [ ] 에러 처리 검토 완료
- [ ] 코드 품질 검토 완료
- [ ] 발견된 이슈 수정 완료

**WORK_STATE.md 업데이트**: P0-1 Step 6 체크, Phase 완료 표시

---

### P0-2: Side Pot eligible_positions

**심각도**: 🟡 High
**예상 소요**: 4 Steps
**선행 조건**: 없음

#### Step 1: core.py 수정

**파일**: `backend/app/engine/core.py`
**라인**: 747-764

**서브에이전트 호출**:
```yaml
Task:
  description: "core.py _extract_pot_state 수정"
  subagent_type: "general-purpose"
  prompt: |
    backend/app/engine/core.py 파일의
    _extract_pot_state 메서드 (라인 747-764)를 수정하세요.

    현재 문제:
    - eligible_positions=() 으로 항상 빈 튜플

    수정사항:
    - pot.player_indices에서 eligible players 추출
    - self._pk_index_to_position 딕셔너리로 변환
    - eligible_positions 튜플로 설정

    수정 코드:
    ```python
    eligible_positions = tuple(
        self._pk_index_to_position.get(pk_idx, pk_idx)
        for pk_idx in pot.player_indices
    )

    side_pots.append(
        SidePot(
            amount=pot.amount,
            eligible_positions=eligible_positions,
        )
    )
    ```
```

**완료 체크**:
- [ ] eligible_positions 추출 로직 추가됨
- [ ] pk_index → position 변환됨

**WORK_STATE.md 업데이트**: P0-2 Step 1 체크

---

#### Step 2-4: 테스트 및 리뷰

(P0-1과 동일 패턴)

---

### P0-3: 재접속 TTL 연장

**심각도**: 🟡 Medium
**예상 소요**: 2 Steps
**선행 조건**: 없음

#### Step 1: manager.py 상수 추가 및 수정

**파일**: `backend/app/ws/manager.py`

**수정 내용**:
```python
# 파일 상단 (라인 27 근처)에 추가
USER_STATE_TTL_SECONDS = 1800  # 30분 (기존 300초에서 변경)

# 라인 737-739 수정
await self.redis.setex(
    f"ws:user_state:{user_id}",
    USER_STATE_TTL_SECONDS,  # 상수 사용
    json.dumps(state),
)
```

**완료 체크**:
- [ ] 상수 추가됨
- [ ] TTL 값 수정됨

---

## 🟡 P1: 기능 누락 수정

### P1-1: 관리자 레이크 설정 UI

(상세 Step 생략 - 위 GSD 계획서 참조)

### P1-2: 부정행위 자동 차단

(상세 Step 생략 - 위 GSD 계획서 참조)

---

## 🔵 P2: 토너먼트 기능

### P2-1: 블라인드 스케줄러

(상세 Step 생략 - 위 GSD 계획서 참조)

---

## 📌 작업 규칙

### 1. 서브에이전트 필수 사용

모든 코드 작성/수정 작업에 Task 도구 사용:
- 코드 작성: `subagent_type: "general-purpose"`
- 코드 탐색: `subagent_type: "Explore"`
- 코드 리뷰: `subagent_type: "feature-dev:code-reviewer"`

### 2. 체크포인트 필수

- 각 Step 완료 시 WORK_STATE.md 업데이트
- 토큰 경고 시 `/holdem-checkpoint` 실행
- 작업 중단 시 `/holdem-handoff` 실행

### 3. 테스트 필수

- 코드 수정 후 반드시 테스트 실행
- 테스트 실패 시 다음 Step 진행 금지

### 4. Git 커밋 권장

- 각 Phase 완료 시 커밋
- 커밋 메시지 형식: `fix(P0-1): 패킷 보안 수정`

---

## 🆘 문제 해결

### 테스트 실패 시
1. 에러 메시지 확인
2. 관련 코드 재검토
3. 서브에이전트로 디버깅 요청

### 토큰 소진 시
1. `/holdem-checkpoint` 즉시 실행
2. `/holdem-handoff` 실행
3. 다음 계정에서 `/holdem-resume`

### 충돌 발생 시
1. WORK_STATE.md 확인
2. 다른 작업자와 조율
3. 필요시 Git stash 사용
