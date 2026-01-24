#!/bin/bash

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 개발 서버 시작 스크립트${NC}"
echo "================================"

# 백그라운드 프로세스 ID 저장
PIDs=()

# 1. 백엔드 (port 8000)
echo -e "${YELLOW}1️⃣  백엔드 FastAPI 시작 (port 8000)...${NC}"
cd backend
pip install -q -r requirements.txt 2>/dev/null || true
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &
PIDs+=($!)
sleep 3

# 2. 관리자 백엔드 (port 8001)
echo -e "${YELLOW}2️⃣  어드민 백엔드 FastAPI 시작 (port 8001)...${NC}"
cd ../admin-backend
pip install -q -r requirements.txt 2>/dev/null || true
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload > /tmp/admin-backend.log 2>&1 &
PIDs+=($!)
sleep 3

# 3. 프론트엔드 (port 3000)
echo -e "${YELLOW}3️⃣  사용자 프론트엔드 Next.js 시작 (port 3000)...${NC}"
cd ../frontend
npm install > /dev/null 2>&1 || true
npm run dev > /tmp/frontend.log 2>&1 &
PIDs+=($!)
sleep 3

# 4. 어드민 프론트엔드 (port 3001)
echo -e "${YELLOW}4️⃣  관리자 프론트엔드 Next.js 시작 (port 3001)...${NC}"
cd ../admin-frontend
npm install > /dev/null 2>&1 || true
npm run dev > /tmp/admin-frontend.log 2>&1 &
PIDs+=($!)
sleep 3

echo ""
echo -e "${GREEN}✅ 모든 서버가 시작되었습니다!${NC}"
echo "================================"
echo ""
echo -e "${GREEN}🌐 접속 주소:${NC}"
echo "  • 게임 서버: http://localhost:8000"
echo "  • 게임 프론트: http://localhost:3000"
echo "  • 어드민 API: http://localhost:8001"
echo "  • 어드민 프론트: http://localhost:3001"
echo ""
echo -e "${GREEN}📊 API 문서:${NC}"
echo "  • 게임 API: http://localhost:8000/docs"
echo "  • 어드민 API: http://localhost:8001/docs"
echo ""
echo -e "${YELLOW}📝 로그 파일:${NC}"
echo "  • 백엔드: tail -f /tmp/backend.log"
echo "  • 어드민백엔드: tail -f /tmp/admin-backend.log"
echo "  • 프론트엔드: tail -f /tmp/frontend.log"
echo "  • 어드민프론트: tail -f /tmp/admin-frontend.log"
echo ""
echo -e "${YELLOW}⏹️  모든 서버 종료: Ctrl+C${NC}"

# 대기
wait

# 정리
for PID in "${PIDs[@]}"; do
    kill $PID 2>/dev/null || true
done
