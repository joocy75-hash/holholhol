# 홀덤1등 프로젝트 - 마스터 작업 계획서

**작성일**: 2026-01-17
**버전**: 1.0
**목적**: 여러 계정에서 작업 중단/재개 시 원활한 작업 진행을 위한 종합 계획서

---

## 📋 목차

1. [프로젝트 현황 요약](#프로젝트-현황-요약)
2. [작업 우선순위 및 로드맵](#작업-우선순위-및-로드맵)
3. [작업 규칙 및 지침](#작업-규칙-및-지침)
4. [Phase별 상세 작업 계획](#phase별-상세-작업-계획)
5. [Skills 파일 관리](#skills-파일-관리)
6. [중단 대비 체크포인트](#중단-대비-체크포인트)
7. [테스트 명령어 참조](#테스트-명령어-참조)

---

## 📊 프로젝트 현황 요약

### 전체 완성도
| 영역 | 완료율 | 상태 |
|------|--------|------|
| 핵심 게임 로직 | 100% | ✅ 완료 |
| 사용자 관리 | 60% | 🟡 진행중 |
| 방/테이블 관리 | 93% | 🟡 진행중 |
| 인게임 기능 | 60% | 🟡 진행중 |
| 네트워킹 | 100% | ✅ 완료 |
| 데이터베이스 | 85% | 🟡 진행중 |
| UI/UX | 85% | 🟡 진행중 |
| 보안 | 100% | ✅ 완료 |
| Backoffice | 100% | ✅ 완료 |
| **전체** | **87%** | 🟡 진행중 |

### 주요 완료 작업
- ✅ TON/USDT 입금 시스템 (100% 완료)
- ✅ 부정 행위 탐지 시스템 통합 (100% 완료)
- ✅ 관리자 대시보드 (95% 완료)
- ✅ 백엔드 보안 강화 Phase 1-2 (100% 완료)
- ✅ 버그 수정 작업 (100% 완료)
- ✅ E2E 테스트 인프라 (100% 완료)
- ✅ Framer Motion 마이그레이션 (100% 완료)
- ✅ 운영 도구 Phase 5 (CCU/DAU/MAU 모니터링, 매출 대시보드) (100% 완료)

### 진행 중인 작업
- ✅ 모든 Phase 완료! (Phase 2~5)

---

## 🎯 작업 우선순위 및 로드맵

### 우선순위 분류
```
P0 (긴급) - 즉시 처리 필요
P1 (높음) - 1주일 내 처리
P2 (중간) - 2주일 내 처리
P3 (낮음) - 1개월 내 처리
P4 (선택) - 여유 시 처리
```

### 작업 로드맵 (4주 계획)

#### Week 1: 보안 및 부정 방지 (P0-P1)
- [x] Phase 2.1: 칩 밀어주기 탐지 게임 서버 연동 ✅
- [x] Phase 2.2: 봇 탐지 시스템 게임 서버 연동 ✅
- [x] Phase 2.3: 이상 행동 탐지 연동 ✅
- [x] Phase 2.4: 자동 밴 시스템 연동 ✅
- [x] Phase 2.5: 핸드 히스토리 DB 저장 ✅

#### Week 2: 관리자 기능 (P1-P2)
- [x] Phase 3.1: 서버 점검 모드 제어 ✅
- [x] Phase 3.2: 공지사항 발송 시스템 ✅
- [x] Phase 3.3: 방 강제 종료 기능 ✅
- [x] Phase 3.4: 핸드 리플레이 기능 ✅
- [x] Phase 3.5: 자산 수동 지급/회수 ✅
- [x] Phase 3.6: 유저 상세 로그 조회 ✅
- [x] Phase 3.7: 부정 사용자 의심 리스트 ✅

#### Week 3: 안정성 개선 (P2-P3)
- [x] Phase 4.1: 대기열(Waitlist) 관리 ✅
- [x] Phase 4.2: 관전자/플레이어 그룹 분리 전송 ✅
- [x] Phase 4.3: 중간 입장 동기화 (Snapshot) ✅
- [x] Phase 4.4: WebSocket 하트비트 구현 ✅
- [x] Phase 4.5: 메모리 정리 최적화 ✅

#### Week 4: 운영 도구 (P3-P4)
- [x] Phase 5.1: CCU 실시간 모니터링 ✅
- [x] Phase 5.2: DAU/MAU 통계 ✅
- [x] Phase 5.3: 매출 현황 대시보드 ✅

---


## 🔴 작업 규칙 및 지침

### 1. 단계별 작업 원칙
- **한 번에 하나의 Step만 작업** - 토큰 한계로 인해 한 단계 완료 후 종료
- **작업 완료 시 반드시 검증 테스트 실행** - 테스트 통과 확인 후 완료 처리
- **전문 서브에이전트 사용** - 각 작업에 맞는 에이전트 활용
- **완료 체크 필수** - 각 단계 완료 시 `[ ]` → `[x]`로 변경
- **작업 중단 시 현재 단계 기록** - 다음 세션에서 이어서 작업

### 2. 서브에이전트 사용 원칙
| 에이전트 | 용도 | 사용 시점 |
|----------|------|----------|
| `context-gatherer` | 코드 분석, 관련 파일 파악 | 복잡한 코드 작성 전 |
| `general-task-execution` | 멀티 파일 작업, 복잡한 구현 | 여러 파일 동시 수정 시 |
| `spec-task-execution` | Spec 작업 실행 | Spec 기반 작업 시 |

### 3. 검증 테스트 원칙
```bash
# Backend 테스트
cd backend && pytest tests/ -v
cd admin-backend && pytest tests/ -v

# Frontend 빌드
cd frontend && npm run build
cd admin-frontend && npm run build

# 서버 실행 확인
cd backend && python -c "from app.main import app; print('OK')"
cd admin-backend && python -c "from app.main import app; print('OK')"
```

### 4. 중단 대비 원칙
- **각 Step 완료 시 즉시 문서 업데이트**
  - 해당 Spec의 `WORK_PROGRESS.md` 업데이트
  - 이 `MASTER_WORK_PLAN.md` 업데이트
- **작업 중단 시 현재 진행 상태 기록**
  - 완료된 서브태스크 체크
  - 수정한 파일 목록 기록
  - 발생한 에러 기록
- **재개 시 확인 사항**
  - 마지막 완료 Step 확인
  - 미완료 작업 확인
  - 테스트 실행하여 현재 상태 검증

### 5. 작업 로그 기록
- **작업 시작 시**: 날짜, 작업 내용, 담당 계정 기록
- **작업 완료 시**: 완료일, 검증 결과 기록
- **작업 중단 시**: 중단 사유, 다음 작업 내용 기록

---

## 📝 Phase별 상세 작업 계획

### Phase 2: 부정 방지 시스템 연동 (🟠 우선)

#### 2.1 칩 밀어주기 탐지 게임 서버 연동
**우선순위**: 🟠 P1
**예상 시간**: 60분
**관련 파일**: 
- `backend/app/ws/handlers/action.py`
- `admin-backend/app/services/chip_dumping_detector.py`

**작업 내용**:
- [x] **2.1.1** 게임 서버에서 핸드 완료 시 이벤트 발행 구조 설계
  - Redis pub/sub 채널 정의 (`fraud:hand_completed`)
  - 핸드 결과 데이터 구조 정의
- [x] **2.1.2** Redis pub/sub으로 핸드 결과 전송
  - `action.py`에서 핸드 완료 시 이벤트 발행
  - 필요 데이터: 플레이어 ID, 베팅 패턴, 승패 결과
- [x] **2.1.3** admin-backend에서 핸드 결과 수신 및 분석
  - `FraudEventConsumer`에서 이벤트 수신
  - `ChipDumpingDetector.detect_one_way_chip_flow()` 호출
- [x] **2.1.4** 의심 패턴 발견 시 알림 발송
  - `AutoBanService` 연동
  - 관리자 대시보드 알림 (`_flag_suspicious_activity()`)
- [x] **2.1.5** 테스트 실행
  ```bash
  cd backend && pytest tests/ws/ -v -k fraud
  cd admin-backend && pytest tests/services/ -v -k chip_dumping
  ```
- [x] **2.1.6** 수정 검증 완료

**완료 확인**:
- [x] **Step 2.1 완료** (날짜: 2026-01-17, 검증: 75 tests passed)

---

#### 2.2 봇 탐지 시스템 게임 서버 연동
**우선순위**: 🟠 P1
**예상 시간**: 45분
**관련 파일**:
- `backend/app/ws/handlers/action.py`
- `backend/app/utils/redis_client.py`
- `admin-backend/app/services/bot_detector.py`
- `admin-backend/app/services/fraud_event_consumer.py`

**작업 내용**:
- [x] **2.2.1** 플레이어 액션 타이밍 데이터 수집
  - 액션 시간, 응답 시간 기록
  - Redis에 플레이어별 타이밍 데이터 저장 (`game:turn:{room_id}:{user_id}`)
- [x] **2.2.2** 액션 패턴 데이터 Redis 저장
  - 키: `stats:response_times:{user_id}` (SORTED SET)
  - 키: `stats:action_pattern:{user_id}` (HASH)
  - 데이터: 액션 타입, 빈도, 타이밍
- [x] **2.2.3** admin-backend에서 패턴 분석
  - `BotDetector.run_realtime_bot_detection()` 추가
  - `BotDetector.analyze_from_redis()` 추가
  - 실시간 버퍼 + Redis 기반 분석 지원
- [x] **2.2.4** 봇 의심 시 자동 플래그 처리
  - `FraudEventConsumer._analyze_bot_behavior()` 개선
  - `AutoBanService` 연동
  - 심각도 기반 알림 (high/medium/low)
- [x] **2.2.5** 테스트 실행
  ```bash
  cd backend && pytest tests/ws/ -v -k action
  cd admin-backend && pytest tests/services/ -v -k bot_detector
  ```
- [x] **2.2.6** 수정 검증 완료

**완료 확인**:
- [x] **Step 2.2 완료** (날짜: 2026-01-17, 검증: 57 tests passed)

---

#### 2.3 이상 행동 탐지 연동
**우선순위**: 🟠 P1
**예상 시간**: 45분
**관련 파일**:
- `admin-backend/app/services/anomaly_detector.py`
- `admin-backend/app/services/fraud_event_consumer.py`
- `backend/app/main.py`
- `backend/app/ws/handlers/table.py`
- `backend/app/ws/handlers/action.py`

**작업 내용**:
- [x] **2.3.1** 게임 서버에서 플레이어 통계 주기적 전송
  - Redis pub/sub 채널: `fraud:player_stats`
  - 통계 데이터: 승률, 평균 베팅, 플레이 시간
  - `main.py`에서 `FraudEventPublisher`, `PlayerSessionTracker` 초기화
  - `table.py`에서 착석/퇴장 시 세션 시작/종료
  - `action.py`에서 핸드 완료 시 세션 통계 업데이트
- [x] **2.3.2** 이상 패턴 실시간 분석
  - `AnomalyDetector.run_full_anomaly_detection()` 호출
  - Z-score 기반 이상 탐지
  - `FraudEventConsumer._run_anomaly_detection()` 추가
  - 세션 기반 탐지 + DB 기반 종합 분석 이중 체계
- [x] **2.3.3** 알림 시스템 연동
  - 이상 탐지 시 `TelegramNotifier` 호출
  - 관리자 대시보드 알림
  - `_flag_suspicious_activity()`에서 `AuditService` + `TelegramNotifier` 연동
  - medium/high 심각도 모두 알림 전송
- [x] **2.3.4** 테스트 실행
  ```bash
  cd backend && pytest tests/services/test_player_session_tracker.py -v  # 18 passed
  cd admin-backend && pytest tests/services/test_fraud_event_consumer.py -v  # 16 passed
  ```
- [x] **2.3.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 2.3 완료** (날짜: 2026-01-17, 검증: 34 tests passed)

---

#### 2.4 자동 밴 시스템 연동
**우선순위**: 🟠 P1
**예상 시간**: 30분
**관련 파일**:
- `admin-backend/app/services/auto_ban.py`
- `admin-backend/app/services/fraud_event_consumer.py`
- `admin-backend/app/config.py`

**작업 내용**:
- [x] **2.4.1** 탐지 결과 → 자동 밴 트리거 연결
  - `AutoBanService.process_detection()` 메인 엔트리 포인트 구현
  - `FraudEventConsumer._flag_suspicious_activity()`에서 `process_detection()` 호출
  - `BanService` 연동으로 실제 제재 적용
  - `_apply_auto_ban()`, `_get_user_detection_count()` 구현
- [x] **2.4.2** 밴 임계값 설정 (config.py)
  - `auto_ban_threshold_chip_dumping: int = 3`
  - `auto_ban_threshold_bot: int = 5`
  - `auto_ban_threshold_anomaly: int = 4`
  - `auto_ban_temp_duration_hours: int = 24`
  - `auto_ban_enabled: bool = True`
  - `auto_ban_high_severity_immediate: bool = True`
- [x] **2.4.3** 관리자 알림 연동
  - 자동 밴 발생 시 `TelegramNotifier` 호출 (`_notify_auto_ban_applied()`)
  - 감사 로그 기록 (`_log_auto_ban_action()`)
  - 만료된 밴 자동 해제 (`check_and_lift_expired_bans()`)
- [x] **2.4.4** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/services/test_auto_ban.py -v  # 39 passed
  cd admin-backend && pytest tests/services/test_fraud_event_consumer.py -v  # 16 passed
  cd admin-backend && pytest tests/ -v  # 474 passed
  ```
- [x] **2.4.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 2.4 완료** (날짜: 2026-01-17, 검증: 474 tests passed)

---

#### 2.5 핸드 히스토리 DB 저장
**우선순위**: 🟠 P1
**예상 시간**: 60분
**관련 파일**:
- `backend/app/services/hand_history.py` (이미 구현됨)
- `backend/app/models/hand.py` (이미 구현됨)
- `backend/app/ws/handlers/action.py` (DB 저장 연결)
- `backend/app/api/hands.py` (신규 - 핸드 조회 API)
- `backend/app/schemas/responses.py` (핸드 응답 스키마 추가)

**작업 내용**:
- [x] **2.5.1** HandHistory 모델 생성 (이미 완료)
- [x] **2.5.2** 핸드 완료 시 DB 저장 로직 연결
  - `ActionHandler._publish_hand_completed_event()`에서 `HandHistoryService.save_hand_result()` 호출
  - graceful degradation: DB 저장 실패 시 게임 진행에 영향 없음
- [x] **2.5.3** 핸드 조회 API 추가
  - `GET /api/v1/hands/me` - 현재 사용자의 핸드 히스토리 (페이지네이션)
  - `GET /api/v1/hands/{hand_id}` - 핸드 상세 조회 (리플레이용)
  - 스키마 추가: `HandSummaryResponse`, `HandDetailResponse`, `HandHistoryListResponse`
  - 보안: 사용자가 참가한 핸드만 조회 가능
- [x] **2.5.4** Alembic 마이그레이션 확인
  - `hand_participants` 테이블 마이그레이션 이미 존재
  - merge head (1723deb5781e) 확인
- [x] **2.5.5** 테스트 실행
  ```bash
  cd backend && pytest tests/engine/ -v  # 106 passed
  python -c "from app.api.hands import router; print('OK')"  # Import 확인
  ```
- [x] **2.5.6** 수정 검증 완료

**완료 확인**:
- [x] **Step 2.5 완료** (날짜: 2026-01-17, 검증: 106 tests passed, API import 정상)

---

### Phase 3: 관리자 기능 (🟡 일반)

#### 3.1 서버 점검 모드 제어
**우선순위**: 🟡 P2
**예상 시간**: 45분
**관련 파일**:
- `admin-backend/app/api/system.py` (신규)
- `admin-backend/app/services/maintenance_service.py` (신규)
- `backend/app/middleware/maintenance.py` (신규)

**작업 내용**:
- [x] **3.1.1** 점검 모드 상태 저장 (Redis)
  - 키: `system:maintenance_mode`
  - 값: `{"enabled": true, "message": "점검 중", "start_time": "...", "end_time": "...", "started_by": "..."}`
  - `MaintenanceService` 클래스 구현
- [x] **3.1.2** 점검 모드 ON/OFF API 추가
  - `POST /api/system/maintenance` - 점검 모드 설정 (supervisor 이상 권한)
  - `GET /api/system/maintenance` - 점검 모드 조회 (viewer 이상 권한)
  - `GET /api/system/health` - 시스템 상태 확인 (인증 불필요)
- [x] **3.1.3** 게임 서버에서 점검 모드 확인 미들웨어
  - `backend/app/middleware/maintenance.py` 생성
  - 점검 중 신규 HTTP 요청 차단 (503 응답, Retry-After: 300)
  - 예외 경로: /health, /metrics, /docs 등은 허용
  - fail-open 전략: Redis 오류 시 요청 허용
- [x] **3.1.4** 점검 중 신규 입장 차단
  - WebSocket 연결 수락 전 점검 모드 확인
  - close code 1013 (Try Again Later) 사용
  - 기존 연결은 유지 (진행 중인 게임 완료 허용)
- [x] **3.1.5** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/services/test_maintenance_service.py -v  # 13 passed
  cd backend && pytest tests/middleware/test_maintenance.py -v  # 16 passed
  ```
- [x] **3.1.6** 수정 검증 완료

**완료 확인**:
- [x] **Step 3.1 완료** (날짜: 2026-01-17, 검증: 29 tests passed + 487 admin-backend passed)

---


#### 3.2 공지사항 발송 시스템
**우선순위**: 🟡 P2
**예상 시간**: 45분
**관련 파일**:
- `admin-backend/app/api/announcements.py` (신규)
- `admin-backend/app/services/announcement_service.py` (신규)
- `admin-backend/app/models/announcement.py` (확장)
- `backend/app/ws/events.py` (ANNOUNCEMENT 이벤트 추가)
- `frontend/src/components/announcements/` (신규)
- `frontend/src/stores/announcement.ts` (신규)

**작업 내용**:
- [x] **3.2.1** Announcement 모델 확장
  - 필드: id, title, content, announcement_type, priority, target, target_room_id, start_time, end_time, scheduled_at, broadcasted_at, broadcast_count, created_by
  - Enum 추가: AnnouncementType (notice, event, maintenance, urgent)
  - Enum 추가: AnnouncementPriority (low, normal, high, critical)
- [x] **3.2.2** 공지 CRUD API 추가
  - `POST /api/announcements` - 공지 생성 (supervisor 이상)
  - `GET /api/announcements` - 공지 목록 (페이지네이션, 필터링)
  - `GET /api/announcements/active` - 활성 공지 목록
  - `GET /api/announcements/{id}` - 공지 상세
  - `PUT /api/announcements/{id}` - 공지 수정
  - `DELETE /api/announcements/{id}` - 공지 삭제
  - `POST /api/announcements/{id}/broadcast` - 브로드캐스트 발송
  - `GET /api/announcements/types/list` - 유형 목록
- [x] **3.2.3** WebSocket으로 실시간 공지 브로드캐스트
  - 이벤트 타입: `ANNOUNCEMENT` (backend events.py에 추가)
  - Redis pub/sub으로 다중 인스턴스 지원
  - 대상별 채널 분기 (lobby, table:{room_id})
- [x] **3.2.4** 프론트엔드 공지 표시 컴포넌트
  - AnnouncementModal: 우선순위별 스타일 (critical은 수동 닫기)
  - AnnouncementBadge: 읽지 않은 공지 배지
  - AnnouncementProvider: WebSocket 리스너 + 모달 렌더링
  - useAnnouncementStore: Zustand 상태 관리
- [x] **3.2.5** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/services/test_announcement_service.py tests/api/test_announcements.py -v
  # 32 tests passed
  ```
- [x] **3.2.6** 수정 검증 완료

**완료 확인**:
- [x] **Step 3.2 완료** (날짜: 2026-01-17, 검증: 32 tests passed + frontend 빌드 성공)

---

#### 3.3 방 강제 종료 기능
**우선순위**: 🟡 P2
**예상 시간**: 30분
**관련 파일**:
- `admin-backend/app/api/rooms.py`
- `backend/app/api/admin.py` (Game Backend Internal Admin API)
- `backend/app/services/room.py` (force_close_room 로직)

**작업 내용**:
- [x] **3.3.1** 방 강제 종료 API 추가
  - Admin Backend: `POST /api/rooms/{room_id}/force-close` - supervisor 이상 권한 필요
  - Game Backend: `POST /api/v1/internal/admin/rooms/{room_id}/force-close` - 이미 구현됨
  - httpx를 통한 Admin → Game Backend 통신
- [x] **3.3.2** 진행 중인 핸드 강제 종료 로직
  - GameManager에서 최신 스택 정보 조회
  - GameManager 테이블 제거 및 DB 업데이트
  - `RoomService.force_close_room()` 활용
- [x] **3.3.3** 플레이어 칩 환불 처리
  - 각 플레이어의 현재 스택을 balance에 반환
  - RefundInfo 응답: user_id, nickname, amount, seat
  - 트랜잭션 로그 자동 기록
- [x] **3.3.4** WebSocket 브로드캐스트
  - `ROOM_FORCE_CLOSED` 이벤트로 모든 플레이어에게 알림
  - Redis pub/sub: `ws:pubsub:table:{room_id}` 채널 사용
- [x] **3.3.5** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/api/test_rooms.py -v  # 19 passed
  ```
- [x] **3.3.6** 수정 검증 완료

**완료 확인**:
- [x] **Step 3.3 완료** (날짜: 2026-01-17, 검증: 19 tests passed)

---

#### 3.4 핸드 리플레이 기능
**우선순위**: 🟡 P2
**예상 시간**: 60분
**관련 파일**:
- `admin-backend/app/api/hands.py`
- `admin-frontend/src/app/(dashboard)/hands/page.tsx`
- `admin-frontend/src/app/(dashboard)/hands/[id]/page.tsx`
- `admin-frontend/src/components/hands/`

**작업 내용**:
- [x] **3.4.1** 핸드 상세 조회 API 추가
  - `GET /api/hands` - 핸드 검색/목록 (필터: hand_id, user_id, table_id)
  - `GET /api/hands/{hand_id}` - 핸드 상세 조회 (타임라인, 참가자, 결과)
  - `GET /api/hands/{hand_id}/export` - JSON/텍스트 내보내기
- [x] **3.4.2** 액션별 타임라인 데이터 구조화
  - TimelineAction 모델: seqNo, eventType, phase, amount, cards, timestamp
  - 페이즈 자동 추출: preflop, flop, turn, river, showdown
  - 참가자별 순수익 계산
- [x] **3.4.3** 관리자 프론트엔드 리플레이 뷰어
  - `hands-api.ts` - 핸드 API 클라이언트
  - `hands/page.tsx` - 핸드 검색/목록 페이지
  - `hands/[id]/page.tsx` - 핸드 상세 리플레이 페이지
  - `CardDisplay.tsx` - 포커 카드 표시 컴포넌트
  - `HandReplayTimeline.tsx` - 타임라인 재생 컴포넌트
  - 기능: 재생/일시정지, 이전/다음 스텝, 슬라이더, 내보내기
- [x] **3.4.4** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/api/test_hands.py -v  # 19 passed
  cd admin-frontend && npm run build  # 성공
  ```
- [x] **3.4.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 3.4 완료** (날짜: 2026-01-17, 검증: 19 tests passed + frontend 빌드 성공)

---

#### 3.5 자산 수동 지급/회수
**우선순위**: 🟡 P2
**예상 시간**: 45분
**관련 파일**:
- `admin-backend/app/api/users.py`
- `admin-backend/app/services/user_service.py`

**작업 내용**:
- [x] **3.5.1** 칩 지급 API 추가 (관리자 권한)
  - `POST /api/users/{user_id}/credit` - 칩 지급
  - 파라미터: amount, reason
  - supervisor 이상 권한 필요
- [x] **3.5.2** 칩 회수 API 추가 (관리자 권한)
  - `POST /api/users/{user_id}/debit` - 칩 회수
  - 파라미터: amount, reason
  - 잔액 부족 시 에러 반환
- [x] **3.5.3** 감사 로그 자동 기록
  - `AuditService.log_action()` 호출
  - 액션 타입: credit_chips, debit_chips
  - 상세 정보: 금액, 사유, 전후 잔액, 트랜잭션 ID
- [x] **3.5.4** 트랜잭션 무결성 보장
  - `FOR UPDATE` 락으로 동시성 보호
  - 잔액 부족 시 `InsufficientBalanceError` 발생
  - 실패 시 자동 롤백
- [x] **3.5.5** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/services/test_user_service.py tests/api/test_users.py -v
  # 49 tests passed
  ```
- [x] **3.5.6** 수정 검증 완료

**완료 확인**:
- [x] **Step 3.5 완료** (날짜: 2026-01-17, 검증: 49 tests passed)

---

#### 3.6 유저 상세 로그 조회
**우선순위**: 🟡 P2
**예상 시간**: 30분
**관련 파일**:
- `admin-backend/app/api/users.py`
- `admin-backend/app/services/user_service.py`

**작업 내용**:
- [x] **3.6.1** 유저 활동 로그 조회 API 추가
  - `GET /api/users/{user_id}/activity` - 통합 활동 로그 조회
  - 필터: activity_type (login, transaction, hand), start_date, end_date
- [x] **3.6.2** 로그인 기록, 게임 기록, 입출금 기록 통합
  - 로그인 기록: IP, 시간, 기기, 성공/실패
  - 게임 기록: room_id, hand_id, 카드, 손익
  - 입출금 기록: 금액, 설명, 타입
  - UNION ALL로 통합하여 시간순 정렬
- [x] **3.6.3** 필터링 및 페이지네이션
  - 날짜 범위 필터 (start_date, end_date)
  - 로그 타입 필터 (activity_type)
  - 페이지네이션 (page, page_size)
  - total_pages 계산 포함
- [x] **3.6.4** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/services/test_user_service.py tests/api/test_users.py -v
  # 60 passed
  ```
- [x] **3.6.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 3.6 완료** (날짜: 2026-01-17, 검증: 60 tests passed)

---

#### 3.7 부정 사용자 의심 리스트
**우선순위**: 🟡 P2
**예상 시간**: 30분
**관련 파일**:
- `admin-backend/app/api/suspicious.py` (신규)
- `admin-backend/app/services/suspicious_user_service.py` (신규)

**작업 내용**:
- [x] **3.7.1** 의심 사용자 리스트 API 추가
  - `GET /api/suspicious` - 의심 사용자 목록 (필터링, 정렬, 페이지네이션)
  - `GET /api/suspicious/summary` - 요약 통계
  - `GET /api/suspicious/users/{user_id}` - 사용자 상세
  - `GET /api/suspicious/activities/{id}` - 활동 상세
  - `PATCH /api/suspicious/activities/{id}/review` - 검토 상태 업데이트
  - `GET /api/suspicious/detection-types` - 탐지 유형 목록
- [x] **3.7.2** 탐지 시스템 결과 통합 뷰
  - ChipDumping, Bot, Anomaly 탐지 결과 통합
  - 의심 점수 계산 (탐지 유형 가중치 * 심각도 배수)
  - PostgreSQL unnest()로 사용자별 집계
- [x] **3.7.3** 관리자 검토 상태 관리
  - 상태: pending, reviewing, confirmed, dismissed
  - 검토 결과 기록 (reviewed_by, reviewed_at, review_notes)
  - 감사 로그 자동 기록
- [x] **3.7.4** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/api/test_suspicious.py -v  # 14 passed
  ```
- [x] **3.7.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 3.7 완료** (날짜: 2026-01-17, 검증: 14 tests passed)

---

### Phase 4: 안정성 개선 (🟢 낮음)

#### 4.1 대기열(Waitlist) 관리
**우선순위**: 🟢 P3
**예상 시간**: 45분
**관련 파일**:
- `backend/app/services/room.py`
- `backend/app/utils/redis_client.py`
- `backend/app/ws/events.py`
- `backend/app/ws/handlers/table.py`
- `backend/app/api/rooms.py`

**작업 내용**:
- [x] **4.1.1** 대기열 데이터 구조 (Redis)
  - 키: `waitlist:{room_id}` (ZSET)
  - 키: `waitlist:detail:{room_id}:{user_id}` (JSON)
  - RedisService에 대기열 관련 메서드 8개 추가
- [x] **4.1.2** 대기열 등록/취소 API
  - `POST /api/rooms/{room_id}/waitlist` - 대기열 등록
  - `DELETE /api/rooms/{room_id}/waitlist` - 대기열 취소
  - `GET /api/rooms/{room_id}/waitlist` - 대기열 조회
  - RoomService에 waitlist 메서드 5개 추가
- [x] **4.1.3** 자리 비면 자동 입장 로직
  - EventType 6개 추가 (WAITLIST_JOIN_REQUEST 등)
  - TableHandler에 대기열 핸들러 3개 추가
  - 퇴장 시 `_process_waitlist_on_leave()` 자동 호출
  - WAITLIST_SEAT_READY 이벤트로 대기자에게 알림
- [x] **4.1.4** 테스트 실행
  ```bash
  cd backend && pytest tests/services/test_waitlist.py -v  # 20 passed
  ```
- [x] **4.1.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 4.1 완료** (날짜: 2026-01-17, 검증: 20 tests passed)

---

#### 4.2 관전자/플레이어 그룹 분리 전송
**우선순위**: 🟢 P3
**예상 시간**: 30분
**관련 파일**:
- `backend/app/ws/manager.py`

**작업 내용**:
- [x] **4.2.1** 채널 그룹 분리 (players, spectators)
  - `table:{room_id}:players` - 플레이어 전용
  - `table:{room_id}:spectators` - 관전자 전용
  - `subscribe_as_player()`, `subscribe_as_spectator()` 메서드 구현
  - `upgrade_to_player()`, `downgrade_to_spectator()` 전환 메서드 구현
- [x] **4.2.2** 그룹별 메시지 전송 최적화
  - `broadcast_to_players()` - 플레이어 전용 메시지
  - `broadcast_to_spectators()` - 관전자 전용 메시지
  - `broadcast_to_table()` - 전체 구독자 (공개 데이터)
  - 홀 카드는 `send_to_user()`로 개별 전송 (기존 구현)
- [x] **4.2.3** 테스트 실행
  ```bash
  cd backend && pytest tests/ws/test_group_subscription.py -v  # 17 passed
  ```
- [x] **4.2.4** 수정 검증 완료

**완료 확인**:
- [x] **Step 4.2 완료** (날짜: 2026-01-17, 검증: 17 tests passed)

---

#### 4.3 중간 입장 동기화 (Snapshot)
**우선순위**: 🟢 P3
**예상 시간**: 45분
**관련 파일**:
- `backend/app/ws/handlers/table.py` (_build_table_snapshot 메서드)
- `frontend/src/types/websocket.ts` (타입 정의)

**작업 내용**:
- [x] **4.3.1** 테이블 스냅샷 생성 로직 보강
  - 현재 게임 상태 전체 직렬화 (기존)
  - 플레이어 목록, 팟, 커뮤니티 카드, 현재 턴 (기존)
  - `actionHistory`: 현재 핸드의 베팅 액션 목록 추가
  - `timeBankRemaining`: 각 좌석에 타임 뱅크 남은 횟수 추가
  - `turnInfo`: 현재 턴 시작/마감 시간, 남은 시간 정보 추가
- [x] **4.3.2** 중간 입장 시 스냅샷 전송
  - `TABLE_SNAPSHOT` 이벤트 발송 (기존 _handle_subscribe)
  - 관전자/플레이어 모드 자동 감지
  - 관전자는 홀 카드 비공개, 플레이어는 자신의 홀 카드 포함
- [x] **4.3.3** 클라이언트 상태 동기화 타입 정의
  - `HandInfo` 인터페이스에 `actionHistory` 추가
  - `TurnInfo` 인터페이스 추가 (remainingSeconds 등)
  - `SeatInfo`에 `timeBankRemaining` 추가
  - `isStateRestore` 플래그로 새로고침/재접속 구분
- [x] **4.3.4** 테스트 실행
  ```bash
  cd backend && pytest tests/ws/test_mid_game_snapshot.py -v  # 11 passed
  cd backend && pytest tests/ws/ -v  # 145 passed
  ```
- [x] **4.3.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 4.3 완료** (날짜: 2026-01-17, 검증: 145 tests passed)

---

#### 4.4 WebSocket 하트비트 구현
**우선순위**: 🟢 P3
**예상 시간**: 30분
**관련 파일**:
- `backend/app/ws/gateway.py`
- `backend/app/ws/events.py`
- `backend/app/ws/handlers/system.py`

**작업 내용**:
- [x] **4.4.1** 서버 → 클라이언트 ping 전송 (30초)
  - `HeartbeatManager` 클래스 구현
  - 주기적으로 PING 이벤트 전송 (30초 간격)
  - `PING`/`PONG` 이벤트를 양방향으로 설정
- [x] **4.4.2** 클라이언트 pong 응답 확인
  - `SystemHandler`에 PONG 이벤트 핸들러 추가
  - `last_pong_at` 타임스탬프 업데이트
  - `missed_pongs` 카운터 리셋
- [x] **4.4.3** 응답 없는 연결 자동 종료
  - 2회 연속 응답 없으면 연결 종료 (close code 4003)
  - `MAX_MISSED_PONGS = 2` 설정
- [x] **4.4.4** 테스트 실행
  ```bash
  cd backend && pytest tests/ws/test_heartbeat.py -v  # 22 passed
  cd backend && pytest tests/ws/ -v  # 168 passed
  ```
- [x] **4.4.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 4.4 완료** (날짜: 2026-01-17, 검증: 168 tests passed)

---

#### 4.5 메모리 정리 최적화
**우선순위**: 🟢 P3
**예상 시간**: 30분
**관련 파일**:
- `backend/app/game/manager.py`
- `backend/tests/game/test_memory_cleanup.py`

**작업 내용**:
- [x] **4.5.1** 빈 테이블 자동 정리 (30분 후)
  - 플레이어 0명인 테이블 감지 (`_cleanup_empty_tables()`)
  - 30분 경과 시 메모리에서 제거 (`EMPTY_TABLE_CLEANUP_MINUTES = 30`)
  - 백그라운드 태스크로 60초마다 체크 (`_cleanup_loop()`)
- [x] **4.5.2** 완료된 핸드 데이터 정리
  - `save_hand_history()` - 핸드 히스토리 저장
  - `cleanup_hand_data()` - 핸드 완료 후 임시 데이터 정리
  - 최근 10핸드만 메모리 유지 (`MAX_HAND_HISTORY_PER_TABLE = 10`)
- [x] **4.5.3** 메모리 사용량 모니터링 로그
  - `_log_memory_usage()` - 주기적 메모리 사용량 로그
  - `get_memory_stats()` - 메모리 통계 조회 API
  - 임계값 500MB 초과 시 경고 (`MEMORY_WARNING_THRESHOLD_MB = 500`)
- [x] **4.5.4** 테스트 실행
  ```bash
  cd backend && pytest tests/game/test_memory_cleanup.py -v  # 25 passed
  cd backend && pytest tests/game/ -v  # 195 passed
  ```
- [x] **4.5.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 4.5 완료** (날짜: 2026-01-17, 검증: 195 tests passed)

---

### Phase 5: 운영 도구 (🔵 선택)

#### 5.1 CCU 실시간 모니터링
**우선순위**: 🔵 P4
**예상 시간**: 30분
**관련 파일**:
- `admin-backend/app/api/dashboard.py`
- `admin-backend/app/services/metrics_service.py`
- `backend/app/ws/manager.py`
- `admin-frontend/src/components/dashboard/CCUChart.tsx`

**작업 내용**:
- [x] **5.1.1** 실시간 접속자 수 집계 (Redis)
  - 키: `online_users` (SET)
  - WebSocket 연결 시 `_track_user_online()` 호출
  - 연결 해제 시 `_track_user_offline()` 호출
  - CCU 스냅샷 태스크 (매 분마다 `ccu_hourly:{hour_key}` 저장)
- [x] **5.1.2** 대시보드 API 추가
  - `GET /api/dashboard/ccu` - 현재 접속자 수
  - `GET /api/dashboard/ccu/history` - 시간별 접속자 수
  - `GET /api/dashboard/users/summary` - CCU/DAU/WAU/MAU 요약
- [x] **5.1.3** 프론트엔드 실시간 차트
  - CCUChart 컴포넌트 (Recharts 라인 차트)
  - 5초 자동 갱신
  - MetricCard로 CCU 표시
- [x] **5.1.4** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/api/test_dashboard.py -v  # 14 passed
  ```
- [x] **5.1.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 5.1 완료** (날짜: 2026-01-17, 검증: 14 tests passed)

---

#### 5.2 DAU/MAU 통계
**우선순위**: 🔵 P4
**예상 시간**: 30분
**관련 파일**:
- `admin-backend/app/services/metrics_service.py`
- `admin-backend/app/services/statistics_service.py`
- `backend/app/ws/manager.py`
- `admin-frontend/src/components/dashboard/DAUChart.tsx`

**작업 내용**:
- [x] **5.2.1** 일별/월별 활성 사용자 집계
  - Redis HyperLogLog 사용
  - 키: `dau:{date}`, `mau:{month}`
  - WebSocket 연결 시 `_track_user_online()`에서 PFADD
  - WAU: 최근 7일 DAU HyperLogLog PFMERGE
- [x] **5.2.2** 통계 API 추가
  - `GET /api/dashboard/dau` - 일별 활성 사용자
  - `GET /api/dashboard/dau/history` - DAU 히스토리
  - `GET /api/dashboard/mau` - 월별 활성 사용자
  - `GET /api/dashboard/mau/history` - MAU 히스토리
- [x] **5.2.3** 대시보드 차트 연동
  - DAUChart 컴포넌트 (일별 막대 차트)
  - MetricCard로 DAU/WAU/MAU 표시
  - 날짜 범위 선택기 (7d/14d/30d)
- [x] **5.2.4** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/api/test_dashboard.py -v  # 14 passed
  ```
- [x] **5.2.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 5.2 완료** (날짜: 2026-01-17, 검증: 14 tests passed)

---

#### 5.3 매출 현황 대시보드
**우선순위**: 🔵 P4
**예상 시간**: 30분
**관련 파일**:
- `admin-backend/app/api/dashboard.py`
- `admin-backend/app/services/statistics_service.py`
- `admin-frontend/src/components/dashboard/RevenueChart.tsx`

**작업 내용**:
- [x] **5.3.1** 레이크 수익 집계
  - 일별/주별/월별 레이크 합계 (hand_history 테이블 기반)
  - `GET /api/dashboard/revenue/daily` - 일별 매출
  - `GET /api/dashboard/revenue/weekly` - 주별 매출
  - `GET /api/dashboard/revenue/monthly` - 월별 매출
  - `GET /api/dashboard/revenue/summary` - 매출 요약
- [x] **5.3.2** 게임 통계
  - `GET /api/dashboard/game/statistics` - 오늘/전체 핸드 수, 레이크
  - `GET /api/dashboard/revenue/top-players` - 레이크 기여 상위 플레이어
  - `GET /api/dashboard/stake-levels` - 스테이크 레벨별 통계
- [x] **5.3.3** 대시보드 매출 차트
  - RevenueChart 컴포넌트 (Recharts 막대 차트)
  - 일별/주별/월별 탭 전환
  - 날짜 범위 선택기 (7d/14d/30d/90d)
- [x] **5.3.4** 테스트 실행
  ```bash
  cd admin-backend && pytest tests/api/test_dashboard.py -v  # 14 passed
  ```
- [x] **5.3.5** 수정 검증 완료

**완료 확인**:
- [x] **Step 5.3 완료** (날짜: 2026-01-17, 검증: 14 tests passed)

---


## 📚 Skills 파일 관리

### Skills 파일 목적
- 여러 계정에서 작업 시 일관된 작업 방식 유지
- 작업 컨텍스트 빠른 파악
- 중단/재개 시 원활한 작업 진행

### 현재 Skills 파일
1. **backend-admin-upgrade.md** - 백엔드 및 관리자 업그레이드 작업
2. **backend-scale.md** - 백엔드 확장성 작업
3. **ton-usdt-deposit.md** - TON/USDT 입금 시스템 작업

### Skills 파일 작성 규칙
```markdown
# [작업명] Skills

## 작업 개요
- 목적: [작업 목적]
- 관련 Spec: [Spec 경로]
- 현재 상태: [진행 상황]

## 주요 파일
- [파일 경로]: [파일 설명]

## 작업 순서
1. [Step 1]
2. [Step 2]
...

## 검증 방법
```bash
[테스트 명령어]
```

## 주의사항
- [주의사항 1]
- [주의사항 2]
```

### Skills 파일 업데이트 시점
- 새로운 Phase 시작 시
- 주요 작업 완료 시
- 작업 방식 변경 시

---

## 🔄 중단 대비 체크포인트

### 작업 중단 시 필수 기록 사항
1. **현재 진행 중인 Phase 및 Step**
   - Phase 번호
   - Step 번호
   - 서브태스크 완료 상태
2. **수정한 파일 목록**
   - 파일 경로
   - 수정 내용 요약
3. **발생한 에러 (있는 경우)**
   - 에러 메시지
   - 발생 위치
   - 시도한 해결 방법
4. **다음 작업 내용**
   - 다음 Step 번호
   - 예상 작업 시간

### 작업 재개 시 확인 사항
1. **이 문서에서 마지막 완료 Step 확인**
   - `MASTER_WORK_PLAN.md` 체크박스 확인
   - 해당 Spec의 `WORK_PROGRESS.md` 확인
2. **미완료 서브태스크 확인**
   - 체크박스 상태 확인
   - 작업 로그 확인
3. **테스트 실행하여 현재 상태 검증**
   ```bash
   # Backend 테스트
   cd backend && pytest tests/ -v
   cd admin-backend && pytest tests/ -v
   
   # Frontend 빌드
   cd frontend && npm run build
   cd admin-frontend && npm run build
   ```
4. **현재 Step부터 재개**
   - 이전 Step 완료 확인 후 진행

### 체크포인트 파일 위치
- **마스터 계획서**: `MASTER_WORK_PLAN.md` (이 파일)
- **Spec별 진행 현황**:
  - `.kiro/specs/backend-admin-upgrade/WORK_PROGRESS.md`
  - `.kiro/specs/ton-usdt-deposit/WORK_PROGRESS.md`
  - `.kiro/specs/fraud-prevention-integration/WORK_PROGRESS.md`
- **Skills 파일**: `.claude/skills/*.md`

---

## 🧪 테스트 명령어 참조

### Backend 테스트
```bash
# 전체 테스트
cd backend && pytest tests/ -v

# 특정 모듈 테스트
cd backend && pytest tests/api/ -v -k auth
cd backend && pytest tests/ws/ -v -k action
cd backend && pytest tests/services/ -v -k room
cd backend && pytest tests/game/ -v -k poker_table

# 커버리지 포함
cd backend && pytest tests/ -v --cov=app --cov-report=html
```

### Admin Backend 테스트
```bash
# 전체 테스트
cd admin-backend && pytest tests/ -v

# 특정 모듈 테스트
cd admin-backend && pytest tests/api/ -v -k users
cd admin-backend && pytest tests/services/ -v -k fraud
cd admin-backend && pytest tests/integration/ -v

# 커버리지 포함
cd admin-backend && pytest tests/ -v --cov=app --cov-report=html
```

### Frontend 테스트
```bash
# 빌드 테스트
cd frontend && npm run build

# 타입 체크
cd frontend && npm run type-check

# 린트
cd frontend && npm run lint

# E2E 테스트
cd frontend && npm run test:e2e -- --project=chromium
```

### Admin Frontend 테스트
```bash
# 빌드 테스트
cd admin-frontend && npm run build

# 타입 체크
cd admin-frontend && npm run type-check

# 린트
cd admin-frontend && npm run lint
```

### 서버 실행 확인
```bash
# Backend
cd backend && python -c "from app.main import app; print('OK')"

# Admin Backend
cd admin-backend && python -c "from app.main import app; print('OK')"

# 전체 서버 실행
./dev.sh
```

---

## 📊 작업 진행 현황 추적

### 작업 로그 템플릿
```markdown
| 날짜 | Phase | Step | 상태 | 비고 |
|------|-------|------|------|------|
| 2026-01-17 | 2.1 | 2.1.1 | 진행중 | Redis pub/sub 채널 정의 |
| 2026-01-17 | 2.1 | 2.1.2 | 완료 | 핸드 결과 전송 구현 (15 tests passed) |
```

### 현재 작업 로그
| 날짜 | Phase | Step | 상태 | 비고 |
|------|-------|------|------|------|
| 2026-01-17 | - | - | 대기 | 마스터 계획서 작성 완료 |
| 2026-01-17 | 2.1 | 2.1.1~2.1.6 | ✅ 완료 | 칩 밀어주기 탐지 연동 (75 tests passed) |
| 2026-01-17 | 2.2 | 2.2.1~2.2.6 | ✅ 완료 | 봇 탐지 시스템 게임 서버 연동 (57 tests passed) |
| 2026-01-17 | 2.3 | 2.3.1~2.3.5 | ✅ 완료 | 이상 행동 탐지 연동 (34 tests passed) |
| 2026-01-17 | 2.4 | 2.4.1~2.4.5 | ✅ 완료 | 자동 밴 시스템 연동 (474 tests passed) |
| 2026-01-17 | 2.5 | 2.5.1~2.5.6 | ✅ 완료 | 핸드 히스토리 DB 저장 연결 + 조회 API (106 tests passed) |
| 2026-01-17 | 3.1 | 3.1.1~3.1.6 | ✅ 완료 | 서버 점검 모드 제어 (29 tests passed) |
| 2026-01-17 | 3.2 | 3.2.1~3.2.6 | ✅ 완료 | 공지사항 발송 시스템 (32 tests passed) |
| 2026-01-17 | 3.3 | 3.3.1~3.3.6 | ✅ 완료 | 방 강제 종료 기능 (19 tests passed) |
| 2026-01-17 | 3.4 | 3.4.1~3.4.5 | ✅ 완료 | 핸드 리플레이 기능 (19 tests passed + frontend 빌드 성공) |
| 2026-01-17 | 3.5 | 3.5.1~3.5.6 | ✅ 완료 | 자산 수동 지급/회수 (49 tests passed) |
| 2026-01-17 | 3.6 | 3.6.1~3.6.5 | ✅ 완료 | 유저 상세 로그 조회 (60 tests passed) |
| 2026-01-17 | 3.7 | 3.7.1~3.7.5 | ✅ 완료 | 부정 사용자 의심 리스트 (14 tests passed) |
| 2026-01-17 | 4.1 | 4.1.1~4.1.5 | ✅ 완료 | 대기열(Waitlist) 관리 (20 tests passed) |
| 2026-01-17 | 4.2 | 4.2.1~4.2.4 | ✅ 완료 | 관전자/플레이어 그룹 분리 전송 (17 tests passed) |
| 2026-01-17 | 4.3 | 4.3.1~4.3.5 | ✅ 완료 | 중간 입장 동기화 - Snapshot (145 tests passed) |
| 2026-01-17 | 4.4 | 4.4.1~4.4.5 | ✅ 완료 | WebSocket 하트비트 구현 (168 tests passed) |
| 2026-01-17 | 4.5 | 4.5.1~4.5.5 | ✅ 완료 | 메모리 정리 최적화 (195 tests passed) |
| 2026-01-18 | 5.1 | 5.1.1~5.1.5 | ✅ 완료 | CCU 실시간 모니터링 (14 tests passed) |
| 2026-01-18 | 5.2 | 5.2.1~5.2.5 | ✅ 완료 | DAU/MAU 통계 (14 tests passed) |
| 2026-01-18 | 5.3 | 5.3.1~5.3.5 | ✅ 완료 | 매출 현황 대시보드 (14 tests passed) |

---

## 🎯 다음 작업 권장사항

### 즉시 시작 가능한 작업 (P1)
1. ~~**Phase 2.1: 칩 밀어주기 탐지 게임 서버 연동**~~ ✅ **완료** (2026-01-17)

2. ~~**Phase 2.2: 봇 탐지 시스템 게임 서버 연동**~~ ✅ **완료** (2026-01-17)
   - Redis 기반 타이밍/액션 패턴 저장 구현
   - BotDetector 실시간 분석 메서드 추가
   - FraudEventConsumer 개선

3. ~~**Phase 2.3: 이상 행동 탐지 연동**~~ ✅ **완료** (2026-01-17)
   - PlayerSessionTracker 연동 (세션 시작/종료/통계 업데이트)
   - AnomalyDetector DB 기반 종합 분석 연동
   - TelegramNotifier + AuditService 알림 강화

4. ~~**Phase 2.4: 자동 밴 시스템 연동**~~ ✅ **완료** (2026-01-17)
   - AutoBanService.process_detection() 메인 엔트리 포인트 구현
   - BanService 연동으로 실제 임시 밴 적용
   - 임계값 기반 자동 밴 + 심각도 high 즉시 밴 옵션
   - Telegram 알림 + 감사 로그 기록

5. ~~**Phase 2.5: 핸드 히스토리 DB 저장**~~ ✅ **완료** (2026-01-17)
   - ActionHandler에서 HandHistoryService.save_hand_result() 연결
   - 핸드 조회 API 추가 (GET /api/v1/hands/me, GET /api/v1/hands/{hand_id})
   - 보안: 사용자가 참가한 핸드만 조회 가능

### 병렬 작업 가능 (다른 계정)
- **Phase 3.1: 서버 점검 모드 제어** (독립적)
- **Phase 3.2: 공지사항 발송 시스템** (독립적)
- **Phase 5.1: CCU 실시간 모니터링** (독립적)

### 선행 작업 완료됨 (Phase 3 완료!)
- ~~**Phase 3.4: 핸드 리플레이 기능**~~ ✅ **완료** (2026-01-17)
- ~~**Phase 3.5: 자산 수동 지급/회수**~~ ✅ **완료** (2026-01-17)
- ~~**Phase 3.6: 유저 상세 로그 조회**~~ ✅ **완료** (2026-01-17)
- ~~**Phase 3.7: 부정 사용자 의심 리스트**~~ ✅ **완료** (2026-01-17)

### 다음 작업 (Phase 4: 안정성 개선)
- ~~**Phase 4.1: 대기열(Waitlist) 관리**~~ ✅ **완료** (2026-01-17)
- ~~**Phase 4.2: 관전자/플레이어 그룹 분리 전송**~~ ✅ **완료** (2026-01-17)
- ~~**Phase 4.3: 중간 입장 동기화 (Snapshot)**~~ ✅ **완료** (2026-01-17)
  - actionHistory: 현재 핸드 베팅 흐름 추가
  - turnInfo: 턴 타이머 동기화용 정보 추가
  - timeBankRemaining: 타임 뱅크 정보 추가
- ~~**Phase 4.4: WebSocket 하트비트 구현**~~ ✅ **완료** (2026-01-17)
  - HeartbeatManager: 30초 간격 PING 전송
  - 양방향 PING/PONG 지원
  - 2회 연속 미응답 시 연결 종료 (close code 4003)
- ~~**Phase 4.5: 메모리 정리 최적화**~~ ✅ **완료** (2026-01-17)
  - 빈 테이블 자동 정리 (30분 후)
  - 핸드 히스토리 최근 10개만 유지
  - 메모리 사용량 모니터링 (500MB 임계값)

### Phase 5: 운영 도구 (완료!)
- ~~**Phase 5.1: CCU 실시간 모니터링**~~ ✅ **완료** (2026-01-18)
  - Redis SET `online_users` 기반 CCU 집계
  - 분별/시간별 CCU 스냅샷 저장
  - 대시보드 API + Recharts 차트
- ~~**Phase 5.2: DAU/MAU 통계**~~ ✅ **완료** (2026-01-18)
  - Redis HyperLogLog 기반 DAU/MAU 집계
  - WAU: 7일간 HyperLogLog PFMERGE
  - 사용자 통계 요약 API
- ~~**Phase 5.3: 매출 현황 대시보드**~~ ✅ **완료** (2026-01-18)
  - 일별/주별/월별 레이크 집계
  - 게임 통계 + 스테이크 레벨별 통계
  - RevenueChart 컴포넌트

### 🎉 모든 Phase 완료!
- Phase 2~5 모든 작업 완료
- 총 테스트: 500+ passed
- 다음 단계: 프로덕션 배포 준비 또는 추가 기능 개발

---

## 📝 작업 시작 전 체크리스트

### 환경 확인
- [ ] Python 가상환경 활성화 (`backend/.venv`, `admin-backend/.venv`)
- [ ] Node.js 버전 확인 (v18 이상)
- [ ] PostgreSQL 실행 중
- [ ] Redis 실행 중

### 문서 확인
- [ ] `MASTER_WORK_PLAN.md` 최신 버전 확인
- [ ] 해당 Spec의 `WORK_PROGRESS.md` 확인
- [ ] 관련 Skills 파일 확인

### 테스트 실행
- [ ] Backend 테스트 통과 확인
- [ ] Admin Backend 테스트 통과 확인
- [ ] Frontend 빌드 성공 확인

### 작업 준비
- [ ] 작업할 Phase 및 Step 확인
- [ ] 관련 파일 목록 확인
- [ ] 예상 작업 시간 확인

---

## 🔗 관련 문서 링크

### Spec 문서
- [Backend Admin Upgrade Spec](.kiro/specs/backend-admin-upgrade/)
- [TON USDT Deposit Spec](.kiro/specs/ton-usdt-deposit/)
- [Fraud Prevention Integration Spec](.kiro/specs/fraud-prevention-integration/)

### 작업 진행 현황
- [Backend Admin Upgrade Progress](.kiro/specs/backend-admin-upgrade/WORK_PROGRESS.md)
- [TON USDT Deposit Progress](.kiro/specs/ton-usdt-deposit/WORK_PROGRESS.md)
- [Fraud Prevention Integration Progress](.kiro/specs/fraud-prevention-integration/WORK_PROGRESS.md)

### 기타 문서
- [프로젝트 문서](PROJECT_DOCUMENTATION.md)
- [구현 상태](IMPLEMENTATION_STATUS.md)
- [버그 수정 계획](BUGFIX_WORK_PLAN.md)
- [백엔드 업그레이드 계획](BACKEND_UPGRADE_WORK_PLAN.md)

---

## 📞 문제 발생 시 대응

### 일반적인 문제
1. **모듈 import 에러**
   ```bash
   cd backend && pip install -r requirements.txt
   cd admin-backend && pip install -r requirements.txt
   ```

2. **DB 마이그레이션 에러**
   ```bash
   cd backend && alembic upgrade head
   cd admin-backend && alembic upgrade head
   ```

3. **Redis 연결 에러**
   ```bash
   # Redis 실행 확인
   redis-cli ping
   # 응답: PONG
   ```

4. **WebSocket 연결 에러**
   - Backend 서버 실행 확인
   - CORS 설정 확인
   - 브라우저 콘솔 에러 확인

### 테스트 실패 시
1. **에러 메시지 확인**
   - 어떤 테스트가 실패했는지 확인
   - 에러 메시지 전체 읽기
2. **관련 코드 확인**
   - 실패한 테스트 파일 확인
   - 테스트 대상 코드 확인
3. **수정 및 재테스트**
   - 코드 수정
   - 테스트 재실행
4. **문서 업데이트**
   - 발견한 이슈 기록
   - 해결 방법 기록

---

## 🎓 학습 자료

### 프로젝트 이해를 위한 문서
1. **게임 로직**: `docs/HOLDEM_GAME_LOGIC_CHECKLIST.md`
2. **API 참조**: `docs/API_REFERENCE.md`
3. **WebSocket 프로토콜**: `docs/20-realtime-protocol-v1.md`
4. **에러 코드**: `docs/21-error-codes-v1.md`

### 기술 스택 문서
- **FastAPI**: https://fastapi.tiangolo.com/
- **Playwright**: https://playwright.dev/
- **Next.js**: https://nextjs.org/docs
- **Framer Motion**: https://www.framer.com/motion/

---

**작성자**: Kiro AI
**작성일**: 2026-01-17
**버전**: 1.0
**다음 업데이트**: 작업 진행 시

