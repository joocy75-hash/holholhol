# Requirements Document

## Introduction

관리자 대시보드(Backoffice)는 온라인 홀덤 게임 시스템의 운영 및 관리를 위한 웹 기반 관리 도구입니다. 실시간 모니터링, 사용자 관리, 게임 관리, CS 지원 기능을 제공하여 운영팀이 효율적으로 서비스를 관리할 수 있도록 합니다.

**핵심 설계 원칙**: 관리자 대시보드는 메인 게임 애플리케이션과 완전히 분리된 독립 애플리케이션으로 구현됩니다. 별도의 프론트엔드, 백엔드, 배포 파이프라인을 가지며, 메인 시스템의 데이터베이스에 읽기 전용 또는 제한된 쓰기 접근만 허용합니다.

## Glossary

- **Admin_Dashboard**: 관리자 전용 웹 인터페이스
- **CCU**: Concurrent Connected Users, 동시 접속자 수
- **DAU**: Daily Active Users, 일일 활성 사용자 수
- **Operator**: 관리자 권한을 가진 운영자
- **Ban_System**: 사용자 제재 관리 시스템
- **Audit_Log**: 관리자 활동 기록 시스템
- **Hand_Replay**: 핸드 히스토리 재생 기능

## Requirements

### Requirement 1: 실시간 모니터링 대시보드

**User Story:** As an Operator, I want to monitor real-time server status and user metrics, so that I can quickly identify and respond to issues.

#### Acceptance Criteria

1. WHEN an Operator accesses the dashboard, THE Admin_Dashboard SHALL display current CCU count updated every 5 seconds
2. WHEN an Operator views the dashboard, THE Admin_Dashboard SHALL display DAU statistics with hourly breakdown
3. WHEN an Operator views the dashboard, THE Admin_Dashboard SHALL display active room count and player distribution
4. WHEN an Operator views the dashboard, THE Admin_Dashboard SHALL display server health metrics (CPU, memory, latency)
5. IF CCU exceeds a configured threshold, THEN THE Admin_Dashboard SHALL display a visual alert

### Requirement 2: 매출 및 통계 현황

**User Story:** As an Operator, I want to view revenue and game statistics, so that I can track business performance.

#### Acceptance Criteria

1. WHEN an Operator views revenue section, THE Admin_Dashboard SHALL display daily/weekly/monthly rake revenue
2. WHEN an Operator views statistics, THE Admin_Dashboard SHALL display total hands played per time period
3. WHEN an Operator views statistics, THE Admin_Dashboard SHALL display average pot size and player count per table
4. THE Admin_Dashboard SHALL provide date range filtering for all statistics

### Requirement 3: 서버 점검 및 공지 관리

**User Story:** As an Operator, I want to manage server maintenance and announcements, so that I can communicate with users and perform maintenance safely.

#### Acceptance Criteria

1. WHEN an Operator schedules maintenance, THE Admin_Dashboard SHALL allow setting start time and estimated duration
2. WHEN maintenance is scheduled, THE Admin_Dashboard SHALL broadcast warning messages to all connected users
3. WHEN an Operator creates an announcement, THE Admin_Dashboard SHALL allow targeting specific user groups or all users
4. WHEN an Operator activates maintenance mode, THE Admin_Dashboard SHALL prevent new room creation and gracefully close existing games
5. THE Audit_Log SHALL record all maintenance and announcement actions with Operator ID and timestamp

### Requirement 4: 방(Room) 관리

**User Story:** As an Operator, I want to manage game rooms, so that I can handle problematic situations and maintain service quality.

#### Acceptance Criteria

1. WHEN an Operator views room list, THE Admin_Dashboard SHALL display all active rooms with player count and status
2. WHEN an Operator selects a room, THE Admin_Dashboard SHALL display detailed room information including current hand state
3. WHEN an Operator force-closes a room, THE Admin_Dashboard SHALL refund all player chips and notify affected users
4. IF a room is force-closed, THEN THE Audit_Log SHALL record the reason and affected players
5. WHEN an Operator views a room, THE Admin_Dashboard SHALL allow sending system messages to that room

### Requirement 5: 사용자 관리 및 조회

**User Story:** As an Operator, I want to search and view user details, so that I can handle customer support requests.

#### Acceptance Criteria

1. WHEN an Operator searches for a user, THE Admin_Dashboard SHALL allow search by username, email, or user ID
2. WHEN an Operator views a user profile, THE Admin_Dashboard SHALL display account info, balance, and recent activity
3. WHEN an Operator views a user profile, THE Admin_Dashboard SHALL display login history with IP addresses
4. WHEN an Operator views a user profile, THE Admin_Dashboard SHALL display transaction history (deposits, withdrawals, game results)
5. THE Admin_Dashboard SHALL allow filtering users by registration date, last login, and balance range

### Requirement 6: 제재(Ban) 관리

**User Story:** As an Operator, I want to manage user bans and restrictions, so that I can enforce rules and maintain fair play.

#### Acceptance Criteria

1. WHEN an Operator bans a user, THE Ban_System SHALL allow setting ban type (temporary/permanent) and reason
2. WHEN a user is banned, THE Ban_System SHALL immediately disconnect the user and prevent login
3. WHEN an Operator views ban list, THE Admin_Dashboard SHALL display all active bans with expiration dates
4. WHEN an Operator lifts a ban, THE Ban_System SHALL restore user access and record the action
5. THE Audit_Log SHALL record all ban/unban actions with Operator ID, reason, and timestamp
6. WHEN an Operator applies a chat ban, THE Ban_System SHALL prevent the user from sending chat messages while allowing gameplay

### Requirement 7: 자산 수동 관리

**User Story:** As an Operator, I want to manually adjust user balances, so that I can handle compensation and corrections.

#### Acceptance Criteria

1. WHEN an Operator adjusts a user balance, THE Admin_Dashboard SHALL require a reason and approval workflow
2. WHEN a balance adjustment is made, THE Admin_Dashboard SHALL create a transaction record with Operator ID
3. IF adjustment amount exceeds a threshold, THEN THE Admin_Dashboard SHALL require supervisor approval
4. THE Audit_Log SHALL record all balance adjustments with full details
5. WHEN an Operator views adjustment history, THE Admin_Dashboard SHALL display all manual adjustments with filters

### Requirement 8: 핸드 리플레이

**User Story:** As an Operator, I want to replay hand histories, so that I can investigate disputes and suspicious activity.

#### Acceptance Criteria

1. WHEN an Operator searches for hands, THE Admin_Dashboard SHALL allow search by hand ID, user ID, or room ID
2. WHEN an Operator views a hand, THE Hand_Replay SHALL display step-by-step action sequence
3. WHEN an Operator views a hand, THE Hand_Replay SHALL show all player cards and community cards
4. WHEN an Operator views a hand, THE Hand_Replay SHALL display pot amounts and chip movements
5. THE Admin_Dashboard SHALL allow exporting hand history as text or JSON format

### Requirement 9: 부정 행위 의심 리스트

**User Story:** As an Operator, I want to view suspicious activity reports, so that I can investigate potential cheating.

#### Acceptance Criteria

1. WHEN the system detects suspicious patterns, THE Admin_Dashboard SHALL add users to a review queue
2. WHEN an Operator views suspicious users, THE Admin_Dashboard SHALL display flagged behaviors (same IP, chip dumping patterns)
3. WHEN an Operator reviews a case, THE Admin_Dashboard SHALL provide related hand histories and user connections
4. WHEN an Operator resolves a case, THE Admin_Dashboard SHALL allow marking as cleared or escalating to ban
5. THE Admin_Dashboard SHALL display statistics on flagged vs resolved cases

### Requirement 10: 관리자 인증 및 권한

**User Story:** As a System Administrator, I want to manage operator access and permissions, so that I can ensure secure access control.

#### Acceptance Criteria

1. WHEN an Operator logs in, THE Admin_Dashboard SHALL require two-factor authentication
2. THE Admin_Dashboard SHALL support role-based access control (viewer, operator, supervisor, admin)
3. WHEN an Operator performs sensitive actions, THE Admin_Dashboard SHALL require re-authentication
4. THE Audit_Log SHALL record all login attempts and permission changes
5. IF an Operator session is inactive for 30 minutes, THEN THE Admin_Dashboard SHALL automatically log out the session

### Requirement 11: 시스템 분리 아키텍처

**User Story:** As a System Administrator, I want the admin dashboard to be completely separated from the main application, so that admin operations don't affect game server performance and security is enhanced.

#### Acceptance Criteria

1. THE Admin_Dashboard SHALL be deployed as a standalone application with its own frontend and backend
2. THE Admin_Dashboard SHALL connect to the main database through a read-replica or restricted connection
3. THE Admin_Dashboard SHALL have its own authentication system separate from player authentication
4. WHEN the Admin_Dashboard performs write operations, THE Admin_API SHALL use dedicated admin endpoints on the main backend
5. THE Admin_Dashboard SHALL be deployable independently without affecting the main game application
6. THE Admin_Dashboard SHALL use a separate domain or subdomain (e.g., admin.holdem.com)
7. IF the main application is down, THEN THE Admin_Dashboard SHALL still display cached metrics and allow viewing historical data

### Requirement 12: USDT(TRC-20) 입금 관리

**User Story:** As an Operator, I want to manage USDT(TRC-20) deposits with KRW equivalent display, so that I can monitor and verify user deposits.

#### Acceptance Criteria

1. WHEN an Operator views deposit list, THE Admin_Dashboard SHALL display all pending and completed USDT deposits
2. WHEN displaying a deposit, THE Admin_Dashboard SHALL show USDT amount, KRW equivalent, transaction hash, and wallet address
3. THE Admin_Dashboard SHALL fetch real-time USDT/KRW exchange rate from external API
4. WHEN a deposit is detected on blockchain, THE Admin_Dashboard SHALL display confirmation count and status
5. WHEN an Operator views deposit details, THE Admin_Dashboard SHALL show TRC-20 transaction details from TRON network
6. THE Admin_Dashboard SHALL allow filtering deposits by status (pending, confirmed, failed), date range, and amount
7. IF a deposit requires manual review, THEN THE Admin_Dashboard SHALL allow Operator to approve or reject with reason

### Requirement 13: USDT(TRC-20) 출금 관리

**User Story:** As an Operator, I want to manage USDT(TRC-20) withdrawals with KRW equivalent display, so that I can process and verify user withdrawal requests.

#### Acceptance Criteria

1. WHEN an Operator views withdrawal queue, THE Admin_Dashboard SHALL display all pending withdrawal requests
2. WHEN displaying a withdrawal, THE Admin_Dashboard SHALL show USDT amount, KRW equivalent, destination wallet, and user info
3. WHEN an Operator approves a withdrawal, THE Admin_Dashboard SHALL initiate USDT transfer to user's TRC-20 wallet
4. THE Admin_Dashboard SHALL display estimated network fee in USDT and KRW equivalent
5. WHEN a withdrawal is processed, THE Admin_Dashboard SHALL record transaction hash and update status
6. IF withdrawal amount exceeds threshold, THEN THE Admin_Dashboard SHALL require supervisor approval
7. THE Audit_Log SHALL record all withdrawal approvals and rejections with Operator ID and reason
8. WHEN an Operator rejects a withdrawal, THE Admin_Dashboard SHALL refund the amount to user's game balance

### Requirement 14: 암호화폐 지갑 관리

**User Story:** As a System Administrator, I want to manage the system's USDT hot wallet, so that I can ensure sufficient funds for withdrawals and monitor wallet security.

#### Acceptance Criteria

1. WHEN an Operator views wallet status, THE Admin_Dashboard SHALL display hot wallet USDT balance and KRW equivalent
2. THE Admin_Dashboard SHALL display daily/weekly/monthly deposit and withdrawal totals in USDT and KRW
3. IF hot wallet balance falls below threshold, THEN THE Admin_Dashboard SHALL display alert to Operators
4. THE Admin_Dashboard SHALL display pending withdrawal total to show required reserve
5. WHEN viewing wallet transactions, THE Admin_Dashboard SHALL show all incoming and outgoing transactions
6. THE Admin_Dashboard SHALL NOT expose private keys or seed phrases in the interface
7. THE Audit_Log SHALL record all wallet-related administrative actions

### Requirement 15: 환율 및 거래 통계

**User Story:** As an Operator, I want to view exchange rate history and transaction statistics, so that I can analyze crypto transaction patterns.

#### Acceptance Criteria

1. THE Admin_Dashboard SHALL display current USDT/KRW exchange rate with last update timestamp
2. WHEN an Operator views exchange rate history, THE Admin_Dashboard SHALL show rate changes over time
3. THE Admin_Dashboard SHALL display total deposits and withdrawals by day/week/month in both USDT and KRW
4. THE Admin_Dashboard SHALL display average transaction size and transaction count statistics
5. IF exchange rate API is unavailable, THEN THE Admin_Dashboard SHALL use cached rate and display warning
