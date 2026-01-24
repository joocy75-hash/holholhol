# 백엔드 보안 수정 로드맵

> **생성일**: 2026-01-23
> **총 Phase 수**: 3
> **예상 소요 시간**: 8-12시간 (계정 전환 포함)

---

## 🗺️ 전체 로드맵 개요

```
Phase 1 (Critical)    Phase 2 (Important)    Phase 3 (Quality)
  2-3시간     →          3-4시간       →         3-5시간

[권한 체크]          [보안 강화]            [통계 개선]
[라우트 수정]        [트랜잭션 안정화]      [성능 최적화]
                     [코드 정리]             [문서화]
```

---

## Phase 1: Critical 보안 이슈 수정 ⚠️

**목표**: 즉시 배포 블로커 제거 (관리자 권한, 라우트)
**예상 시간**: 2-3시간
**의존성**: 없음 (최우선 작업)

### Step 1.1: 관리자 권한 의존성 추가
**담당 에이전트**: code-explorer → code-architect
**시간**: 30분

#### 작업 내용
1. `backend/app/api/deps.py` 분석
   - 현재 `CurrentUser` 의존성 확인
   - 기존 권한 체크 패턴 탐색

2. `get_current_admin` 의존성 추가
   ```python
   async def get_current_admin(
       current_user: CurrentUser,
   ) -> User:
       """관리자 권한 검증"""
       if not current_user.is_admin:  # 실제 필드명 확인 필요
           raise HTTPException(
               status_code=403,
               detail="관리자 권한이 필요합니다"
           )
       return current_user

   CurrentAdmin = Annotated[User, Depends(get_current_admin)]
   ```

3. `User` 모델에 `is_admin` 필드 확인
   - 없으면 대체 방법 탐색 (role 필드, admin_users 테이블 등)

#### 검증
- [ ] deps.py import 오류 없음
- [ ] `CurrentAdmin` 타입 힌트 정상 동작

#### 체크포인트
```bash
# WORK_STATE.md 업데이트
Phase: P1
Step: 1.1 완료
파일: backend/app/api/deps.py
변경: get_current_admin 추가
```

---

### Step 1.2: admin_partner.py 엔드포인트 권한 적용
**담당 에이전트**: code-reviewer (적용 후)
**시간**: 45분

#### 작업 내용
1. `backend/app/api/admin_partner.py` 수정
   - 모든 엔드포인트 함수에서 `CurrentUser` → `CurrentAdmin` 교체
   - 영향받는 함수 (총 7개):
     - `create_partner` (Line 50)
     - `get_partners` (Line 95)
     - `get_partner` (Line 134)
     - `update_partner` (Line 151)
     - `delete_partner` (Line 167)
     - `generate_api_key` (추정)
     - 기타 엔드포인트

2. Import 추가
   ```python
   from app.api.deps import CurrentAdmin
   ```

#### 검증
- [ ] 모든 엔드포인트 수정 완료
- [ ] 타입 체크 통과 (mypy 또는 Pylance)
- [ ] 백엔드 서버 시작 오류 없음

#### 체크포인트
```bash
# WORK_STATE.md 업데이트
Phase: P1
Step: 1.2 완료
파일: backend/app/api/admin_partner.py
변경: 7개 엔드포인트 권한 적용
```

---

### Step 1.3: 라우트 경로 표준화
**담당 에이전트**: 없음 (간단 수정)
**시간**: 15분

#### 작업 내용
1. `backend/app/main.py` 수정
   - 현재: `app.include_router(admin_partner.router, prefix="/api/internal")`
   - 수정: `app.include_router(admin_partner.router, prefix=API_V1_PREFIX, tags=["admin-partners"])`

2. `backend/app/api/admin_partner.py` 라우터 prefix 수정
   - 현재: `router = APIRouter(prefix="/admin/partners")`
   - 수정: `router = APIRouter(prefix="/admin/partners", tags=["admin-partners"])`

#### 최종 경로
- Before: `/api/internal/admin/partners/*`
- After: `/api/v1/admin/partners/*`

#### 검증
- [ ] 라우터 등록 확인 (`curl http://localhost:8000/docs`)
- [ ] OpenAPI 스키마에 경로 정상 표시

#### 체크포인트
```bash
# WORK_STATE.md 업데이트
Phase: P1
Step: 1.3 완료
파일: backend/app/main.py, backend/app/api/admin_partner.py
변경: 라우트 경로 /api/v1/admin/partners로 표준화
```

---

### Step 1.4: 권한 체크 테스트 작성
**담당 에이전트**: test-runner (실행 후)
**시간**: 1시간

#### 작업 내용
1. `backend/tests/api/test_admin_partner.py` 생성

2. 테스트 케이스 작성
   ```python
   # 1. 관리자 권한 없이 호출 시 403
   async def test_create_partner_without_admin(client, normal_user_token):
       response = await client.post(
           "/api/v1/admin/partners",
           json={"name": "Test", "commission_rate": 10},
           headers={"Authorization": f"Bearer {normal_user_token}"}
       )
       assert response.status_code == 403
       assert "관리자 권한" in response.json()["detail"]

   # 2. 관리자 권한으로 성공
   async def test_create_partner_with_admin(client, admin_user_token):
       response = await client.post(
           "/api/v1/admin/partners",
           json={"name": "Test", "commission_rate": 10},
           headers={"Authorization": f"Bearer {admin_user_token}"}
       )
       assert response.status_code == 200

   # 3. 모든 엔드포인트 권한 체크
   @pytest.mark.parametrize("endpoint,method", [
       ("/api/v1/admin/partners", "POST"),
       ("/api/v1/admin/partners", "GET"),
       ("/api/v1/admin/partners/1", "GET"),
       ("/api/v1/admin/partners/1", "PATCH"),
       ("/api/v1/admin/partners/1", "DELETE"),
   ])
   async def test_all_endpoints_require_admin(client, normal_user_token, endpoint, method):
       # ...
   ```

3. Fixture 추가 (conftest.py)
   - `admin_user_token`: 관리자 토큰
   - `normal_user_token`: 일반 사용자 토큰

#### 검증
- [ ] 테스트 최소 5개 작성
- [ ] 모든 테스트 통과
- [ ] 커버리지 90% 이상

#### 체크포인트
```bash
pytest backend/tests/api/test_admin_partner.py -v
# 결과 기록
Phase: P1
Step: 1.4 완료
테스트: 5개 통과
커버리지: 95%
```

---

### Step 1.5: Phase 1 검증 및 체크포인트
**담당 에이전트**: code-reviewer
**시간**: 30분

#### 작업 내용
1. 전체 테스트 실행
   ```bash
   cd backend && pytest tests/ -v --tb=short
   ```

2. Code review agent 실행
   - Critical 이슈 해결 확인
   - 새로운 이슈 발견 시 기록

3. WORK_STATE.md 업데이트
   - Phase 1 완료 표시
   - 다음 Phase 시작 준비

4. Git commit
   ```bash
   git add backend/app/api/deps.py backend/app/api/admin_partner.py backend/app/main.py
   git add backend/tests/api/test_admin_partner.py
   git commit -m "fix(security): add admin authorization to partner endpoints

   - Add CurrentAdmin dependency to deps.py
   - Apply admin check to all admin_partner endpoints
   - Standardize route path to /api/v1/admin/partners
   - Add comprehensive authorization tests

   Fixes: C-1 (관리자 권한 체크 누락, 95% confidence)
   Fixes: C-2 (라우트 경로 불일치, 92% confidence)

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   ```

#### 검증
- [ ] 전체 테스트 통과 (352개 + 신규 5개)
- [ ] Critical 이슈 0건
- [ ] Git commit 성공

#### 체크포인트
```bash
/holdem-checkpoint "Phase 1 완료: Critical 보안 이슈 수정"
```

---

## Phase 2: Important 보안 이슈 수정 🔒

**목표**: 보안 취약점 제거 및 안정성 향상
**예상 시간**: 3-4시간
**의존성**: Phase 1 완료

### Step 2.1: LIKE 패턴 이스케이프 유틸 작성
**담당 에이전트**: 없음
**시간**: 30분

#### 작업 내용
1. `backend/app/utils/sql.py` 생성 (또는 기존 파일 확인)

2. 이스케이프 함수 작성
   ```python
   """SQL 관련 유틸리티 함수"""

   def escape_like_pattern(pattern: str, escape_char: str = "\\") -> str:
       """
       LIKE 패턴의 특수문자 이스케이프

       Args:
           pattern: 사용자 입력 검색어
           escape_char: 이스케이프 문자 (기본: \\)

       Returns:
           이스케이프된 패턴

       Example:
           >>> escape_like_pattern("100%")
           '100\\%'
           >>> escape_like_pattern("test_user")
           'test\\_user'
       """
       pattern = pattern.replace(escape_char, escape_char + escape_char)
       pattern = pattern.replace("%", escape_char + "%")
       pattern = pattern.replace("_", escape_char + "_")
       return pattern
   ```

3. 테스트 작성 (`backend/tests/utils/test_sql.py`)
   ```python
   from app.utils.sql import escape_like_pattern

   def test_escape_percentage():
       assert escape_like_pattern("100%") == "100\\%"

   def test_escape_underscore():
       assert escape_like_pattern("test_user") == "test\\_user"

   def test_escape_backslash():
       assert escape_like_pattern("path\\to\\file") == "path\\\\to\\\\file"

   def test_escape_multiple():
       assert escape_like_pattern("100%_off") == "100\\%\\_off"
   ```

#### 검증
- [ ] 테스트 4개 통과
- [ ] Docstring 작성 완료

---

### Step 2.2: partner.py 검색 필터 수정
**담당 에이전트**: 없음
**시간**: 30분

#### 작업 내용
1. `backend/app/services/partner.py` 수정
   - Line 256-259 (get_partners 메서드)
   - Line 411-414 (get_referrals 메서드 - 있다면)

2. 수정 전
   ```python
   search_filter = Partner.name.ilike(f"%{search}%") | Partner.partner_code.ilike(
       f"%{search}%"
   )
   ```

3. 수정 후
   ```python
   from app.utils.sql import escape_like_pattern

   escaped_search = escape_like_pattern(search)
   search_filter = (
       Partner.name.ilike(f"%{escaped_search}%", escape="\\") |
       Partner.partner_code.ilike(f"%{escaped_search}%", escape="\\")
   )
   ```

#### 검증
- [ ] Import 추가 확인
- [ ] 검색 기능 정상 동작 (수동 테스트)
- [ ] `%`, `_` 입력 시 특수문자로 검색되지 않음

---

### Step 2.3: 트랜잭션 롤백 로직 개선
**담당 에이전트**: silent-failure-hunter (검증 후)
**시간**: 1시간

#### 작업 내용
1. `backend/app/services/partner_settlement.py` 수정
   - `pay_settlement` 메서드 (Line 1960-2028)

2. 트랜잭션 패턴 개선
   ```python
   async def pay_settlement(self, settlement_id: int, approved_by_id: int):
       # 기존 검증 로직...

       try:
           # 1. 지갑 트랜잭션 생성
           transaction = WalletTransaction(...)
           self.db.add(transaction)

           # 2. 잔액 업데이트
           user.krw_balance = balance_after

           # 3. 파트너 통계 업데이트
           partner.total_commission_earned += settlement.commission_amount
           partner.total_commission_paid += settlement.commission_amount

           # 4. 정산 상태 업데이트
           settlement.status = PartnerSettlementStatus.PAID
           settlement.paid_at = datetime.utcnow()
           settlement.paid_by_id = approved_by_id

           # 5. 모든 변경사항 flush (여기서 실패 가능)
           await self.db.flush()

           # 6. 로그 기록
           logger.info(
               f"정산 지급 완료: settlement_id={settlement_id}, "
               f"amount={settlement.commission_amount}"
           )

           # 7. Commit은 caller가 수행

       except IntegrityError as e:
           await self.db.rollback()
           logger.error(f"정산 지급 실패 (무결성 오류): {e}")
           raise PartnerSettlementError(
               error_code="PAYMENT_INTEGRITY_ERROR",
               message="정산 지급 중 데이터 무결성 오류 발생"
           )
       except Exception as e:
           await self.db.rollback()
           logger.error(f"정산 지급 실패: {e}")
           raise PartnerSettlementError(
               error_code="PAYMENT_FAILED",
               message="정산 지급 중 오류 발생"
           )
   ```

3. 테스트 작성 (`backend/tests/services/test_partner_settlement.py`)
   ```python
   async def test_pay_settlement_rollback_on_balance_error(db_session):
       """잔액 부족 시 트랜잭션 롤백 확인"""
       # Setup: 잔액 부족한 파트너
       # When: pay_settlement 호출
       # Then: PartnerSettlementError 발생, DB 변경 없음

   async def test_pay_settlement_rollback_on_db_error(db_session, monkeypatch):
       """DB 오류 시 트랜잭션 롤백 확인"""
       # Setup: flush() 강제 실패
       # When: pay_settlement 호출
       # Then: 모든 변경사항 롤백
   ```

#### 검증
- [ ] 테스트 2개 이상 통과
- [ ] silent-failure-hunter agent 실행 (새로운 이슈 없음)

---

### Step 2.4: import 위치 정리
**담당 에이전트**: 없음
**시간**: 15분

#### 작업 내용
1. `backend/app/services/partner_settlement.py` 수정
   - Line 1997-1998의 `import hashlib`를 파일 상단으로 이동

2. 수정 전
   ```python
   async def pay_settlement(...):
       # ...
       import hashlib
       trace_id = hashlib.sha256(...)
   ```

3. 수정 후 (파일 상단)
   ```python
   import hashlib
   from datetime import datetime
   from typing import Optional
   # ... 기타 import

   # 클래스 정의...
   async def pay_settlement(...):
       # ...
       trace_id = hashlib.sha256(...)
   ```

#### 검증
- [ ] Import 순서 확인 (표준 라이브러리 → 서드파티 → 로컬)
- [ ] Linter 경고 없음

---

### Step 2.5: Integer → BigInteger 마이그레이션
**담당 에이전트**: 없음
**시간**: 1시간

#### 작업 내용
1. Alembic 마이그레이션 생성
   ```bash
   cd backend
   alembic revision -m "change_partner_total_referrals_to_bigint"
   ```

2. 마이그레이션 파일 작성
   ```python
   """change partner total_referrals to bigint

   Revision ID: xxxxx
   """
   from alembic import op
   import sqlalchemy as sa

   def upgrade():
       op.alter_column(
           'partners',
           'total_referrals',
           type_=sa.BigInteger(),
           existing_type=sa.Integer(),
           existing_nullable=False,
       )

   def downgrade():
       op.alter_column(
           'partners',
           'total_referrals',
           type_=sa.Integer(),
           existing_type=sa.BigInteger(),
           existing_nullable=False,
       )
   ```

3. `backend/app/models/partner.py` 수정
   ```python
   # Before
   total_referrals: Mapped[int] = mapped_column(
       default=0,
       nullable=False,
       comment="총 추천 회원 수",
   )

   # After
   total_referrals: Mapped[int] = mapped_column(
       BigInteger,
       default=0,
       nullable=False,
       comment="총 추천 회원 수",
   )
   ```

4. 마이그레이션 실행
   ```bash
   alembic upgrade head
   ```

#### 검증
- [ ] 마이그레이션 성공
- [ ] 기존 데이터 유지 확인
- [ ] Downgrade 테스트 성공

---

### Step 2.6: Phase 2 검증 및 체크포인트
**담당 에이전트**: code-reviewer, silent-failure-hunter
**시간**: 30분

#### 작업 내용
1. 전체 테스트 실행
   ```bash
   cd backend && pytest tests/ -v
   ```

2. Agent 검증
   - code-reviewer: Important 이슈 해결 확인
   - silent-failure-hunter: 에러 처리 검증

3. Git commit
   ```bash
   git add backend/app/utils/sql.py backend/app/services/partner.py
   git add backend/app/services/partner_settlement.py backend/app/models/partner.py
   git add backend/alembic/versions/*.py backend/tests/
   git commit -m "fix(security): improve SQL security and transaction handling

   - Add LIKE pattern escaping utility
   - Apply escaping to partner search filters
   - Improve transaction rollback in pay_settlement
   - Move imports to file top
   - Change total_referrals to BigInteger

   Fixes: I-1 (SQL Injection 위험, 85% confidence)
   Fixes: I-2 (트랜잭션 롤백 미흡, 88% confidence)
   Fixes: I-3 (함수 내부 import, 82% confidence)
   Fixes: I-4 (Integer 타입 불일치, 81% confidence)

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   ```

4. 체크포인트 저장
   ```bash
   /holdem-checkpoint "Phase 2 완료: Important 보안 이슈 수정"
   ```

#### 검증
- [ ] 전체 테스트 통과
- [ ] Important 이슈 0건
- [ ] Agent 검증 완료

---

## Phase 3: 코드 품질 개선 📈

**목표**: 장기 유지보수성 향상 (통계 로직 개선)
**예상 시간**: 3-5시간
**의존성**: Phase 2 완료

### Step 3.1: 통계 집계 로직 개선 설계
**담당 에이전트**: code-explorer, code-architect
**시간**: 1시간

#### 작업 내용
1. 현재 문제점 분석
   - `backend/app/api/partner.py:693-707` 확인
   - 일일/월간 통계가 실제로는 누적 통계 반환

2. 개선 방안 설계
   ```
   Option A: 별도 통계 테이블 (권장)
   - partner_daily_stats 테이블 생성
   - Celery로 매일 자정 집계
   - 조회 성능 향상

   Option B: 핸드 히스토리 집계
   - hands, hand_players 테이블 활용
   - 실시간 정확도 높음
   - 조회 성능 낮음 (대량 데이터 시)

   Option C: Materialized View (PostgreSQL)
   - PostgreSQL의 Materialized View 활용
   - 주기적 REFRESH
   ```

3. 최종 선택: **Option A (별도 통계 테이블)**
   - 이유: 성능 + 정확도 균형
   - 트레이드오프: 저장 공간 증가, 배치 작업 필요

#### 검증
- [ ] 설계 문서 작성 완료
- [ ] 아키텍처 다이어그램 작성

---

### Step 3.2: 별도 통계 테이블 마이그레이션
**담당 에이전트**: 없음
**시간**: 1.5시간

#### 작업 내용
1. 모델 작성 (`backend/app/models/partner_stats.py`)
   ```python
   class PartnerDailyStats(Base):
       __tablename__ = "partner_daily_stats"

       id: Mapped[int] = mapped_column(primary_key=True)
       partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id"))
       date: Mapped[date] = mapped_column(Date, nullable=False)

       # 통계 필드
       new_referrals: Mapped[int] = mapped_column(BigInteger, default=0)
       total_bet_amount: Mapped[int] = mapped_column(BigInteger, default=0)
       total_rake: Mapped[int] = mapped_column(BigInteger, default=0)
       commission_amount: Mapped[int] = mapped_column(BigInteger, default=0)

       # 인덱스
       __table_args__ = (
           Index("idx_partner_daily_stats_partner_date", "partner_id", "date"),
           UniqueConstraint("partner_id", "date", name="uq_partner_date"),
       )
   ```

2. Alembic 마이그레이션
   ```bash
   alembic revision -m "create_partner_daily_stats"
   ```

3. 초기 데이터 마이그레이션
   - 기존 파트너 데이터로부터 통계 계산
   - 최근 90일 데이터 마이그레이션

#### 검증
- [ ] 마이그레이션 성공
- [ ] 초기 데이터 정확도 확인
- [ ] 인덱스 성능 확인

---

### Step 3.3: 통계 서비스 리팩토링
**담당 에이전트**: code-reviewer (리뷰 후)
**시간**: 1.5시간

#### 작업 내용
1. `backend/app/services/partner_stats.py` 생성
   ```python
   class PartnerStatsService:
       """파트너 통계 집계 서비스"""

       async def aggregate_daily_stats(self, date: date):
           """특정 날짜의 일일 통계 집계"""
           # hands, hand_players 테이블에서 집계
           # partner_daily_stats에 저장

       async def get_daily_stats(self, partner_id: int, start_date: date, end_date: date):
           """기간별 일일 통계 조회"""
           # partner_daily_stats 조회

       async def get_monthly_stats(self, partner_id: int, year: int, month: int):
           """월간 통계 조회 (일일 통계 합산)"""
   ```

2. `backend/app/api/partner.py` 수정
   - 기존 쿼리 제거
   - PartnerStatsService 사용

3. Celery 배치 작업 추가 (`backend/app/tasks/partner_stats.py`)
   ```python
   @celery_app.task
   def aggregate_partner_daily_stats():
       """매일 자정 파트너 통계 집계"""
       yesterday = date.today() - timedelta(days=1)
       # ...
   ```

#### 검증
- [ ] API 응답 정확도 검증
- [ ] 성능 비교 (Before/After)

---

### Step 3.4: 성능 테스트 및 검증
**담당 에이전트**: test-runner
**시간**: 1시간

#### 작업 내용
1. 부하 테스트 작성 (`backend/tests/performance/test_partner_stats.py`)
   ```python
   @pytest.mark.benchmark
   async def test_daily_stats_performance(benchmark):
       """1000개 파트너, 90일 통계 조회 성능"""
       # Setup: 1000개 파트너, 각 90일 데이터
       # Benchmark: get_daily_stats 호출
       # Assert: 응답 시간 < 100ms
   ```

2. 정확도 테스트
   ```python
   async def test_daily_stats_accuracy():
       """통계 집계 정확도 검증"""
       # Setup: 테스트 데이터 (핸드 히스토리)
       # When: aggregate_daily_stats 실행
       # Then: 집계 결과 = 수동 계산 결과
   ```

#### 검증
- [ ] 성능 테스트 통과 (응답 시간 < 100ms)
- [ ] 정확도 100%
- [ ] 메모리 사용량 확인

---

### Step 3.5: 문서화 및 Phase 3 체크포인트
**담당 에이전트**: 없음
**시간**: 30분

#### 작업 내용
1. API 문서 업데이트
   - OpenAPI 스키마 확인
   - 통계 API 응답 예시 추가

2. CLAUDE.md 업데이트
   ```markdown
   ## 파트너 통계 시스템

   ### 아키텍처
   - `partner_daily_stats` 테이블: 일일 통계 사전 집계
   - Celery 배치: 매일 자정 집계 (KST 기준)
   - 조회 성능: 90일 통계 < 100ms

   ### 주의사항
   - 실시간 통계 아님 (최대 24시간 지연)
   - 과거 데이터 수정 시 재집계 필요
   ```

3. Git commit
   ```bash
   git add backend/app/models/partner_stats.py backend/app/services/partner_stats.py
   git add backend/app/api/partner.py backend/app/tasks/partner_stats.py
   git add backend/alembic/versions/*.py backend/tests/
   git add CLAUDE.md
   git commit -m "feat(partner): improve statistics aggregation with dedicated table

   - Create partner_daily_stats table for pre-aggregated stats
   - Add PartnerStatsService for accurate daily/monthly stats
   - Add Celery task for daily aggregation
   - Improve query performance from O(n) to O(1)
   - Add performance and accuracy tests

   Fixes: I-5 (통계 집계 로직 부정확, 80% confidence)

   Performance:
   - Before: 2-5s for 90-day stats (full table scan)
   - After: <100ms (indexed pre-aggregated data)

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   ```

4. 최종 체크포인트
   ```bash
   /holdem-checkpoint "Phase 3 완료: 코드 품질 개선 완료"
   ```

#### 검증
- [ ] 문서화 완료
- [ ] 전체 테스트 통과
- [ ] 모든 Phase 완료

---

## 🎯 최종 검증 체크리스트

### Critical 이슈
- [ ] C-1: 관리자 권한 체크 적용 (95%)
- [ ] C-2: 라우트 경로 표준화 (92%)

### Important 이슈
- [ ] I-1: SQL Injection 방지 (85%)
- [ ] I-2: 트랜잭션 롤백 개선 (88%)
- [ ] I-3: Import 위치 정리 (82%)
- [ ] I-4: BigInteger 마이그레이션 (81%)
- [ ] I-5: 통계 로직 개선 (80%)

### 테스트
- [ ] 단위 테스트: 352개 + 신규 20개 이상 통과
- [ ] 통합 테스트: 100% 통과
- [ ] 성능 테스트: 통계 API < 100ms
- [ ] 보안 테스트: SQL Injection 시도 차단 확인

### 문서
- [ ] CLAUDE.md 업데이트
- [ ] API 문서 업데이트
- [ ] WORK_STATE.md 최종 상태 기록

---

## 📞 작업 재개 프로토콜

### 토큰 소진 임박 시 (90% 사용)
```bash
# 1. 현재 상태 저장
/holdem-status

# 2. 체크포인트 생성
/holdem-checkpoint "Step X.Y 진행 중: [작업 내용]"

# 3. 다음 계정에서 재개
/holdem-resume
```

### 에러 발생 시
```bash
# 1. 에러 로그 기록
# WORK_STATE.md에 에러 내용 추가

# 2. 인계 문서 생성
/holdem-handoff

# 3. 이슈 등록
# .planning/backend-security-fixes/WORK_STATE.md
# "알려진 이슈/블로커" 섹션에 추가
```

### Step 완료 시
```bash
# 1. 체크리스트 업데이트
# WORK_STATE.md에서 [x] 표시

# 2. 테스트 실행 및 결과 기록

# 3. 다음 Step 시작 또는 체크포인트
```

---

**다음 단계**: WORK_STATE.md 작성
