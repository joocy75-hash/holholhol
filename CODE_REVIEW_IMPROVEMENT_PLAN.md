# 코드 개선 작업 계획서

**작성일**: 2026-01-24
**작성자**: Code Review Agent
**프로젝트**: 홀덤 게임 플랫폼

---

## 📋 목차

1. [개요](#개요)
2. [Critical Issues (즉시 수정 필요)](#critical-issues-즉시-수정-필요)
3. [Important Issues (개선 권장)](#important-issues-개선-권장)
4. [작업 우선순위 및 순서](#작업-우선순위-및-순서)
5. [테스트 계획](#테스트-계획)
6. [완료 체크리스트](#완료-체크리스트)

---

## 개요

### 리뷰 범위
- **백엔드**: `backend/app/` (FastAPI, SQLAlchemy)
- **관리자 페이지**: `admin-frontend/src/` (Next.js 14, TypeScript)

### 발견된 이슈 요약

| 심각도 | 이슈 수 | 주요 내용 |
|--------|--------|----------|
| **Critical** | 3 | SQL Injection, Deprecated API, 아키텍처 문제 |
| **Important** | 5 | N+1 쿼리, 타입 불일치, 민감정보 노출, 월 계산 오류 |

### 작업 목표
1. 보안 취약점 제거 (SQL Injection, 민감정보 노출)
2. 코드 품질 및 유지보수성 향상
3. 타입 안정성 강화 (프론트-백엔드 일관성)
4. 성능 최적화 기반 마련

---

## Critical Issues (즉시 수정 필요)

### Issue #1: SQL Injection 취약점 - 검색어 직접 삽입

**심각도**: 🔴 Critical (신뢰도 95%)
**파일**: `backend/app/services/room.py`
**라인**: 1002

#### 현재 코드
```python
# ❌ 취약한 코드
if search:
    conditions.append(Room.name.ilike(f"%{search}%"))
```

#### 문제점
- `search` 파라미터가 이스케이핑 없이 LIKE 쿼리에 직접 삽입
- 공격자가 `%`, `_` 등 와일드카드 문자를 사용하여 의도하지 않은 검색 결과 조작 가능
- 같은 프로젝트의 `partner.py`에서는 `escape_like_pattern`을 사용하고 있어 일관성 부족

#### 수정 방안
```python
# ✅ 안전한 코드
from app.utils.sql import escape_like_pattern

if search:
    escaped_search = escape_like_pattern(search)
    conditions.append(Room.name.ilike(f"%{escaped_search}%", escape="\\"))
```

#### 작업 단계
1. `room.py` 파일 열기
2. 상단에 `from app.utils.sql import escape_like_pattern` import 추가
3. Line 1002의 검색 로직 수정
4. 동일한 패턴이 있는 다른 검색 기능도 검토 (전체 파일 검색)

#### 영향 범위
- **API**: `/api/v1/rooms` (GET) - 방 목록 검색
- **사용자**: 관리자 및 일반 사용자 (방 검색 기능)

#### 테스트 방법
```bash
# 1. 정상 검색
curl -X GET "http://localhost:8000/api/v1/rooms?search=VIP"

# 2. 와일드카드 공격 시도 (수정 전: 모든 방 노출, 수정 후: 리터럴 검색)
curl -X GET "http://localhost:8000/api/v1/rooms?search=%25"

# 3. 언더스코어 공격
curl -X GET "http://localhost:8000/api/v1/rooms?search=_"
```

#### 예상 결과
- 수정 전: `%` 입력 시 모든 방이 검색됨
- 수정 후: `%` 문자가 포함된 방 이름만 검색됨

---

### Issue #2: Deprecated datetime API 사용

**심각도**: 🔴 Critical (신뢰도 90%)
**파일**: `backend/app/api/announcements.py`
**라인**: 86

#### 현재 코드
```python
# ❌ Deprecated API
now = datetime.utcnow()
```

#### 문제점
- `datetime.utcnow()`는 Python 3.12+에서 deprecated
- Timezone-naive datetime 반환 (타임존 정보 없음)
- 프로젝트의 다른 부분에서는 `datetime.now(timezone.utc)` 사용 (일관성 부족)

#### 수정 방안
```python
# ✅ 권장 방식
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
```

#### 작업 단계
1. `announcements.py` 파일 열기
2. 상단 import 문 수정: `from datetime import datetime, timezone`
3. Line 86의 `datetime.utcnow()` → `datetime.now(timezone.utc)` 변경
4. 전체 코드베이스에서 `utcnow()` 검색하여 일괄 수정

#### 영향 범위
- **파일**: `backend/app/api/announcements.py`
- **추가 검토 필요**: 프로젝트 전체에서 `utcnow()` 사용 여부 확인

#### 테스트 방법
```python
# 단위 테스트
import pytest
from datetime import datetime, timezone

def test_announcement_datetime():
    now = datetime.now(timezone.utc)
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc
```

#### 전체 검색 명령어
```bash
# 코드베이스 전체에서 utcnow() 사용 찾기
grep -r "utcnow()" backend/app/ --include="*.py"
```

---

### Issue #3: 쪽지 시스템 아키텍처 문제

**심각도**: 🟡 Critical/Architectural (신뢰도 92%)
**파일**: `backend/app/api/messages.py`
**라인**: 76-108

#### 현재 코드
```python
# ❌ 게임 백엔드가 admin DB 테이블을 직접 쿼리
base_query = """
    SELECT id, title, content, is_read, read_at, created_at
    FROM messages
    WHERE recipient_id = :user_id
"""
# 코드 주석: "admin DB에 연결해야 하지만, 간단히 구현"
```

#### 문제점
- 게임 백엔드(`backend/`)가 admin DB의 `messages` 테이블을 직접 접근
- 서비스 분리 원칙(Separation of Concerns) 위배
- 현재는 파라미터 바인딩으로 SQL Injection은 방지되나, 아키텍처적으로 부적절

#### 수정 방안 (옵션)

**옵션 A: 별도 마이크로서비스 (권장)**
```
게임 백엔드 → [HTTP API] → 메시지 서비스 → Admin DB
```
- 장점: 완전한 서비스 분리, 확장성 우수
- 단점: 복잡도 증가, 네트워크 오버헤드

**옵션 B: 공유 데이터베이스 뷰 (중간)**
```sql
-- 게임 DB에 읽기 전용 뷰 생성
CREATE VIEW game_user_messages AS
SELECT id, recipient_id, title, content, is_read, read_at, created_at
FROM admin_db.messages;
```
- 장점: 구현 간단, 성능 우수
- 단점: 데이터베이스 간 커플링

**옵션 C: 데이터 복제 (캐시)**
```
Admin DB (쓰기) → Redis/Game DB (읽기 전용 복제)
```
- 장점: 읽기 성능 최고
- 단점: 데이터 일관성 문제, 복제 지연

#### 작업 단계 (옵션 B 기준)
1. DBA와 협의하여 크로스 DB 뷰 생성 가능 여부 확인
2. `messages` 테이블을 게임 DB에 뷰로 생성
3. SQLAlchemy 모델 추가 (`backend/app/models/message.py`)
4. Raw SQL 제거 후 ORM 쿼리로 변경
5. 통합 테스트

#### 의사결정 필요 사항
- **질문**: 쪽지 시스템이 게임 백엔드에 속해야 하는가, 아니면 별도 서비스여야 하는가?
- **고려사항**: 향후 확장성, 운영 복잡도, 팀 리소스

---

## Important Issues (개선 권장)

### Issue #4: N+1 쿼리 문제 - 파트너 통계 집계

**심각도**: 🟠 Important (신뢰도 85%)
**파일**: `backend/app/services/partner_stats.py`
**라인**: 75-137

#### 현재 코드
```python
# ❌ N+1 쿼리 발생
for partner in partners:
    # 쿼리 1: 통계 집계
    stats_query = (...)
    stats_result = await self.db.execute(stats_query)

    # 쿼리 2: 기존 레코드 조회
    existing = await self.db.execute(
        select(PartnerDailyStats)
        .where(PartnerDailyStats.partner_id == partner.id)
        .where(PartnerDailyStats.date == target_date)
    )

    # 쿼리 3: INSERT/UPDATE
    if existing_record:
        await self.db.execute(update(...))
    else:
        await self.db.execute(insert(...))
```

#### 문제점
- 파트너 N명 → 최소 2N~3N개의 개별 쿼리 실행
- 파트너가 100명이면 200~300개 쿼리 발생
- 대규모 배치 작업 시 성능 저하

#### 수정 방안

**단계 1: 배치 조회**
```python
# ✅ 모든 파트너의 기존 레코드를 한 번에 조회
partner_ids = [p.id for p in partners]
existing_records = await self.db.execute(
    select(PartnerDailyStats)
    .where(PartnerDailyStats.partner_id.in_(partner_ids))
    .where(PartnerDailyStats.date == target_date)
)
existing_dict = {r.partner_id: r for r in existing_records.scalars()}
```

**단계 2: Bulk Upsert (PostgreSQL 14+)**
```python
# ✅ INSERT ... ON CONFLICT UPDATE 사용
from sqlalchemy.dialects.postgresql import insert

stmt = insert(PartnerDailyStats).values(batch_data)
stmt = stmt.on_conflict_do_update(
    index_elements=['partner_id', 'date'],
    set_={
        'new_referrals': stmt.excluded.new_referrals,
        'total_bet_amount': stmt.excluded.total_bet_amount,
        # ...
        'updated_at': func.now()
    }
)
await self.db.execute(stmt)
```

#### 작업 단계
1. `partner_stats.py` 백업
2. `aggregate_daily_stats` 메서드 리팩토링
3. 기존 레코드 배치 조회 로직 추가
4. Bulk upsert 구현
5. 단위 테스트 작성 (파트너 10명, 100명 시나리오)
6. 성능 비교 측정

#### 성능 개선 예상치
- **Before**: 100명 파트너 → 200~300 쿼리, 2~5초
- **After**: 100명 파트너 → 2~3 쿼리, <500ms

#### 우선순위
- CLAUDE.md에 따라 "베타 테스트 전"에 최적화하면 됨
- 현재 파트너 수가 적으면 당장 시급하지 않음

---

### Issue #5: 월간 통계 계산 오류

**심각도**: 🟠 Important (신뢰도 84%)
**파일**: `backend/app/api/partner.py`
**라인**: 356-360

#### 현재 코드
```python
# ❌ 30일 단위로 월 계산 (부정확)
for i in range(months):
    target_date = now - timedelta(days=i * 30)
    year = target_date.year
    month = target_date.month
```

#### 문제점
- `timedelta(days=30)`으로 월을 계산하면 실제 달력 월과 불일치
- 예: 2026-01-24에서 2개월 전 = 60일 전 = 2025-11-25 (실제 2025-11-01이어야 함)
- 2월(28일), 31일 월 등 고려 안 됨

#### 수정 방안
```python
# ✅ 정확한 월 계산
from dateutil.relativedelta import relativedelta

for i in range(months):
    target_date = now - relativedelta(months=i)
    year = target_date.year
    month = target_date.month
```

#### 작업 단계
1. `requirements.txt`에 `python-dateutil` 추가 (이미 설치되어 있을 가능성 높음)
2. `partner.py` 상단에 `from dateutil.relativedelta import relativedelta` import
3. Line 356-360 수정
4. 단위 테스트 작성 (경계 케이스: 1월, 2월, 12월)

#### 테스트 케이스
```python
# 단위 테스트
def test_monthly_stats_calculation():
    # 2026-01-31 기준
    now = datetime(2026, 1, 31, tzinfo=timezone.utc)

    # 1개월 전 = 2025-12-31
    one_month_ago = now - relativedelta(months=1)
    assert one_month_ago.month == 12
    assert one_month_ago.year == 2025

    # 2개월 전 = 2025-11-30 (11월은 30일까지)
    two_months_ago = now - relativedelta(months=2)
    assert two_months_ago.month == 11
    assert two_months_ago.day == 30
```

#### 영향 범위
- **API**: `/api/v1/partner/stats/monthly`
- **사용자**: 파트너 포털의 월간 통계 조회

---

### Issue #6: 타입 불일치 (프론트엔드-백엔드)

**심각도**: 🟠 Important (신뢰도 80%)
**파일**: `admin-frontend/src/lib/partner-portal-api.ts`
**라인**: 100-104

#### 현재 코드

**백엔드** (`backend/app/api/partner.py`):
```python
class PartnerDailyStatsResponse(BaseModel):
    items: List[DailyStatItem]
    period_start: datetime
    period_end: datetime
```

**프론트엔드** (`admin-frontend/src/lib/partner-portal-api.ts`):
```typescript
getDailyStats: async (
    token: string,
    days: number = 30
  ): Promise<PartnerDailyStat[]> => {  // ❌ 배열만 기대
```

#### 문제점
- 백엔드는 `{ items: [], period_start, period_end }` 객체 반환
- 프론트엔드는 배열만 기대
- 런타임 에러 발생 가능 (`.map()` 호출 시 undefined)

#### 수정 방안

**옵션 A: 프론트엔드 타입 수정 (권장)**
```typescript
// ✅ 백엔드 응답 구조와 일치
interface PartnerDailyStatsResponse {
  items: PartnerDailyStat[]
  period_start: string  // ISO 8601 datetime
  period_end: string
}

getDailyStats: async (
  token: string,
  days: number = 30
): Promise<PartnerDailyStatsResponse> => {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/partner/stats/daily?days=${days}`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.json()
}
```

**옵션 B: 백엔드 응답 간소화**
```python
# ✅ 배열만 반환 (기간 정보는 헤더로)
@router.get("/stats/daily")
async def get_daily_stats(days: int = 30):
    # ...
    return items  # List[DailyStatItem]만 반환
```

#### 작업 단계 (옵션 A)
1. `admin-frontend/src/types/index.ts`에 `PartnerDailyStatsResponse` 타입 정의
2. `partner-portal-api.ts`의 `getDailyStats` 반환 타입 수정
3. 호출하는 컴포넌트 수정 (`response.items` 접근)
4. 타입스크립트 컴파일 확인 (`npm run build`)

#### 영향 범위
- **API**: `/api/v1/partner/stats/daily`, `/api/v1/partner/stats/monthly`
- **컴포넌트**: `admin-frontend/src/app/partner/dashboard/page.tsx`

---

### Issue #7: 민감 정보 노출 - 사용자 잔액

**심각도**: 🟠 Important (신뢰도 81%)
**파일**: `backend/app/services/room.py`
**라인**: 284-288

#### 현재 코드
```python
# ❌ 사용자 잔액이 에러 메시지에 노출
if user.balance < buy_in:
    raise RoomError(
        "INSUFFICIENT_BALANCE",
        f"Insufficient balance. Required: {buy_in}, Available: {user.balance}",
        {"required": buy_in, "available": user.balance},
    )
```

#### 문제점
- 사용자의 정확한 잔액이 API 응답에 포함
- 공격자가 타 사용자의 잔액을 추론할 가능성
- 예: 여러 방에 입장 시도하며 `available` 값 확인

#### 수정 방안
```python
# ✅ 민감 정보는 로그에만 기록
import logging

logger = logging.getLogger(__name__)

if user.balance < buy_in:
    # 상세 정보는 서버 로그에만
    logger.warning(
        f"Insufficient balance for user {user.id}. "
        f"Required: {buy_in}, Available: {user.balance}"
    )

    # 클라이언트에는 간단한 메시지만
    raise RoomError(
        "INSUFFICIENT_BALANCE",
        "잔액이 부족합니다.",
        {"required": buy_in}  # 필요 금액만 노출
    )
```

#### 작업 단계
1. `room.py` 상단에 `logger = logging.getLogger(__name__)` 추가
2. Line 284-288의 에러 처리 수정
3. 유사한 패턴 검색 (잔액, 개인정보 노출)
4. 통합 테스트

#### 보안 영향 평가
- **위험도**: Medium (정보 노출만, 자금 탈취는 아님)
- **영향 범위**: 방 입장 API
- **추가 검토**: 출금, 베팅 등 다른 금액 관련 API도 확인 필요

---

### Issue #8: CSRF 보호 (향후 고려사항)

**심각도**: 🟡 Low/Informational (신뢰도 82%)
**파일**: `admin-frontend/src/lib/api.ts`

#### 현재 상태
- JWT Bearer 토큰을 `Authorization` 헤더로 전송
- CSRF 공격에 대해 **현재는 안전** (Bearer 토큰은 쿠키가 아니므로)

#### 향후 고려사항
만약 쿠키 기반 세션 인증으로 변경 시:
```typescript
// CSRF 토큰 추가 예시
headers: {
  'Authorization': `Bearer ${token}`,
  'X-CSRF-Token': getCsrfToken()  // 쿠키 기반 인증 시 필요
}
```

#### 작업 필요 여부
- **현재**: 작업 불필요
- **조건**: 인증 방식 변경 시에만 구현

---

## 작업 우선순위 및 순서

### Phase 1: 보안 취약점 제거 (즉시)

| 순서 | 이슈 | 예상 난이도 | 의존성 |
|------|------|------------|--------|
| 1 | #1: SQL Injection (room.py) | ⭐ 쉬움 | 없음 |
| 2 | #2: Deprecated datetime | ⭐ 쉬움 | 없음 |
| 3 | #7: 민감정보 노출 | ⭐⭐ 보통 | 없음 |

### Phase 2: 타입 안정성 및 정확성 (단기)

| 순서 | 이슈 | 예상 난이도 | 의존성 |
|------|------|------------|--------|
| 4 | #5: 월간 통계 계산 오류 | ⭐ 쉬움 | 없음 |
| 5 | #6: 타입 불일치 | ⭐⭐ 보통 | 없음 |

### Phase 3: 성능 및 아키텍처 (중장기)

| 순서 | 이슈 | 예상 난이도 | 의존성 |
|------|------|------------|--------|
| 6 | #4: N+1 쿼리 | ⭐⭐⭐ 어려움 | 베타 테스트 전 |
| 7 | #3: 쪽지 시스템 아키텍처 | ⭐⭐⭐⭐ 매우 어려움 | 아키텍처 의사결정 필요 |

---

## 테스트 계획

### 단위 테스트

```bash
# 1. SQL 이스케이핑 테스트
cd backend
pytest tests/services/test_room.py::test_search_with_special_chars -v

# 2. Datetime 타임존 테스트
pytest tests/api/test_announcements.py::test_datetime_timezone -v

# 3. 월간 통계 계산 테스트
pytest tests/api/test_partner.py::test_monthly_stats_calculation -v
```

### 통합 테스트

```bash
# 1. Room 검색 API
curl -X GET "http://localhost:8000/api/v1/rooms?search=%25" \
  -H "Authorization: Bearer <token>"

# 2. 파트너 통계 API
curl -X GET "http://localhost:8001/api/v1/partner/stats/monthly?months=3" \
  -H "Authorization: Bearer <partner-token>"
```

### 보안 테스트

```bash
# 1. SQL Injection 시도 (수정 후 실패해야 함)
curl -X GET "http://localhost:8000/api/v1/rooms?search=%25%27%20OR%201=1--"

# 2. 잔액 정보 노출 확인 (수정 후 잔액 미포함)
curl -X POST "http://localhost:8000/api/v1/rooms/join" \
  -H "Authorization: Bearer <token>" \
  -d '{"room_id": "uuid", "buy_in": 999999999}'
```

---

## 완료 체크리스트

### Phase 1: 보안 취약점 제거

- [ ] **Issue #1: SQL Injection**
  - [ ] `room.py`에 `escape_like_pattern` import 추가
  - [ ] 검색 로직 수정 (Line 1002)
  - [ ] 전체 코드베이스에서 유사 패턴 검색 및 수정
  - [ ] 단위 테스트 작성 및 통과
  - [ ] 통합 테스트 수행

- [ ] **Issue #2: Deprecated datetime**
  - [ ] `announcements.py` import 문 수정
  - [ ] `utcnow()` → `now(timezone.utc)` 변경
  - [ ] 전체 코드베이스 검색 (`grep -r "utcnow()"`)
  - [ ] 모든 파일 일괄 수정
  - [ ] 단위 테스트 작성 및 통과

- [ ] **Issue #7: 민감정보 노출**
  - [ ] `room.py`에 logger 추가
  - [ ] 에러 메시지 수정 (잔액 제거)
  - [ ] 서버 로그 추가
  - [ ] 다른 금액 관련 API 검토 (출금, 베팅 등)
  - [ ] 통합 테스트 수행

### Phase 2: 타입 안정성 및 정확성

- [ ] **Issue #5: 월간 통계 계산**
  - [ ] `requirements.txt`에 `python-dateutil` 확인/추가
  - [ ] `partner.py`에 `relativedelta` import
  - [ ] 월 계산 로직 수정 (Line 356-360)
  - [ ] 경계 케이스 단위 테스트 (1월, 2월, 12월)
  - [ ] 기존 통계 재계산 필요 여부 확인

- [ ] **Issue #6: 타입 불일치**
  - [ ] 백엔드-프론트엔드 응답 구조 확인
  - [ ] `types/index.ts`에 `PartnerDailyStatsResponse` 타입 정의
  - [ ] `partner-portal-api.ts` 반환 타입 수정
  - [ ] 호출 컴포넌트 수정 (`response.items` 접근)
  - [ ] 타입스크립트 빌드 확인 (`npm run build`)

### Phase 3: 성능 및 아키텍처

- [ ] **Issue #4: N+1 쿼리**
  - [ ] `partner_stats.py` 백업
  - [ ] 기존 레코드 배치 조회 구현
  - [ ] Bulk upsert 구현 (PostgreSQL `ON CONFLICT`)
  - [ ] 성능 비교 테스트 (10명, 100명)
  - [ ] 프로덕션 배포 (베타 테스트 전)

- [ ] **Issue #3: 쪽지 시스템 아키텍처**
  - [ ] 아키텍처 옵션 검토 (마이크로서비스 vs 공유 뷰 vs 복제)
  - [ ] 팀 회의 및 의사결정
  - [ ] 선택한 옵션에 따라 구현
  - [ ] 마이그레이션 계획 수립
  - [ ] 통합 테스트 및 배포

### 최종 검증

- [ ] 전체 단위 테스트 실행 (`pytest tests/ -v`)
- [ ] 전체 통합 테스트 실행
- [ ] 코드 커버리지 확인 (목표: 80%+)
- [ ] 보안 스캔 도구 실행 (`bandit backend/app/`)
- [ ] 타입 체크 (`mypy backend/app/`)
- [ ] 린트 검사 (`flake8 backend/app/`)
- [ ] 프론트엔드 빌드 (`npm run build`)
- [ ] 스테이징 환경 배포 및 검증

---

## 참고 자료

### 내부 문서
- [CLAUDE.md](./CLAUDE.md) - 프로젝트 코딩 가이드라인
- [파트너 통계 시스템](./CLAUDE.md#파트너-통계-시스템)

### 외부 자료
- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [Python datetime best practices](https://docs.python.org/3/library/datetime.html#aware-and-naive-objects)
- [PostgreSQL Bulk Insert/Update](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)

---

**작업 시작 전 확인사항**:
1. Git 브랜치 생성 (`git checkout -b fix/code-review-improvements`)
2. 백업 생성 (주요 파일)
3. 개발 환경 가상환경 활성화
4. 테스트 데이터베이스 준비

**작업 완료 후**:
1. Pull Request 생성
2. 코드 리뷰 요청
3. 머지 후 스테이징 배포
4. 프로덕션 배포 일정 수립
