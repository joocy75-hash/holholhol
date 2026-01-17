# 부정 행위 탐지 시스템 통합 스킬

## 프로젝트 개요
게임 서버와 관리자 백엔드 간 부정 행위 탐지 시스템 실시간 연동

## 작업 규칙

### 1. 단계별 작업 원칙
- **한 번에 하나의 Task만 작업**
- 각 Task 완료 후 반드시 **검증 테스트 실행**
- 테스트 통과 후 **WORK_PROGRESS.md에 완료 체크 (✅)** 표시
- 다음 Task로 진행 전 **이전 Task 완료 확인**

### 2. 검증 테스트 원칙
```bash
# Backend 테스트
cd backend && pytest tests/services/ -v -k fraud
cd backend && pytest tests/ws/ -v -k fraud

# Admin Backend 테스트
cd admin-backend && pytest tests/services/ -v -k fraud
cd admin-backend && pytest tests/integration/ -v

# 서버 실행 확인
cd backend && python -c "from app.main import app; print('OK')"
cd admin-backend && python -c "from app.main import app; print('OK')"
```

## 파일 구조

### Backend (이벤트 발행)
```
backend/
├── app/
│   ├── services/
│   │   ├── fraud_event_publisher.py  # 이벤트 발행자
│   │   ├── player_session_tracker.py # 세션 추적
│   │   └── hand_history.py           # 핸드 히스토리
│   ├── ws/handlers/
│   │   └── action.py                 # 액션 핸들러 (이벤트 발행)
│   └── models/
│       └── hand.py                   # HandParticipant 모델
```

### Admin Backend (이벤트 소비)
```
admin-backend/
├── app/
│   ├── services/
│   │   ├── fraud_event_consumer.py    # 이벤트 소비자
│   │   ├── chip_dumping_detector.py   # 칩 밀어주기 탐지
│   │   ├── bot_detector.py            # 봇 탐지
│   │   ├── anomaly_detector.py        # 이상 행동 탐지
│   │   └── auto_ban.py                # 자동 제재
│   └── api/
│       └── fraud.py                   # 모니터링 API
```

## Redis Pub/Sub 채널

### 채널 목록
- `fraud:hand_completed` - 핸드 완료 이벤트
- `fraud:player_action` - 플레이어 액션 이벤트
- `fraud:player_stats` - 플레이어 통계 이벤트

### 메시지 형식
```python
# hand_completed
{
    "hand_id": "uuid",
    "room_id": "uuid",
    "players": [
        {
            "user_id": "uuid",
            "actions": [...],
            "result": "win/lose",
            "amount": 1000
        }
    ],
    "timestamp": "2026-01-17T..."
}

# player_action
{
    "user_id": "uuid",
    "room_id": "uuid",
    "action_type": "raise",
    "amount": 100,
    "response_time_ms": 1500,
    "timestamp": "2026-01-17T..."
}

# player_stats
{
    "user_id": "uuid",
    "win_rate": 0.65,
    "avg_bet": 500,
    "play_time_hours": 10,
    "timestamp": "2026-01-17T..."
}
```

## 작업 진행 현황 확인

작업 시작 전 반드시 확인:
```
.kiro/specs/fraud-prevention-integration/WORK_PROGRESS.md
```

## 관련 문서

- `.kiro/specs/fraud-prevention-integration/requirements.md` - 요구사항
- `.kiro/specs/fraud-prevention-integration/tasks.md` - 태스크 목록
- `.kiro/specs/fraud-prevention-integration/design.md` - 기술 설계
- `.kiro/specs/fraud-prevention-integration/WORK_PROGRESS.md` - 진행 현황

## 테스트 명령어

```bash
# Backend 테스트
cd backend && pytest tests/services/test_fraud_event_publisher.py -v
cd backend && pytest tests/services/test_player_session_tracker.py -v
cd backend && pytest tests/services/test_hand_history.py -v
cd backend && pytest tests/ws/test_fraud_event_integration.py -v

# Admin Backend 테스트
cd admin-backend && pytest tests/services/test_fraud_event_consumer.py -v
cd admin-backend && pytest tests/services/test_chip_dumping_detector.py -v
cd admin-backend && pytest tests/services/test_bot_detector.py -v
cd admin-backend && pytest tests/services/test_anomaly_detector.py -v
cd admin-backend && pytest tests/services/test_auto_ban.py -v
cd admin-backend && pytest tests/integration/test_fraud_pipeline.py -v

# 전체 통합 테스트
cd admin-backend && pytest tests/integration/ -v
```

## 주요 API 엔드포인트

### 모니터링 API
```
GET /api/fraud/detections - 탐지 목록
GET /api/fraud/detections/{id} - 탐지 상세
GET /api/fraud/stats - 탐지 통계
```

## 주의사항

1. **Redis 연결 필수** - pub/sub 채널 사용
2. **봇 플레이어 필터링** - 봇 액션은 이벤트 발행 제외
3. **이벤트 순서 보장** - 시퀀스 번호 사용
4. **에러 처리** - 이벤트 발행/소비 실패 시 로깅
5. **성능 고려** - 비동기 처리, 배치 처리

## 다음 작업

현재 상태: **Phase 5 완료 (100%)**
- 모든 통합 테스트 통과 (111 tests)
- Backend 46 tests, Admin Backend 65 tests

추가 작업 필요 시:
- 실시간 대시보드 UI 개선
- 탐지 알고리즘 정확도 향상
- 성능 최적화
