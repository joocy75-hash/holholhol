# Requirements Document

## Introduction

타임 뱅크(Time Bank)는 플레이어가 턴 제한 시간이 부족할 때 추가 시간을 요청할 수 있는 기능입니다. 경쟁 포커 게임의 표준 기능으로, 중요한 결정에 더 많은 시간이 필요할 때 사용합니다.

## Glossary

- **Time_Bank**: 플레이어가 보유한 추가 시간 저장소
- **Time_Bank_Request**: 추가 시간 사용 요청
- **Turn_Timer**: 현재 턴의 남은 시간을 관리하는 타이머
- **Auto_Fold**: 시간 초과 시 자동 폴드 처리

## Requirements

### Requirement 1: 타임 뱅크 초기화

**User Story:** As a 플레이어, I want 게임 시작 시 타임 뱅크를 부여받고 싶다, so that 중요한 결정에 추가 시간을 사용할 수 있다.

#### Acceptance Criteria

1. WHEN 새로운 핸드가 시작되면 THE Time_Bank SHALL 각 플레이어에게 기본 타임 뱅크 횟수(3회)를 부여한다
2. THE Time_Bank SHALL 플레이어당 최대 타임 뱅크 횟수를 설정값으로 제한한다
3. WHEN 플레이어가 테이블에 앉으면 THE Time_Bank SHALL 해당 플레이어의 타임 뱅크를 초기화한다

### Requirement 2: 타임 뱅크 사용

**User Story:** As a 플레이어, I want 턴 시간이 부족할 때 타임 뱅크를 사용하고 싶다, so that 더 신중한 결정을 내릴 수 있다.

#### Acceptance Criteria

1. WHEN 플레이어가 타임 뱅크를 요청하면 THE Turn_Timer SHALL 추가 시간(30초)을 현재 턴에 더한다
2. WHEN 타임 뱅크가 사용되면 THE Time_Bank SHALL 해당 플레이어의 남은 타임 뱅크 횟수를 1 감소시킨다
3. IF 플레이어의 타임 뱅크 횟수가 0이면 THEN THE Time_Bank_Request SHALL 거부되고 에러를 반환한다
4. IF 현재 플레이어의 턴이 아니면 THEN THE Time_Bank_Request SHALL 거부된다
5. WHEN 타임 뱅크가 성공적으로 사용되면 THE System SHALL 모든 클라이언트에게 타임 뱅크 사용을 브로드캐스트한다

### Requirement 3: 타임 뱅크 UI 표시

**User Story:** As a 플레이어, I want 남은 타임 뱅크 횟수를 볼 수 있다, so that 언제 타임 뱅크를 사용할지 계획할 수 있다.

#### Acceptance Criteria

1. THE UI SHALL 각 플레이어의 남은 타임 뱅크 횟수를 표시한다
2. WHEN 플레이어의 턴이면 THE UI SHALL 타임 뱅크 사용 버튼을 활성화한다
3. WHEN 타임 뱅크 횟수가 0이면 THE UI SHALL 타임 뱅크 버튼을 비활성화한다
4. WHEN 타임 뱅크가 사용되면 THE UI SHALL 추가된 시간을 타이머에 반영한다

### Requirement 4: 타임 뱅크 자동 사용 (선택)

**User Story:** As a 플레이어, I want 시간이 거의 다 되었을 때 자동으로 타임 뱅크가 사용되길 원한다, so that 실수로 타임아웃되는 것을 방지할 수 있다.

#### Acceptance Criteria

1. WHEN 턴 시간이 5초 미만이고 타임 뱅크가 남아있으면 THE System SHALL 자동 타임 뱅크 사용 옵션을 제공한다
2. IF 자동 타임 뱅크가 활성화되어 있으면 THEN THE System SHALL 시간 초과 전에 자동으로 타임 뱅크를 사용한다
