# 온라인 홀덤 게임 시스템 구현 현황

> 마지막 업데이트: 2026-01-15 (Time Bank 기능 추가)
> 이 문서는 프로젝트의 구현 상태를 추적하는 마스터 문서입니다.

---

## 1. 핵심 게임 로직 (Core Game Logic)

### 게임 상태 머신 (FSM)
- [x] 상태 정의: WAITING → PREFLOP → FLOP → TURN → RIVER → SHOWDOWN
- [x] 상태 전환 트리거 및 유효성 검사
- [x] 파일: `backend/app/game/poker_table.py`

### 덱(Deck) 및 셔플(Shuffle)
- [x] 52장 카드 생성
- [x] 암호화 수준 RNG 셔플 (PokerKit 위임)
- [x] 카드 분배(Deal) 로직
- [x] 파일: `backend/app/engine/core.py`

### 핸드 랭킹 계산기 (Hand Evaluator)
- [x] 7장 중 최상위 5장 판별
- [x] 족보 계산 (Royal Flush ~ High Card)
- [x] 동점자 처리 (Kicker)
- [x] Split Pot 로직
- [x] 파일: `backend/app/game/hand_evaluator.py` (400+ lines)

### 베팅 로직 및 팟 관리
- [x] 액션 처리: Check, Call, Bet, Raise, Fold, All-in
- [x] 사이드 팟(Side Pot) 계산 (PokerKit 자동 처리)
- [x] 레이크(Rake) 계산 - NFND 방식
- [x] 파일: `backend/app/services/rake.py`

---

## 2. 사용자 관리 (User Management)

### 인증 및 인가
- [x] 회원가입/로그인
- [x] JWT 토큰 관리
- [x] bcrypt 비밀번호 해싱
- [ ] 소셜 로그인 연동 (Google, Kakao)
- [ ] 성인 인증 / KYC 모듈
- [x] 파일: `backend/app/services/auth.py`

### 프로필 및 전적 관리
- [x] 닉네임 설정
- [ ] 아바타 설정
- [ ] 통계 지표 (VPIP, PFR 등)
- [x] 기본 전적 데이터

### 자산(Wallet) 시스템
- [x] 게임 머니(칩) 관리
- [x] 트랜잭션 로그 기록
- [x] Redis 분산 락 (동시성 제어)
- [x] 무결성 해시 검증
- [ ] 유료 재화 (골드/다이아)
- [ ] 무료 충전(리필) 로직
- [x] 파일: `backend/app/services/wallet.py`


---

## 3. 방/테이블 관리 (Room/Table Management)

### 로비 및 매치메이킹
- [x] 방 리스트 제공
- [x] 블라인드/인원/바이인 필터링
- [x] 빠른 입장(Quick Join) 자동 배정
- [x] 파일: `backend/app/api/rooms.py`, `backend/app/services/room_matcher.py`

### 방(Room) 객체 구조
- [x] 테이블 속성 (최대 인원, 블라인드, 앤티)
- [x] 참가자(Player) 목록 관리
- [x] 관전자(Spectator) 목록 구조 (SpectatorViewState)
- [x] 턴 제한 시간 설정

### 입장 및 좌석 점유 (Sit-in)
- [x] 방 입장 (WebSocket 연결)
- [x] 자리에 앉기 (seat_player)
- [x] 바이인(Buy-in) 금액 설정
- [ ] 대기열(Waitlist) 관리

### 이탈 및 자리 비움 (Sit-out/Leave)
- [x] 자리 비움 (sit_out)
- [x] 자리 복귀 (sit_in)
- [x] 퇴장 및 정산
- [x] 파일: `backend/app/game/poker_table.py`

---

## 4. 인게임 기능 (In-Game Features)

### 턴 관리 및 타이머
- [x] 플레이어별 제한 시간 (30초)
- [x] 시간 초과 시 자동 폴드
- [x] 타임 뱅크(Time Bank) 기능
- [x] 파일: `backend/app/game/poker_table.py`

### 관전(Spectating) 모드
- [x] SpectatorViewState 모델 정의
- [x] 관전자 핸드 카드 정보 제한
- [ ] 중간 입장 시 테이블 상황 동기화 (Snapshot)
- [x] 파일: `backend/app/engine/state.py`

### 채팅 및 이모티콘
- [x] 전체 채팅
- [ ] 플레이어 전용 채팅 구분
- [ ] 이모티콘 시스템
- [ ] 선물하기 기능
- [x] 파일: `backend/app/ws/handlers/chat.py`

### 핸드 히스토리
- [x] 핸드 기록 저장
- [x] 핸드 요약 정보
- [ ] 리플레이(Replay) 기능
- [x] 파일: `backend/app/models/hand.py`

---

## 5. 네트워킹 및 통신 (Networking)

### 프로토콜 전략
- [x] WebSocket: 실시간 게임 진행
- [x] REST API: 로그인, 방 리스트 등
- [x] 파일: `backend/app/ws/gateway.py`

### 패킷 구조 및 직렬화
- [x] JSON 기반 메시지 포맷
- [x] 39개 이벤트 타입 정의
- [x] 파일: `backend/app/ws/events.py`

### 재접속(Reconnection) 처리
- [x] 연결 끊김 감지
- [x] 30초 내 재접속 시 복구
- [x] 기존 자리 및 핸드 복구
- [x] 파일: `backend/app/ws/manager.py`

### 브로드캐스팅 최적화
- [x] Public Info 전체 전송
- [x] Private Info 개별 전송 (핸드 카드)
- [x] Redis pub/sub 멀티 인스턴스 지원
- [ ] 관전자/플레이어 그룹 분리 전송


---

## 6. 데이터베이스 (Database)

### RDBMS (PostgreSQL)
- [x] SQLAlchemy 2.0 async ORM
- [x] 사용자 계정 테이블
- [x] 자산(칩) 원장
- [x] 트랜잭션 보장
- [x] Alembic 마이그레이션
- [x] 파일: `backend/app/models/`

### In-Memory DB (Redis)
- [x] 실시간 게임 세션 정보
- [x] 방 상태 캐싱
- [x] 사용자 접속 위치
- [x] 턴 타이머 관리
- [x] 파일: `backend/app/services/redis.py`

### Log DB
- [ ] 핸드 히스토리 로그 (MongoDB/Elasticsearch)
- [ ] 부정 행위 분석용 상세 로그

---

## 7. UI/UX (Frontend)

### 로비 인터페이스
- [x] 방 리스트 표시
- [x] 방 필터링 UI
- [x] 보유 자산 표시
- [x] 빠른 입장 버튼
- [x] 파일: `frontend/src/app/lobby/page.tsx`, `frontend/src/components/lobby/QuickJoinButton.tsx`

### 테이블(인게임) 뷰
- [x] 플레이어 자리 배치
- [x] 본인 중앙 하단 로테이션 뷰
- [x] 카드 애니메이션 (Framer Motion)
- [x] 칩 이동 애니메이션
- [x] 팟 수집 애니메이션
- [x] 베팅 조작 UI (슬라이더, 팟 비율 버튼)
- [x] 파일: `frontend/src/app/table/[id]/page.tsx`

### Pmang 스타일 기능
- [x] 카드 스퀴즈 (CardSqueeze)
- [x] 쇼다운 하이라이트 (ShowdownHighlight)
- [x] 팟 비율 버튼 (PotRatioButtons)
- [x] 핸드 랭킹 가이드 (HandRankingGuide)
- [x] 파일: `frontend/src/components/table/pmang/`

### 관전 모드 UI
- [x] 관전 상태 표시
- [x] 빈 자리 "앉기" 버튼
- [ ] 중립적 시각 UI 구성

### 효과 및 피드백
- [x] 자신의 턴 알림 (시각적 하이라이트)
- [x] 승리/패배 연출
- [ ] 진동/사운드 피드백
- [ ] Big Win 이펙트

---

## 8. 보안 및 부정 방지 (Security & Anti-Cheat)

### 무결성 검증
- [x] 서버 사이드 승패 판정
- [x] 서버 사이드 카드 분배
- [x] HMAC 서명 검증
- [ ] 클라이언트 변조 방지 솔루션

### 부정 행위 탐지 (Anti-Collusion)
- [ ] 동일 IP/기기 같은 방 입장 차단
- [ ] 칩 밀어주기(Dumping) 패턴 모니터링
- [ ] 봇(Bot) 탐지 시스템

### 통신 보안
- [x] SSL/TLS 암호화
- [x] Rate Limiting
- [x] Security Headers
- [ ] 패킷 암호화
- [x] 파일: `backend/app/middleware/`

---

## 9. 운영 및 관리 도구 (Backoffice)

### 대시보드
- [ ] CCU(동접자) 실시간 모니터링
- [ ] DAU 통계
- [ ] 매출 현황

### 게임 관리
- [ ] 서버 점검 제어
- [ ] 공지사항 발송
- [ ] 방 강제 종료
- [ ] 채팅 금지 처리

### 사용자 관리 및 CS
- [ ] 유저 상세 로그 조회
- [ ] 핸드 리플레이 기능
- [ ] 제재(Ban) 관리
- [ ] 자산 수동 지급/회수
- [ ] 부정 사용자 의심 리스트


---

## 구현 요약

| 카테고리 | 완료 | 미완료 | 완료율 |
|---------|------|--------|--------|
| 1. 핵심 게임 로직 | 12 | 0 | 100% |
| 2. 사용자 관리 | 9 | 6 | 60% |
| 3. 방/테이블 관리 | 13 | 1 | 93% |
| 4. 인게임 기능 | 9 | 6 | 60% |
| 5. 네트워킹 | 11 | 1 | 92% |
| 6. 데이터베이스 | 9 | 2 | 82% |
| 7. UI/UX | 17 | 3 | 85% |
| 8. 보안 | 6 | 5 | 55% |
| 9. Backoffice | 0 | 12 | 0% |
| **총계** | **86** | **36** | **70%** |

---

## 우선순위 작업 목록 (Priority TODO)

### 높음 (High Priority)
- [ ] Backoffice 대시보드 기본 구현
- [ ] 부정 행위 탐지 시스템 (Anti-Collusion)
- [ ] 봇(Bot) 탐지 시스템

### 중간 (Medium Priority)
- [ ] 타임 뱅크(Time Bank) 기능
- [ ] 소셜 로그인 연동
- [ ] 핸드 리플레이 기능
- [ ] 관전자/플레이어 그룹 분리 전송

### 낮음 (Low Priority)
- [ ] 아바타 설정
- [ ] 이모티콘 시스템
- [ ] 선물하기 기능
- [ ] Big Win 이펙트

---

## 주요 파일 경로

```
backend/
├── app/
│   ├── game/
│   │   ├── poker_table.py    # 핵심 게임 로직, FSM
│   │   ├── hand_evaluator.py # 핸드 평가기
│   │   └── manager.py        # 게임 매니저
│   ├── engine/
│   │   ├── core.py           # PokerKit 통합
│   │   └── state.py          # 불변 상태 모델
│   ├── services/
│   │   ├── auth.py           # 인증 서비스
│   │   ├── wallet.py         # 지갑 서비스
│   │   └── rake.py           # 레이크 계산
│   ├── ws/
│   │   ├── gateway.py        # WebSocket 게이트웨이
│   │   ├── manager.py        # 연결 관리
│   │   └── events.py         # 이벤트 타입 정의
│   └── middleware/
│       ├── rate_limit.py     # Rate Limiting
│       └── security_headers.py
│
frontend/
├── src/
│   ├── app/
│   │   ├── lobby/page.tsx    # 로비 페이지
│   │   └── table/[id]/page.tsx # 테이블 페이지
│   └── components/table/
│       ├── pmang/            # Pmang 스타일 컴포넌트
│       ├── ActionButtons.tsx
│       ├── PlayerSeat.tsx
│       └── ChipAnimation.tsx
```

---

> 새로운 작업이 완료되면 해당 항목을 `[x]`로 체크하고, 새 작업이 추가되면 적절한 섹션에 `[ ]`로 추가하세요.
