# 🚀 프론트엔드 개발자 퀵스타트 가이드

백엔드 서버를 빠르게 실행하는 2가지 방법을 안내합니다.

---

## 📋 사전 요구사항

| 방법 | 필요한 것 |
|------|----------|
| 방법 1 (Docker 전체) | Docker Desktop만 설치 |
| 방법 2 (로컬 개발) | Docker + Python 3.11+ |

---

# 방법 1: Docker로 전체 실행 (가장 쉬움) ⭐

Python 설치 없이 Docker만으로 모든 것을 실행합니다.

### Step 1: 프로젝트 다운로드

```bash
git clone https://github.com/joocy75-hash/Holdem.git
cd Holdem
```

### Step 2: 환경변수 설정

```bash
cp .env.example .env
```

### Step 3: 전체 서비스 실행

```bash
docker-compose -f infra/docker/docker-compose.full.yml up -d
```

### Step 4: 확인

| 서비스 | URL |
|--------|-----|
| API 문서 | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| WebSocket | ws://localhost:8000/ws |

### 종료

```bash
docker-compose -f infra/docker/docker-compose.full.yml down
```

---

# 방법 2: 로컬 개발 환경 (코드 수정 시)

DB는 Docker로, 백엔드는 로컬에서 실행합니다. 코드 수정 시 자동 리로드됩니다.

### Step 1: 프로젝트 다운로드

```bash
git clone https://github.com/joocy75-hash/Holdem.git
cd Holdem
```

### Step 2: 환경변수 설정

```bash
cp .env.example .env
```

### Step 3: DB 실행 (Docker)

```bash
docker-compose -f infra/docker/docker-compose.dev.yml up -d
```

### Step 4: 백엔드 설정

```bash
cd backend

# 가상환경 생성
python -m venv .venv

# 가상환경 활성화
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows

# 패키지 설치
pip install -r requirements.txt

# DB 테이블 생성
alembic upgrade head
```

### Step 5: 서버 실행

```bash
uvicorn app.main:app --reload --port 8000
```

### Step 6: 확인

| 서비스 | URL |
|--------|-----|
| API 문서 | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| WebSocket | ws://localhost:8000/ws |

### 종료

```bash
# 서버: Ctrl+C
# Docker:
docker-compose -f infra/docker/docker-compose.dev.yml down
```

---

## 🔌 프론트엔드 연결 테스트

### 1. 회원가입

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"Test1234","nickname":"tester"}'
```

### 2. 로그인

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"Test1234"}'
```

응답에서 `accessToken`을 복사하세요.

### 3. WebSocket 연결

```javascript
const token = "YOUR_ACCESS_TOKEN";
const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

ws.onopen = () => console.log("Connected!");
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## 📚 상세 문서

| 문서 | 설명 |
|------|------|
| [API_REFERENCE.md](docs/API_REFERENCE.md) | REST API, WebSocket 이벤트 상세 |
| [FRONTEND_INTEGRATION_GUIDE.md](docs/FRONTEND_INTEGRATION_GUIDE.md) | TypeScript 연동 코드 |
| [20-realtime-protocol-v1.md](docs/20-realtime-protocol-v1.md) | WebSocket 프로토콜 |
| [21-error-codes-v1.md](docs/21-error-codes-v1.md) | 에러 코드 목록 |

---

## ❓ 문제 해결

### 포트 충돌

```bash
# 사용 중인 포트 확인
lsof -i :5432   # PostgreSQL
lsof -i :6379   # Redis
lsof -i :8000   # Backend
```

### Docker 컨테이너 확인

```bash
docker ps                          # 실행 중인 컨테이너
docker logs pokerkit-postgres      # PostgreSQL 로그
docker logs pokerkit-redis         # Redis 로그
```

### DB 초기화

```bash
docker-compose -f infra/docker/docker-compose.dev.yml down -v
docker-compose -f infra/docker/docker-compose.dev.yml up -d
cd backend && alembic upgrade head
```
