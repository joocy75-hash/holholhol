# Implementation Plan: Admin Dashboard

## Overview

관리자 대시보드는 메인 홀덤 게임과 완전히 분리된 독립 애플리케이션으로 구현됩니다.
USDT(TRC-20) 입출금 관리 및 KRW 환산 기능을 포함합니다.

**예상 총 개발 기간**: 8-10주
**팀 구성**: Frontend 2명, Backend 2명, DevOps 1명, QA 1명

---

## Phase 1: 프로젝트 설정 및 인프라 (Week 1)

- [x] 1. Admin 프로젝트 초기 설정
  - [x] 1.1 Admin Frontend 프로젝트 생성 (Next.js 14)
    - `admin-frontend/` 디렉토리 생성
    - shadcn/ui, Tailwind CSS, Zustand 설정
    - _Role: Frontend Developer_
    - _Checkpoint: `npm run dev` 실행 확인_
    - _Requirements: 11.1_

  - [x] 1.2 Admin Backend 프로젝트 생성 (FastAPI)
    - `admin-backend/` 디렉토리 생성
    - SQLAlchemy 2.0, Pydantic v2 설정
    - _Role: Backend Developer_
    - _Checkpoint: `/health` 엔드포인트 응답 확인_
    - _Requirements: 11.1_

  - [x] 1.3 Admin 전용 데이터베이스 스키마 설정
    - AdminUser, AuditLog, Announcement 테이블 생성
    - Alembic 마이그레이션 설정
    - _Role: Backend Developer_
    - _Checkpoint: 마이그레이션 성공 및 테이블 생성 확인_
    - _Requirements: 11.2_

  - [x] 1.4 Docker 및 배포 환경 구성
    - admin-frontend, admin-backend Dockerfile 작성
    - docker-compose.admin.yml 작성
    - _Role: DevOps_
    - _Checkpoint: `docker-compose up` 으로 전체 스택 실행 확인_
    - _Requirements: 11.5_

- [x] 2. Checkpoint - Phase 1 완료 검증
  - Admin Frontend/Backend 독립 실행 확인
  - 메인 시스템과 분리된 DB 연결 확인
  - _All tests pass before proceeding_

---

## Phase 2: 인증 및 권한 시스템 (Week 2)

- [x] 3. 관리자 인증 시스템 구현
  - [x] 3.1 AdminUser 모델 및 CRUD 구현
    - 비밀번호 해싱 (bcrypt)
    - Role enum (viewer, operator, supervisor, admin)
    - _Role: Backend Developer_
    - _Checkpoint: 관리자 계정 생성/조회 API 테스트_
    - _Requirements: 10.2_

  - [x] 3.2 JWT 인증 구현
    - 로그인 엔드포인트 (`POST /api/auth/login`)
    - 토큰 발급 및 검증 미들웨어
    - _Role: Backend Developer_
    - _Checkpoint: 로그인 후 보호된 엔드포인트 접근 테스트_
    - _Requirements: 10.1_

  - [x] 3.3 2FA (TOTP) 구현
    - pyotp 라이브러리 연동
    - 2FA 설정 및 검증 엔드포인트
    - _Role: Backend Developer_
    - _Checkpoint: Google Authenticator로 2FA 검증 테스트_
    - _Requirements: 10.1_

  - [x] 3.4 세션 타임아웃 구현
    - 30분 비활성 시 자동 로그아웃
    - Redis 세션 저장소
    - _Role: Backend Developer_
    - _Checkpoint: 30분 후 토큰 만료 확인_
    - _Requirements: 10.5_

  - [x] 3.5 RBAC 미들웨어 구현
    - 역할별 엔드포인트 접근 제어
    - 민감 작업 재인증 요구
    - _Role: Backend Developer_
    - _Checkpoint: 권한 없는 역할의 접근 거부 테스트_
    - _Requirements: 10.2, 10.3_

  - [ ]* 3.6 Property Test: Role-Based Access Control
    - **Property 9: Role-Based Access Control**
    - **Validates: Requirements 10.2, 10.3**

- [x] 4. 로그인 UI 구현
  - [x] 4.1 로그인 페이지 구현
    - 이메일/비밀번호 폼
    - 에러 메시지 표시
    - _Role: Frontend Developer_
    - _Checkpoint: 로그인 성공/실패 플로우 확인_
    - _Requirements: 10.1_

  - [x] 4.2 2FA 입력 페이지 구현
    - 6자리 코드 입력 UI
    - 재시도 및 에러 처리
    - _Role: Frontend Developer_
    - _Checkpoint: 2FA 검증 후 대시보드 리다이렉트 확인_
    - _Requirements: 10.1_

- [x] 5. Checkpoint - Phase 2 완료 검증
  - ✅ 로그인 → 2FA → 대시보드 전체 플로우 구현 완료
  - ✅ 역할별 접근 제어 (RBAC) 미들웨어 구현 완료
  - ✅ 세션 타임아웃 (Redis 기반) 구현 완료
  - ✅ Frontend 빌드 성공
  - ✅ Backend import 검증 완료
  - _All tests pass before proceeding_

---

## Phase 3: 대시보드 및 모니터링 (Week 3)

- [ ] 6. 메트릭 수집 서비스 구현
  - [ ] 6.1 CCU/DAU 집계 서비스 구현
    - Redis에서 실시간 접속자 수 조회
    - 시간별 DAU 집계 쿼리
    - _Role: Backend Developer_
    - _Checkpoint: CCU/DAU API 응답 정확성 검증_
    - _Requirements: 1.1, 1.2_

  - [ ] 6.2 방/플레이어 통계 서비스 구현
    - 활성 방 수, 플레이어 분포 조회
    - _Role: Backend Developer_
    - _Checkpoint: 실제 방 데이터와 일치 확인_
    - _Requirements: 1.3_

  - [ ] 6.3 매출 통계 서비스 구현
    - 일별/주별/월별 레이크 수익 집계
    - 날짜 범위 필터링
    - _Role: Backend Developer_
    - _Checkpoint: 트랜잭션 합계와 일치 확인_
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 6.4 Property Test: Dashboard Metrics Accuracy
    - **Property 1: Dashboard Metrics Accuracy**
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [ ]* 6.5 Property Test: Statistics Calculation Accuracy
    - **Property 2: Statistics Calculation Accuracy**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

- [ ] 7. 대시보드 UI 구현
  - [ ] 7.1 메인 대시보드 레이아웃 구현
    - 사이드바 네비게이션
    - 헤더 (사용자 정보, 로그아웃)
    - _Role: Frontend Developer_
    - _Checkpoint: 레이아웃 렌더링 및 네비게이션 동작 확인_
    - _Requirements: 1.1_

  - [ ] 7.2 CCU/DAU 차트 컴포넌트 구현
    - Recharts 라인 차트
    - 5초 자동 갱신
    - _Role: Frontend Developer_
    - _Checkpoint: 실시간 데이터 갱신 확인_
    - _Requirements: 1.1, 1.2_

  - [ ] 7.3 매출 카드 및 통계 컴포넌트 구현
    - 일별/주별/월별 탭
    - 날짜 범위 선택기
    - _Role: Frontend Developer_
    - _Checkpoint: 필터 변경 시 데이터 갱신 확인_
    - _Requirements: 2.1, 2.4_

  - [ ] 7.4 서버 상태 표시 컴포넌트 구현
    - CPU, 메모리, 레이턴시 게이지
    - 임계값 초과 시 경고 표시
    - _Role: Frontend Developer_
    - _Checkpoint: 임계값 초과 시 경고 UI 확인_
    - _Requirements: 1.4, 1.5_

- [ ] 8. Checkpoint - Phase 3 완료 검증
  - ✅ 대시보드 전체 UI 렌더링 확인
  - ✅ CCU/DAU 차트 컴포넌트 구현 완료
  - ✅ 매출 차트 컴포넌트 구현 완료
  - ✅ 서버 상태 표시 컴포넌트 구현 완료
  - ✅ Frontend 빌드 성공
  - ✅ Backend import 검증 완료
  - _All tests pass before proceeding_

---

## Phase 4: 사용자 관리 (Week 4)

- [ ] 9. 사용자 조회 서비스 구현
  - [ ] 9.1 사용자 검색 API 구현
    - username, email, user_id 검색
    - 페이지네이션 및 필터링
    - _Role: Backend Developer_
    - _Checkpoint: 검색 결과 정확성 테스트_
    - _Requirements: 5.1, 5.5_

  - [ ] 9.2 사용자 상세 정보 API 구현
    - 계정 정보, 잔액, 최근 활동
    - 로그인 기록 (IP 포함)
    - 거래 내역
    - _Role: Backend Developer_
    - _Checkpoint: 사용자 상세 데이터 완전성 확인_
    - _Requirements: 5.2, 5.3, 5.4_

  - [x]* 9.3 Property Test: Search and Filter Accuracy
    - **Property 4: Search and Filter Accuracy**
    - **Validates: Requirements 5.1, 5.5, 8.1**

- [ ] 10. 사용자 관리 UI 구현
  - [ ] 10.1 사용자 목록 페이지 구현
    - DataTable with 검색, 필터, 정렬
    - 페이지네이션
    - _Role: Frontend Developer_
    - _Checkpoint: 1000+ 사용자 목록 렌더링 성능 확인_
    - _Requirements: 5.1, 5.5_

  - [ ] 10.2 사용자 상세 페이지 구현
    - 탭 구조 (정보, 거래, 로그인, 핸드)
    - 제재 버튼
    - _Role: Frontend Developer_
    - _Checkpoint: 모든 탭 데이터 로딩 확인_
    - _Requirements: 5.2, 5.3, 5.4_

- [ ] 11. Checkpoint - Phase 4 완료 검증
  - ✅ 사용자 검색 및 필터링 API 구현 완료
  - ✅ 사용자 상세 정보 API 구현 완료
  - ✅ 사용자 목록 페이지 구현 완료
  - ✅ 사용자 상세 페이지 구현 완료 (탭: 정보, 거래, 로그인, 핸드)
  - ✅ Frontend 빌드 성공
  - _All tests pass before proceeding_

---

## Phase 5: 제재 및 감사 로그 (Week 5)

- [ ] 12. 제재 시스템 구현
  - [ ] 12.1 Ban 서비스 구현
    - 제재 생성 (임시/영구, 사유)
    - 제재 해제
    - 채팅 금지 (게임 허용)
    - _Role: Backend Developer_
    - _Checkpoint: 제재 적용 후 로그인 차단 확인_
    - _Requirements: 6.1, 6.2, 6.4, 6.6_

  - [ ] 12.2 메인 백엔드 Admin API 연동
    - MainAPIClient 구현
    - ban_user, unban_user 호출
    - _Role: Backend Developer_
    - _Checkpoint: 메인 시스템에 제재 반영 확인_
    - _Requirements: 11.4_

  - [ ]* 12.3 Property Test: Ban Enforcement Correctness
    - **Property 5: Ban Enforcement Correctness**
    - **Validates: Requirements 6.2, 6.4**

  - [ ]* 12.4 Property Test: Chat Ban Partial Restriction
    - **Property 6: Chat Ban Partial Restriction**
    - **Validates: Requirements 6.6**

- [ ] 13. 감사 로그 시스템 구현
  - [ ] 13.1 AuditLog 서비스 구현
    - 모든 관리자 액션 기록
    - 조회 API (필터링, 페이지네이션)
    - _Role: Backend Developer_
    - _Checkpoint: 액션 수행 후 로그 생성 확인_
    - _Requirements: 3.5, 4.4, 6.5, 7.4, 10.4_

  - [ ]* 13.2 Property Test: Audit Logging Completeness
    - **Property 3: Audit Logging Completeness**
    - **Validates: Requirements 3.5, 4.4, 6.5, 7.4, 10.4**

- [ ] 14. 제재 관리 UI 구현
  - [ ] 14.1 제재 목록 페이지 구현
    - 활성 제재 목록
    - 제재 해제 버튼
    - _Role: Frontend Developer_
    - _Checkpoint: 제재 목록 및 해제 동작 확인_
    - _Requirements: 6.3, 6.4_

  - [ ] 14.2 제재 생성 다이얼로그 구현
    - 제재 유형, 기간, 사유 입력
    - 확인 다이얼로그
    - _Role: Frontend Developer_
    - _Checkpoint: 제재 생성 플로우 확인_
    - _Requirements: 6.1_

- [ ] 15. Checkpoint - Phase 5 완료 검증
  - 제재 생성/해제 전체 플로우 테스트
  - 감사 로그 기록 확인
  - 메인 시스템 연동 확인
  - _All tests pass before proceeding_

---

## Phase 6: 암호화폐 기본 인프라 (Week 6)

- [ ] 16. 환율 서비스 구현
  - [ ] 16.1 ExchangeRateService 구현
    - Upbit API 연동 (USDT/KRW)
    - Binance API 폴백
    - Redis 캐싱 (30초 TTL)
    - _Role: Backend Developer_
    - _Checkpoint: 환율 조회 API 응답 확인_
    - _Requirements: 12.3, 15.1_

  - [ ] 16.2 환율 히스토리 저장 구현
    - 1분 간격 환율 기록
    - 히스토리 조회 API
    - _Role: Backend Developer_
    - _Checkpoint: 환율 변동 그래프 데이터 확인_
    - _Requirements: 15.2_

  - [ ]* 16.3 Property Test: KRW Conversion Accuracy
    - **Property 13: KRW Conversion Accuracy**
    - **Validates: Requirements 12.2, 13.2, 15.1**

  - [ ]* 16.4 Property Test: Exchange Rate Fallback
    - **Property 17: Exchange Rate Fallback**
    - **Validates: Requirements 15.5**

- [ ] 17. TRON 네트워크 클라이언트 구현
  - [ ] 17.1 TronClient 기본 구현
    - tronpy 라이브러리 연동
    - USDT TRC-20 컨트랙트 연결
    - 잔액 조회, 트랜잭션 조회
    - _Role: Backend Developer_
    - _Checkpoint: 테스트넷에서 잔액 조회 확인_
    - _Requirements: 12.5, 14.1_

  - [ ] 17.2 트랜잭션 확인 수 조회 구현
    - 블록 번호 기반 확인 수 계산
    - 20 confirmations 기준 확정
    - _Role: Backend Developer_
    - _Checkpoint: 트랜잭션 확인 수 정확성 검증_
    - _Requirements: 12.4_

- [ ] 18. 암호화폐 데이터 모델 구현
  - [ ] 18.1 CryptoDeposit 모델 구현
    - 입금 기록 테이블
    - 상태 관리 (pending → confirmed → credited)
    - _Role: Backend Developer_
    - _Checkpoint: 입금 레코드 CRUD 테스트_
    - _Requirements: 12.1, 12.2_

  - [ ] 18.2 CryptoWithdrawal 모델 구현
    - 출금 요청 테이블
    - 승인 워크플로우 상태
    - _Role: Backend Developer_
    - _Checkpoint: 출금 레코드 CRUD 테스트_
    - _Requirements: 13.1, 13.2_

  - [ ] 18.3 HotWalletBalance 모델 구현
    - 지갑 잔액 스냅샷 테이블
    - _Role: Backend Developer_
    - _Checkpoint: 잔액 기록 저장 확인_
    - _Requirements: 14.1_

- [ ] 19. Checkpoint - Phase 6 완료 검증
  - 환율 API 정상 동작 확인
  - TRON 테스트넷 연동 확인
  - 암호화폐 데이터 모델 마이그레이션 확인
  - _All tests pass before proceeding_

---

## Phase 7: 입금 관리 시스템 (Week 7)

- [ ] 20. 입금 모니터링 서비스 구현
  - [ ] 20.1 DepositMonitor 구현
    - 시스템 입금 주소 트랜잭션 모니터링
    - 새 입금 감지 및 DB 기록
    - _Role: Backend Developer_
    - _Checkpoint: 테스트넷 입금 감지 확인_
    - _Requirements: 12.1, 12.4_

  - [ ] 20.2 입금 확정 처리 구현
    - 20 confirmations 도달 시 확정
    - 사용자 게임 잔액 반영
    - _Role: Backend Developer_
    - _Checkpoint: 입금 확정 후 잔액 증가 확인_
    - _Requirements: 12.4_

  - [ ]* 20.3 Property Test: Deposit Detection Accuracy
    - **Property 12: Deposit Detection Accuracy**
    - **Validates: Requirements 12.1, 12.4, 12.5**

- [ ] 21. 입금 관리 API 구현
  - [ ] 21.1 입금 목록 조회 API 구현
    - 상태별, 날짜별 필터링
    - USDT 및 KRW 환산액 포함
    - _Role: Backend Developer_
    - _Checkpoint: 입금 목록 API 응답 확인_
    - _Requirements: 12.1, 12.2, 12.6_

  - [ ] 21.2 입금 상세 조회 API 구현
    - 트랜잭션 해시, 확인 수, 상태
    - _Role: Backend Developer_
    - _Checkpoint: 입금 상세 데이터 완전성 확인_
    - _Requirements: 12.5_

  - [ ] 21.3 수동 입금 승인/거부 API 구현
    - 수동 검토 필요 입금 처리
    - 감사 로그 기록
    - _Role: Backend Developer_
    - _Checkpoint: 수동 승인 후 잔액 반영 확인_
    - _Requirements: 12.7_

- [ ] 22. 입금 관리 UI 구현
  - [ ] 22.1 입금 목록 페이지 구현
    - 상태별 탭 (대기/확인중/완료/실패)
    - USDT/KRW 이중 표시
    - _Role: Frontend Developer_
    - _Checkpoint: 입금 목록 렌더링 및 필터 동작 확인_
    - _Requirements: 12.1, 12.2, 12.6_

  - [ ] 22.2 입금 상세 모달 구현
    - 트랜잭션 정보, 확인 수 표시
    - 수동 승인/거부 버튼
    - _Role: Frontend Developer_
    - _Checkpoint: 입금 상세 및 액션 동작 확인_
    - _Requirements: 12.5, 12.7_

- [ ] 23. Checkpoint - Phase 7 완료 검증
  - 입금 감지 → 확정 → 잔액 반영 전체 플로우 테스트
  - 수동 승인/거부 플로우 테스트
  - KRW 환산 정확성 확인
  - _All tests pass before proceeding_

---

## Phase 8: 출금 관리 시스템 (Week 8)

- [ ] 24. 출금 처리 서비스 구현
  - [ ] 24.1 WithdrawalProcessor 구현
    - 출금 요청 검증
    - 핫월렛 잔액 확인
    - 네트워크 수수료 계산
    - _Role: Backend Developer_
    - _Checkpoint: 출금 요청 검증 로직 테스트_
    - _Requirements: 13.3, 13.4_

  - [ ] 24.2 HSM/KMS 연동 구현
    - AWS KMS 또는 HSM 연동
    - 프라이빗 키 안전 관리
    - 트랜잭션 서명
    - _Role: Backend Developer + Security_
    - _Checkpoint: 테스트넷에서 서명된 트랜잭션 전송 확인_
    - _Requirements: 14.6_

  - [ ] 24.3 출금 실행 구현
    - USDT 전송 트랜잭션 생성 및 브로드캐스트
    - 트랜잭션 해시 기록
    - _Role: Backend Developer_
    - _Checkpoint: 테스트넷 출금 전송 확인_
    - _Requirements: 13.3, 13.5_

  - [ ]* 24.4 Property Test: Withdrawal Balance Integrity
    - **Property 14: Withdrawal Balance Integrity**
    - **Validates: Requirements 13.3, 13.4, 13.8**

- [ ] 25. 출금 승인 워크플로우 구현
  - [ ] 25.1 출금 승인 API 구현
    - 권한 검증 (금액별 역할 요구)
    - 2FA 재인증 요구
    - _Role: Backend Developer_
    - _Checkpoint: 승인 권한 및 재인증 테스트_
    - _Requirements: 13.6, 10.3_

  - [ ] 25.2 출금 거부 API 구현
    - 거부 사유 기록
    - 사용자 잔액 환불
    - _Role: Backend Developer_
    - _Checkpoint: 거부 후 잔액 환불 확인_
    - _Requirements: 13.8_

  - [ ]* 25.3 Property Test: Withdrawal Approval Workflow
    - **Property 15: Withdrawal Approval Workflow**
    - **Validates: Requirements 13.6, 13.7**

- [ ] 26. 출금 관리 UI 구현
  - [ ] 26.1 출금 대기열 페이지 구현
    - 대기 중인 출금 요청 목록
    - USDT/KRW 이중 표시
    - 예상 수수료 표시
    - _Role: Frontend Developer_
    - _Checkpoint: 출금 대기열 렌더링 확인_
    - _Requirements: 13.1, 13.2, 13.4_

  - [ ] 26.2 출금 승인/거부 다이얼로그 구현
    - 상세 정보 확인
    - 2FA 재인증 입력
    - 승인/거부 버튼
    - _Role: Frontend Developer_
    - _Checkpoint: 승인/거부 플로우 UI 확인_
    - _Requirements: 13.3, 13.8_

- [ ] 27. Checkpoint - Phase 8 완료 검증
  - 출금 요청 → 승인 → 전송 → 완료 전체 플로우 테스트
  - 고액 출금 supervisor 승인 테스트
  - 출금 거부 및 환불 테스트
  - HSM 서명 보안 검증
  - _All tests pass before proceeding_

---

## Phase 9: 지갑 관리 및 통계 (Week 9)

- [ ] 28. 핫월렛 관리 서비스 구현
  - [ ] 28.1 WalletManager 구현
    - 핫월렛 잔액 조회
    - 잔액 스냅샷 저장 (1시간 간격)
    - _Role: Backend Developer_
    - _Checkpoint: 잔액 조회 및 스냅샷 저장 확인_
    - _Requirements: 14.1, 14.2_

  - [ ] 28.2 잔액 경고 시스템 구현
    - 임계값 설정
    - 잔액 부족 시 알림
    - _Role: Backend Developer_
    - _Checkpoint: 임계값 이하 시 경고 생성 확인_
    - _Requirements: 14.3, 14.4_

  - [ ]* 28.3 Property Test: Hot Wallet Alert Threshold
    - **Property 16: Hot Wallet Alert Threshold**
    - **Validates: Requirements 14.3, 14.4**

- [ ] 29. 암호화폐 통계 서비스 구현
  - [ ] 29.1 입출금 통계 API 구현
    - 일별/주별/월별 집계
    - USDT 및 KRW 합계
    - _Role: Backend Developer_
    - _Checkpoint: 통계 데이터 정확성 검증_
    - _Requirements: 14.2, 15.3, 15.4_

- [ ] 30. 지갑 관리 UI 구현
  - [ ] 30.1 지갑 상태 페이지 구현
    - 현재 잔액 (USDT/KRW)
    - 대기 중 출금 총액
    - 잔액 경고 표시
    - _Role: Frontend Developer_
    - _Checkpoint: 지갑 상태 UI 렌더링 확인_
    - _Requirements: 14.1, 14.3, 14.4_

  - [ ] 30.2 환율 및 통계 페이지 구현
    - 현재 환율 및 히스토리 차트
    - 입출금 통계 차트
    - _Role: Frontend Developer_
    - _Checkpoint: 환율/통계 차트 렌더링 확인_
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [ ] 31. Checkpoint - Phase 9 완료 검증
  - 지갑 잔액 모니터링 확인
  - 잔액 경고 알림 테스트
  - 통계 데이터 정확성 검증
  - _All tests pass before proceeding_

---

## Phase 10: 추가 기능 및 마무리 (Week 10)

- [ ] 32. 방 관리 기능 구현
  - [ ] 32.1 방 목록/상세 API 구현
    - _Role: Backend Developer_
    - _Requirements: 4.1, 4.2_

  - [ ] 32.2 방 강제 종료 API 구현
    - _Role: Backend Developer_
    - _Requirements: 4.3, 4.4_

  - [ ] 32.3 방 관리 UI 구현
    - _Role: Frontend Developer_
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

- [ ] 33. 핸드 리플레이 기능 구현
  - [ ] 33.1 핸드 검색/상세 API 구현
    - _Role: Backend Developer_
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ] 33.2 핸드 내보내기 API 구현
    - _Role: Backend Developer_
    - _Requirements: 8.5_

  - [ ] 33.3 핸드 리플레이 UI 구현
    - _Role: Frontend Developer_
    - _Requirements: 8.2, 8.3, 8.4_

  - [ ]* 33.4 Property Test: Hand Replay Data Completeness
    - **Property 8: Hand Replay Data Completeness**
    - **Validates: Requirements 8.2, 8.3, 8.4**

- [ ] 34. 공지/점검 관리 기능 구현
  - [ ] 34.1 공지/점검 API 구현
    - _Role: Backend Developer_
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 34.2 공지/점검 UI 구현
    - _Role: Frontend Developer_
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 35. 의심 사용자 관리 기능 구현
  - [ ] 35.1 의심 사용자 API 구현
    - _Role: Backend Developer_
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ] 35.2 의심 사용자 UI 구현
    - _Role: Frontend Developer_
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 36. 자산 수동 조정 기능 구현
  - [ ] 36.1 잔액 조정 API 구현
    - _Role: Backend Developer_
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 36.2 Property Test: Balance Adjustment Transaction Integrity
    - **Property 7: Balance Adjustment Transaction Integrity**
    - **Validates: Requirements 7.2, 7.3**

  - [ ] 36.3 잔액 조정 UI 구현
    - _Role: Frontend Developer_
    - _Requirements: 7.1, 7.5_

- [ ] 37. Checkpoint - Phase 10 완료 검증
  - 모든 기능 통합 테스트
  - E2E 테스트 실행
  - 보안 감사 수행
  - _All tests pass before proceeding_

---

## Phase 11: 배포 및 운영 준비

- [ ] 38. 프로덕션 배포 준비
  - [ ] 38.1 프로덕션 환경 설정
    - 환경 변수, 시크릿 관리
    - _Role: DevOps_

  - [ ] 38.2 Kubernetes 매니페스트 작성
    - admin-frontend, admin-backend 배포
    - _Role: DevOps_

  - [ ] 38.3 모니터링 설정
    - Prometheus 메트릭, Grafana 대시보드
    - 암호화폐 트랜잭션 알림
    - _Role: DevOps_

- [ ] 39. 보안 검토
  - [ ] 39.1 보안 감사 수행
    - 암호화폐 관련 보안 검토
    - 인증/권한 검토
    - _Role: Security_

  - [ ] 39.2 침투 테스트
    - _Role: Security_

- [ ] 40. Final Checkpoint - 배포 준비 완료
  - 모든 테스트 통과
  - 보안 감사 완료
  - 문서화 완료
  - 운영팀 교육 완료

---

## Notes

- `*` 표시된 태스크는 선택적 Property-Based 테스트입니다
- 각 Phase 완료 후 반드시 Checkpoint 검증을 수행합니다
- 암호화폐 관련 기능은 반드시 테스트넷에서 먼저 검증합니다
- HSM/KMS 연동은 보안팀과 협업하여 진행합니다
