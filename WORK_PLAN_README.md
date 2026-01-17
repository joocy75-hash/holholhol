# 작업 계획서 빠른 참조 가이드

> 여러 계정에서 작업 시 빠르게 현재 상황을 파악하기 위한 가이드

---

## 🚀 빠른 시작

### 1. 현재 상황 파악 (30초)
```bash
# 1. 마스터 계획서 확인
cat MASTER_WORK_PLAN.md | grep "현재 작업 로그" -A 5

# 2. 진행 중인 Spec 확인
ls -la .kiro/specs/*/WORK_PROGRESS.md

# 3. 최근 수정 파일 확인
git status
```

### 2. 작업 시작 전 체크 (1분)
```bash
# 환경 확인
cd backend && source .venv/bin/activate && python -c "from app.main import app; print('Backend OK')"
cd admin-backend && source .venv/bin/activate && python -c "from app.main import app; print('Admin Backend OK')"

# 테스트 실행
cd backend && pytest tests/ -v --tb=short
cd admin-backend && pytest tests/ -v --tb=short
```

### 3. 다음 작업 확인 (30초)
```bash
# 마스터 계획서에서 다음 작업 확인
cat MASTER_WORK_PLAN.md | grep "다음 작업 권장사항" -A 10
```

---

## 📊 현재 프로젝트 상태

### 전체 완성도: **76%**

| 영역 | 완료율 | 다음 작업 |
|------|--------|----------|
| 핵심 게임 로직 | 100% ✅ | - |
| TON/USDT 입금 | 100% ✅ | - |
| 부정 행위 탐지 | 100% ✅ | - |
| 버그 수정 | 100% ✅ | - |
| 관리자 대시보드 | 80% 🟡 | Phase 3 진행 |
| 백엔드 보안 | 55% 🟡 | Phase 2 진행 |
| 안정성 개선 | 0% 🔴 | Phase 4 대기 |
| 운영 도구 | 0% 🔴 | Phase 5 대기 |

---

## 🎯 우선순위 작업 (이번 주)

### P1 (높음) - 즉시 시작 가능
1. **Phase 2.1: 칩 밀어주기 탐지 연동** (60분)
   - 파일: `backend/app/ws/handlers/action.py`
   - 테스트: `pytest tests/ws/ -v -k fraud`

2. **Phase 2.2: 봇 탐지 시스템 연동** (45분)
   - 파일: `admin-backend/app/services/bot_detector.py`
   - 테스트: `pytest tests/services/ -v -k bot_detector`

### P2 (중간) - 병렬 작업 가능
3. **Phase 3.1: 서버 점검 모드** (45분)
4. **Phase 3.2: 공지사항 시스템** (45분)

---

## 📁 주요 문서 위치

### 계획서
- **마스터 계획서**: `MASTER_WORK_PLAN.md` ⭐
- **버그 수정 계획**: `BUGFIX_WORK_PLAN.md`
- **백엔드 업그레이드 계획**: `BACKEND_UPGRADE_WORK_PLAN.md`

### 진행 현황
- **Backend Admin Upgrade**: `.kiro/specs/backend-admin-upgrade/WORK_PROGRESS.md`
- **TON USDT Deposit**: `.kiro/specs/ton-usdt-deposit/WORK_PROGRESS.md`
- **Fraud Prevention**: `.kiro/specs/fraud-prevention-integration/WORK_PROGRESS.md`

### Skills 파일
- **Backend Admin Upgrade**: `.claude/skills/backend-admin-upgrade.md`
- **TON USDT Deposit**: `.claude/skills/ton-usdt-deposit.md`
- **Fraud Prevention**: `.claude/skills/fraud-prevention-integration.md`

---

## 🔧 자주 사용하는 명령어

### 테스트
```bash
# Backend 전체
cd backend && pytest tests/ -v

# Admin Backend 전체
cd admin-backend && pytest tests/ -v

# 특정 모듈만
pytest tests/services/test_fraud_event_publisher.py -v

# 실패한 테스트만 재실행
pytest --lf -v
```

### 서버 실행
```bash
# 전체 서버 실행
./dev.sh

# Backend만
cd backend && uvicorn app.main:app --reload

# Admin Backend만
cd admin-backend && uvicorn app.main:app --reload --port 8001
```

### 빌드
```bash
# Frontend
cd frontend && npm run build

# Admin Frontend
cd admin-frontend && npm run build
```

---

## 🚨 작업 중단 시 체크리스트

### 중단 전 (2분)
- [ ] 현재 작업 중인 Phase/Step 번호 기록
- [ ] 수정한 파일 목록 기록
- [ ] 발생한 에러 기록 (있는 경우)
- [ ] `WORK_PROGRESS.md` 업데이트
- [ ] `MASTER_WORK_PLAN.md` 작업 로그 업데이트

### 재개 시 (2분)
- [ ] `MASTER_WORK_PLAN.md` 작업 로그 확인
- [ ] 해당 Spec의 `WORK_PROGRESS.md` 확인
- [ ] 테스트 실행하여 현재 상태 검증
- [ ] 다음 Step부터 재개

---

## 💡 팁

### 효율적인 작업 방법
1. **한 번에 하나의 Step만** - 토큰 한계 고려
2. **서브에이전트 활용** - 복잡한 작업은 전문 에이전트에게
3. **테스트 먼저** - 작업 전 테스트 통과 확인
4. **문서 즉시 업데이트** - 작업 완료 시 바로 기록

### 문제 발생 시
1. **에러 메시지 전체 읽기**
2. **관련 테스트 확인**
3. **문서에 기록**
4. **다음 계정에서 이어서 작업**

---

## 📞 도움말

### 일반적인 문제
- **모듈 import 에러**: `pip install -r requirements.txt`
- **DB 마이그레이션 에러**: `alembic upgrade head`
- **Redis 연결 에러**: `redis-cli ping`
- **WebSocket 연결 에러**: Backend 서버 실행 확인

### 더 자세한 정보
- 전체 계획: `MASTER_WORK_PLAN.md`
- 프로젝트 문서: `PROJECT_DOCUMENTATION.md`
- 구현 상태: `IMPLEMENTATION_STATUS.md`

---

**마지막 업데이트**: 2026-01-17
**다음 작업**: Phase 2.1 (칩 밀어주기 탐지 연동)
