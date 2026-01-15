# Requirements Document

## Introduction

빠른 입장(Quick Join) 기능은 사용자가 복잡한 방 선택 과정 없이 자동으로 적합한 방에 배정되는 UX 핵심 기능입니다. 사용자의 보유 자산과 선호 조건에 맞는 빈 자리가 있는 방으로 자동 배정합니다.

## Glossary

- **Quick_Join_Service**: 빠른 입장 로직을 처리하는 서비스 모듈
- **Room_Matcher**: 사용자 조건에 맞는 방을 찾는 매칭 알고리즘
- **Available_Room**: 빈 좌석이 있고 입장 가능한 상태의 방
- **Buy_In_Range**: 방의 최소/최대 바이인 범위
- **User_Balance**: 사용자의 현재 보유 칩

## Requirements

### Requirement 1: 빠른 입장 API

**User Story:** As a 플레이어, I want 빠른 입장 버튼을 클릭하면 자동으로 적합한 방에 입장하고 싶다, so that 복잡한 방 선택 과정 없이 빠르게 게임을 시작할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 빠른 입장을 요청하면 THE Quick_Join_Service SHALL 사용자의 보유 칩으로 입장 가능한 방 목록을 조회한다
2. WHEN 입장 가능한 방이 존재하면 THE Room_Matcher SHALL 빈 좌석이 있는 방 중 가장 적합한 방을 선택한다
3. WHEN 적합한 방이 선택되면 THE Quick_Join_Service SHALL 사용자를 해당 방의 빈 좌석에 자동 배정한다
4. WHEN 입장 가능한 방이 없으면 THE Quick_Join_Service SHALL 에러 코드 NO_AVAILABLE_ROOM을 반환한다
5. WHEN 사용자의 보유 칩이 최소 바이인보다 적으면 THE Quick_Join_Service SHALL 에러 코드 INSUFFICIENT_BALANCE를 반환한다

### Requirement 2: 방 매칭 알고리즘

**User Story:** As a 시스템, I want 사용자에게 최적의 방을 매칭하고 싶다, so that 사용자 경험과 게임 품질을 높일 수 있다.

#### Acceptance Criteria

1. THE Room_Matcher SHALL 다음 우선순위로 방을 선택한다: (1) 게임 진행 중인 방 > 대기 중인 방, (2) 플레이어 수가 많은 방 > 적은 방
2. WHEN 동일 조건의 방이 여러 개 있으면 THE Room_Matcher SHALL 무작위로 하나를 선택한다
3. THE Room_Matcher SHALL 사용자가 이미 참여 중인 방은 제외한다
4. WHEN 사용자가 블라인드 레벨을 지정하면 THE Room_Matcher SHALL 해당 블라인드 범위의 방만 검색한다

### Requirement 3: 자동 바이인

**User Story:** As a 플레이어, I want 빠른 입장 시 적절한 바이인 금액이 자동 설정되길 원한다, so that 추가 입력 없이 바로 게임에 참여할 수 있다.

#### Acceptance Criteria

1. WHEN 빠른 입장으로 방에 배정되면 THE Quick_Join_Service SHALL 기본 바이인 금액(최대 바이인의 50%)으로 자동 설정한다
2. IF 사용자의 보유 칩이 기본 바이인보다 적으면 THEN THE Quick_Join_Service SHALL 보유 칩 전액을 바이인으로 설정한다
3. IF 보유 칩이 최소 바이인보다 적으면 THEN THE Quick_Join_Service SHALL 입장을 거부하고 에러를 반환한다

### Requirement 4: 프론트엔드 통합

**User Story:** As a 플레이어, I want 로비에서 빠른 입장 버튼을 볼 수 있다, so that 쉽게 빠른 입장 기능을 사용할 수 있다.

#### Acceptance Criteria

1. WHEN 로비 페이지가 로드되면 THE Lobby_UI SHALL 빠른 입장 버튼을 표시한다
2. WHEN 빠른 입장 버튼을 클릭하면 THE Lobby_UI SHALL 로딩 상태를 표시하고 API를 호출한다
3. WHEN 빠른 입장이 성공하면 THE Lobby_UI SHALL 해당 테이블 페이지로 자동 이동한다
4. WHEN 빠른 입장이 실패하면 THE Lobby_UI SHALL 적절한 에러 메시지를 표시한다
