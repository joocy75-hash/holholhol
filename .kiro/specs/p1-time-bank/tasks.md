# Implementation Plan: Time Bank (타임 뱅크)

## Overview

Time Bank 기능을 단계별로 구현합니다. 각 단계 완료 후 테스트를 실행하고 체크리스트를 업데이트합니다.

## 작업 지침

> ⚠️ **중요**: 각 작업 완료 시 반드시 해당 체크박스를 `[x]`로 변경하세요.
> 작업 중단 시에도 진행 상황을 파악할 수 있습니다.

---

## Tasks

- [x] 1. Player 클래스 확장
  - [x] 1.1 time_bank_remaining 필드 추가
    - 파일: `backend/app/game/poker_table.py`
    - Player dataclass에 time_bank_remaining: int = 3 추가
    - _Requirements: 1.1, 1.3_
  - [x] 1.2 TimeBankResult 타입 정의
    - 파일: `backend/app/game/types.py`
    - success, remaining, added_seconds, new_deadline, error 필드
    - _Requirements: 2.1, 2.2_

- [x] 2. PokerTable 타임 뱅크 메서드 구현
  - [x] 2.1 상수 정의
    - TIME_BANK_COUNT = 3
    - TIME_BANK_SECONDS = 30
    - _Requirements: 1.1, 1.2_
  - [x] 2.2 use_time_bank() 메서드 구현
    - 현재 턴 검증, 횟수 검증
    - 타이머 연장, 횟수 차감
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  - [x] 2.3 reset_time_banks() 메서드 구현
    - 핸드 시작 시 호출
    - _Requirements: 1.1_
  - [x] 2.4 start_hand()에서 reset_time_banks() 호출 추가
    - _Requirements: 1.1_
  - [x]* 2.5 Property Test: Time Bank Initialization
    - **Property 1: Time Bank Initialization**
    - **Validates: Requirements 1.1, 1.2, 1.3**
  - [x]* 2.6 Property Test: Time Bank Usage Effect
    - **Property 2: Time Bank Usage Effect**
    - **Validates: Requirements 2.1, 2.2**

- [x] 3. WebSocket 이벤트 추가
  - [x] 3.1 EventType에 TIME_BANK_REQUEST, TIME_BANK_USED 추가
    - 파일: `backend/app/ws/events.py`
    - _Requirements: 2.5_
  - [x] 3.2 Action Handler에 _handle_time_bank() 메서드 추가
    - 파일: `backend/app/ws/handlers/action.py`
    - handled_events에 TIME_BANK_REQUEST 추가
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 3.3 TIME_BANK_USED 브로드캐스트 구현
    - _Requirements: 2.5_
  - [x]* 3.4 Unit Test: Time Bank Handler
    - 성공 케이스, 에러 케이스 테스트
    - _Requirements: 2.1-2.5_

- [x] 4. Checkpoint - 백엔드 테스트 검증
  - 모든 백엔드 테스트 통과 확인
  - `pytest backend/tests/` 실행
  - 문제 발생 시 사용자에게 질문

- [x] 5. 프론트엔드 구현
  - [x] 5.1 WebSocket 이벤트 타입 추가
    - 파일: `frontend/src/types/websocket.ts`
    - TIME_BANK_REQUEST, TIME_BANK_USED 타입
    - _Requirements: 2.5_
  - [x] 5.2 TimeBankButton 컴포넌트 생성
    - 새 파일: `frontend/src/components/table/TimeBankButton.tsx`
    - 남은 횟수 표시, 사용 버튼
    - _Requirements: 3.1, 3.2, 3.3_
  - [x] 5.3 테이블 페이지에 TimeBankButton 통합
    - 파일: `frontend/src/app/table/[id]/page.tsx`
    - 자신의 턴일 때만 활성화
    - _Requirements: 3.2, 3.4_
  - [x] 5.4 TIME_BANK_USED 이벤트 처리
    - 타이머 UI 업데이트
    - _Requirements: 3.4_

- [x] 6. Final Checkpoint - 전체 테스트 검증
  - 백엔드 테스트: `pytest backend/tests/`
  - 프론트엔드 빌드: `npm run build`
  - 문제 발생 시 사용자에게 질문

- [x] 7. IMPLEMENTATION_STATUS.md 업데이트
  - 타임 뱅크(Time Bank) 항목 체크 완료
  - _Requirements: 전체_

---

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 각 작업 완료 시 반드시 체크박스 업데이트
- 기존 코드 수정 시 기존 테스트가 깨지지 않도록 주의
- 타이머 로직은 기존 _turn_started_at 필드 활용
