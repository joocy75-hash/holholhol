# Implementation Plan: Quick Join (빠른 입장)

## Overview

Quick Join 기능을 단계별로 구현합니다. 각 단계 완료 후 테스트를 실행하고 체크리스트를 업데이트합니다.

## 작업 지침

> ⚠️ **중요**: 각 작업 완료 시 반드시 해당 체크박스를 `[x]`로 변경하세요.
> 작업 중단 시에도 진행 상황을 파악할 수 있습니다.

---

## Tasks

- [x] 1. 스키마 및 타입 정의
  - [x] 1.1 QuickJoinRequest, QuickJoinResponse 스키마 추가
    - 파일: `backend/app/schemas/__init__.py` 또는 새 파일
    - blind_level 옵션 필드 포함
    - _Requirements: 1.1, 2.4_
  - [x] 1.2 에러 코드 상수 추가
    - NO_AVAILABLE_ROOM, INSUFFICIENT_BALANCE 등
    - 파일: `backend/app/utils/errors.py`
    - _Requirements: 1.4, 1.5_

- [x] 2. Room Matcher 서비스 구현
  - [x] 2.1 RoomMatcher 클래스 생성
    - 새 파일: `backend/app/services/room_matcher.py`
    - find_best_room() 메서드 구현
    - _Requirements: 1.2, 2.1, 2.2, 2.3_
  - [x] 2.2 방 우선순위 점수 계산 로직 구현
    - calculate_room_score() 메서드
    - 게임 진행 중 > 대기 중, 플레이어 많은 방 우선
    - _Requirements: 2.1_
  - [x] 2.3 바이인 계산 로직 구현
    - calculate_default_buy_in() 함수
    - 최대 바이인의 50% 기본값
    - _Requirements: 3.1, 3.2, 3.3_
  - [x]* 2.4 Property Test: Room Filtering
    - **Property 1: Room Filtering Correctness**
    - **Validates: Requirements 1.1, 2.3, 2.4**
  - [x]* 2.5 Property Test: Room Selection Priority
    - **Property 2: Room Selection Priority**
    - **Validates: Requirements 1.2, 2.1, 2.2**
  - [x]* 2.6 Property Test: Buy-in Calculation
    - **Property 3: Buy-in Calculation Correctness**
    - **Validates: Requirements 3.1, 3.2**

- [x] 3. Room Service 확장
  - [x] 3.1 find_available_rooms() 메서드 추가
    - 파일: `backend/app/services/room.py`
    - 사용자 잔액 기반 필터링
    - _Requirements: 1.1_
  - [x] 3.2 quick_join_room() 메서드 추가
    - 방 입장 및 좌석 배정 로직
    - _Requirements: 1.3_
  - [x]* 3.3 Unit Test: Room Service 확장 메서드
    - find_available_rooms, quick_join_room 테스트
    - _Requirements: 1.1, 1.3_

- [x] 4. Quick Join API 엔드포인트 구현
  - [x] 4.1 POST /rooms/quick-join 엔드포인트 추가
    - 파일: `backend/app/api/rooms.py`
    - RoomMatcher 및 RoomService 통합
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 4.2 에러 핸들링 구현
    - NO_AVAILABLE_ROOM, INSUFFICIENT_BALANCE 처리
    - _Requirements: 1.4, 1.5_
  - [x]* 4.3 Integration Test: Quick Join API
    - 전체 흐름 테스트
    - _Requirements: 1.1-1.5_

- [x] 5. Checkpoint - 백엔드 테스트 검증
  - 모든 백엔드 테스트 통과 확인
  - `pytest backend/tests/` 실행
  - 문제 발생 시 사용자에게 질문

- [x] 6. 프론트엔드 구현
  - [x] 6.1 Quick Join API 클라이언트 함수 추가
    - 파일: `frontend/src/lib/api.ts` 또는 관련 파일
    - _Requirements: 4.2_
  - [x] 6.2 QuickJoinButton 컴포넌트 생성
    - 새 파일: `frontend/src/components/lobby/QuickJoinButton.tsx`
    - 로딩 상태, 에러 처리 포함
    - _Requirements: 4.1, 4.2, 4.4_
  - [x] 6.3 로비 페이지에 QuickJoinButton 통합
    - 파일: `frontend/src/app/lobby/page.tsx`
    - 기존 UI 스타일과 일관성 유지
    - _Requirements: 4.1, 4.3_
  - [ ]* 6.4 E2E Test: Quick Join 흐름
    - 로비 → 빠른 입장 → 테이블 이동
    - _Requirements: 4.1-4.4_

- [x] 7. Final Checkpoint - 전체 테스트 검증
  - 백엔드 테스트: `pytest backend/tests/`
  - 프론트엔드 테스트: `npm test` (frontend 디렉토리)
  - 문제 발생 시 사용자에게 질문

- [x] 8. IMPLEMENTATION_STATUS.md 업데이트
  - 빠른 입장(Quick Join) 항목 체크 완료
  - _Requirements: 전체_

---

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 각 작업 완료 시 반드시 체크박스 업데이트
- 기존 코드 수정 시 기존 테스트가 깨지지 않도록 주의
- Property tests는 Hypothesis 라이브러리 사용
