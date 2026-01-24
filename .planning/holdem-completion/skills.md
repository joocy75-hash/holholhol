# Holdem 프로젝트 Skills & 운영 가이드

> **버전**: 1.0.0
> **작성일**: 2026-01-24
> **목적**: 작업 중단/재개, 세션 동기화, Sub-Agent 활용 가이드

---

## 🔄 1. Check-pointing (작업 맥락 복구)

### 1.1 체크포인트 저장 규칙

**매 단계 완료 시 반드시 수행**:

```markdown
## Checkpoint: [Phase]-[Step] 완료
**시간**: YYYY-MM-DD HH:MM KST
**작업자**: [계정/세션 ID]

### 완료 내용
- [x] 체크리스트 항목 1
- [x] 체크리스트 항목 2

### 변경된 파일
1. `path/to/file1.py` - 설명
2. `path/to/file2.tsx` - 설명

### 테스트 결과
- 단위 테스트: X passed, 0 failed
- 렌더링 확인: ✅

### 다음 단계
- Step X.X.X: [설명]

### 커밋 정보
- Hash: [abc1234]
- Message: "[Phase X] Step X.X 완료"
```

### 1.2 체크포인트 복구 절차

새 세션/계정에서 작업 재개 시:

```bash
# 1. 최신 상태 확인
cat .planning/holdem-completion/work-plan.md | grep -A 20 "Current State"

# 2. Git 상태 확인
git log --oneline -5
git status

# 3. 마지막 체크포인트 확인
cat .planning/holdem-completion/checkpoints/latest.md

# 4. 테스트 실행으로 상태 검증
cd backend && pytest tests/ -v --tb=short
cd ../frontend && npm run build
```

### 1.3 자동 체크포인트 스크립트

```bash
#!/bin/bash
# .planning/scripts/checkpoint.sh

PHASE=$1
STEP=$2
MESSAGE=$3
TIMESTAMP=$(date "+%Y-%m-%d %H:%M KST")

cat > .planning/holdem-completion/checkpoints/latest.md << EOF
## Checkpoint: ${PHASE}-${STEP}
**시간**: ${TIMESTAMP}

### 요약
${MESSAGE}

### Git 상태
$(git status --short)

### 최근 커밋
$(git log --oneline -3)
EOF

echo "✅ Checkpoint saved: ${PHASE}-${STEP}"
```

---

## 👥 2. 복수 계정 세션 동기화

### 2.1 세션 전환 프로토콜

```
┌─────────────────────────────────────────────────────────────┐
│                    세션 전환 플로우                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  계정 A (토큰 소진)                                          │
│       │                                                     │
│       ▼                                                     │
│  1. Current State Summary 작성                              │
│       │                                                     │
│       ▼                                                     │
│  2. Git commit & push                                       │
│       │                                                     │
│       ▼                                                     │
│  3. WORK_STATE.md 업데이트                                  │
│       │                                                     │
│       ▼                                                     │
│  ═══════════════════════════════════════════════════════    │
│       │                                                     │
│       ▼                                                     │
│  계정 B (새 세션)                                            │
│       │                                                     │
│       ▼                                                     │
│  1. git pull                                                │
│       │                                                     │
│       ▼                                                     │
│  2. WORK_STATE.md 읽기                                      │
│       │                                                     │
│       ▼                                                     │
│  3. /holdem-resume 명령 실행                                │
│       │                                                     │
│       ▼                                                     │
│  4. 작업 재개                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 WORK_STATE.md 형식

```markdown
# 홀덤 완성 프로젝트 작업 상태

> **마지막 업데이트**: YYYY-MM-DD HH:MM KST
> **현재 작업자**: [계정명]
> **토큰 사용량**: X/200000 (X%)

## 현재 Phase/Step
- **Phase**: P0 - Core Auth
- **Step**: 0.2.3 - auth.py 수정 중
- **진행률**: 45%

## 진행 중인 작업
```
파일: backend/app/services/auth.py
위치: Line 150-180
내용: login() 메서드에서 email → username 전환 중
상태: 함수 시그니처 변경 완료, 내부 로직 수정 필요
```

## 다음 할 일
1. auth.py Line 165-170 수정
2. 단위 테스트 실행
3. Step 0.2.4로 이동

## 블로커
- 없음

## 계정 전환 로그
| 시간 | 이전 | 새 계정 | Phase/Step |
|------|-----|--------|-----------|
| 12:00 | A | B | P0/0.2.3 |
```

### 2.3 환경 설정 동기화

```bash
# 새 계정에서 환경 설정
# .planning/scripts/sync-env.sh

#!/bin/bash

echo "🔄 환경 동기화 시작..."

# 1. Git 최신화
git fetch origin
git pull origin main

# 2. 의존성 설치
echo "📦 Backend 의존성..."
cd backend && pip install -r requirements.txt

echo "📦 Frontend 의존성..."
cd ../frontend && npm install

echo "📦 Admin Frontend 의존성..."
cd ../admin-frontend && npm install

# 3. DB 마이그레이션 확인
echo "🗄️ DB 마이그레이션 확인..."
cd ../backend && alembic current

# 4. 서비스 상태 확인
echo "🔍 서비스 상태..."
nc -zv localhost 5432 && echo "✅ PostgreSQL"
nc -zv localhost 6379 && echo "✅ Redis"

echo "✅ 환경 동기화 완료!"
```

---

## 🤖 3. Sub-Agent 호출 규약

### 3.1 사용 가능한 Sub-Agent 유형

| Agent 유형 | 용도 | 호출 시점 |
|-----------|------|----------|
| `code-explorer` | 코드베이스 분석 | 구조 파악 필요 시 |
| `code-architect` | 아키텍처 설계 | 새 기능 설계 시 |
| `code-reviewer` | 코드 리뷰 | PR 전, 단계 완료 후 |
| `silent-failure-hunter` | 에러 핸들링 검증 | 트랜잭션 코드 작성 후 |
| `Bash` | 명령 실행 | 빌드, 테스트 실행 |
| `Explore` | 코드베이스 탐색 | 파일 검색 필요 시 |

### 3.2 Sub-Agent 호출 패턴

#### DB 마이그레이션 작업
```
Task: gsd-executor
Prompt: |
  Phase P0, Step 0.1: DB 스키마 마이그레이션 실행

  목표:
  - users 테이블에 username 컬럼 추가
  - 기존 데이터 마이그레이션

  작업 순서:
  1. alembic revision 생성
  2. upgrade 함수 작성
  3. 마이그레이션 실행
  4. 검증 쿼리 실행

  완료 조건:
  - 모든 users 레코드에 username 존재
  - UNIQUE 제약조건 확인
```

#### 프론트엔드 CSS 작업
```
Task: code-architect
Prompt: |
  회원가입 폼 UI 확장 설계

  요구사항:
  - USDT 지갑 주소 입력란 추가
  - TRC20/ERC20 선택 라디오 버튼
  - 주소 유효성 검증 표시

  기존 스타일:
  - glass-card, glass-input 클래스 사용
  - Framer Motion 애니메이션 적용

  산출물:
  - 컴포넌트 구조 제안
  - 스타일 가이드
```

#### 이벤트 로직 구현
```
Task: code-architect
Prompt: |
  출석체크 이벤트 시스템 설계

  요구사항:
  - 일일 1회 출석체크
  - 연속 출석 보너스 (7일, 30일)
  - 보상 자동 지급

  고려사항:
  - 타임존 처리 (KST 기준)
  - 중복 체크인 방지
  - 보상 트랜잭션 원자성

  산출물:
  - DB 스키마
  - API 엔드포인트
  - 서비스 로직 설계
```

### 3.3 Sub-Agent 결과 처리

```markdown
## Sub-Agent 결과 템플릿

### Agent: [agent-type]
### Task: [task-description]
### 실행 시간: YYYY-MM-DD HH:MM

#### 결과 요약
- 성공/실패: [결과]
- 주요 발견사항: [내용]

#### 생성된 파일
1. `path/to/file1` - [설명]
2. `path/to/file2` - [설명]

#### 후속 조치
- [ ] 코드 리뷰 필요
- [ ] 테스트 작성 필요
- [ ] 문서 업데이트 필요

#### 이슈/경고
- [이슈 내용]
```

---

## 🚨 4. 토큰 고갈 대처 (Emergency Protocol)

### 4.1 토큰 사용량 모니터링

```
토큰 사용 임계값:
├── 🟢 0-50%: 정상 진행
├── 🟡 50-75%: 체크포인트 빈도 증가
├── 🟠 75-90%: 현재 Step 완료 후 전환 준비
└── 🔴 90%+: 즉시 상태 저장 및 전환
```

### 4.2 긴급 상태 저장 템플릿

```markdown
# 🚨 Emergency Handoff - 토큰 고갈

**시간**: YYYY-MM-DD HH:MM KST
**토큰**: 95% 사용

## 즉시 저장 정보

### 현재 작업
- 파일: [경로]
- 라인: [번호]
- 작업: [설명]

### 미완료 변경사항
```diff
// 작업 중인 코드 diff
```

### 다음 세션 첫 명령
```bash
# 1. 상태 복구
cat .planning/holdem-completion/EMERGENCY_HANDOFF.md

# 2. Git stash 확인 (있다면)
git stash list

# 3. 작업 재개
[구체적 명령]
```

### 컨텍스트 키워드
- [중요 변수명]
- [함수명]
- [관련 테스트]
```

### 4.3 세션 종료 전 필수 체크리스트

```markdown
## 세션 종료 전 체크리스트

- [ ] 현재 변경사항 git add/commit
- [ ] WORK_STATE.md 업데이트
- [ ] 체크포인트 파일 생성
- [ ] work-plan.md 진행률 업데이트
- [ ] 테스트 상태 기록
- [ ] 다음 세션 시작 명령 작성
```

---

## 📁 5. 파일 구조

```
.planning/
└── holdem-completion/
    ├── work-plan.md           # 마스터 작업 계획
    ├── skills.md              # 이 파일
    ├── WORK_STATE.md          # 실시간 작업 상태
    ├── checkpoints/
    │   ├── latest.md          # 최신 체크포인트
    │   ├── P0-0.1.md          # Phase별 체크포인트
    │   ├── P0-0.2.md
    │   └── ...
    ├── scripts/
    │   ├── checkpoint.sh      # 체크포인트 저장
    │   ├── sync-env.sh        # 환경 동기화
    │   └── resume.sh          # 작업 재개
    └── sub-agent-logs/
        ├── 2026-01-24-db-migration.md
        └── ...
```

---

## 🔧 6. 슬래시 명령어 (Slash Commands)

### 프로젝트 전용 명령어

| 명령어 | 설명 |
|--------|------|
| `/holdem-status` | 현재 작업 상태 확인 |
| `/holdem-resume` | 작업 재개 (컨텍스트 복구) |
| `/holdem-checkpoint` | 체크포인트 저장 |
| `/holdem-handoff` | 계정 전환 준비 |

### 명령어 구현 위치
```
.claude/commands/
├── holdem-status.md
├── holdem-resume.md
├── holdem-checkpoint.md
└── holdem-handoff.md
```

---

## 📊 7. 진행 상황 대시보드

### 실시간 진행률 표시
```
┌─────────────────────────────────────────────────────────────┐
│  Holdem Completion Progress                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  P0: Core Auth        ████████████░░░░░░░░  60%            │
│  P1: User Mapping     ░░░░░░░░░░░░░░░░░░░░   0%            │
│  P2: UI/UX Extension  ░░░░░░░░░░░░░░░░░░░░   0%            │
│  P3: Event System     ░░░░░░░░░░░░░░░░░░░░   0%            │
│  ─────────────────────────────────────────────             │
│  Overall              ███░░░░░░░░░░░░░░░░░  15%            │
│                                                             │
│  Current: P0-Step 0.2.3                                     │
│  Last Update: 2026-01-24 12:30 KST                         │
│  Active Session: Claude-A                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

**마지막 업데이트**: 2026-01-24 12:00 KST
