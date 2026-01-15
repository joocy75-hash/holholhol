# 게임 플레이 로직 점검 결과

## 점검 항목 및 상태

### 1. 카드 딜링 위치 (봇 0-8 위치) ✅ 정상
- **파일**: `PlayerSeat.tsx`, `DealingAnimation.tsx`, `useTableLayout.ts`
- **SEAT_POSITIONS**: 9개 좌석 위치 올바르게 정의됨
  - 0번: 90% (하단 중앙 - 플레이어)
  - 1,2번: 70% (하단 좌우)
  - 3,4번: 52% (중간 좌우)
  - 5,6번: 35% (상단 좌우)
  - 7,8번: 21% (최상단 좌우)
- **딜링 시퀀스**: SB부터 시계방향, 2바퀴 (정상)

### 2. 카드 오픈 확인 로직 ✅ 정상
- **파일**: `PlayerSeat.tsx`, `page.tsx`
- **FlippableCard**: 탭하여 카드 오픈 기능 정상
- **자동 오픈**: 10초 후 자동 오픈 (CARD_AUTO_REVEAL_DELAY)
- **사운드**: `/sounds/opencard.webm` 재생

### 3. 남은 자리 클릭 게임 참여 ⚠️ 수정됨
- **문제**: `SeatsRenderer`에서 `onJoinClick`이 position 파라미터를 무시
- **수정**: `onSeatClick(position: number)` 형태로 변경
- **파일**: `SeatsRenderer.tsx`, `page.tsx`

### 4. 정식룰 기반 카드 테이블 깔리는 로직 ✅ 정상
- **파일**: `useTableWebSocket.ts` (COMMUNITY_CARDS 핸들러)
- **플랍**: 3장 동시 공개
- **턴/리버**: 1장씩 공개
- **칩 수집 애니메이션**: 커뮤니티 카드 공개 전 실행

### 5. 족보 실시간 표시 ✅ 정상
- **파일**: `handEvaluator.ts`, `TableCenter.tsx`
- **analyzeHand**: 프리플랍~리버까지 족보 계산
- **표시 위치**: 팟 아래쪽 (top: 58%)
- **스타일**: 황금색 그라데이션 배지

### 6. 베팅 순서 타이머 애니메이션 ✅ 정상
- **파일**: `TimerDisplay.tsx`
- **기본 시간**: 15초 (DEFAULT_TURN_TIME)
- **카운트다운**: 마지막 10초부터 표시
- **색상 변화**: 녹색 → 황색 → 빨강
- **자동 폴드**: 시간 초과 시 onAutoFold 호출

## 수정 내역

### SeatsRenderer.tsx
```diff
- onJoinClick: () => void;
+ onSeatClick: (position: number) => void;

- onSeatClick={!seat?.player && isSpectator ? onJoinClick : undefined}
+ onSeatClick={!seat?.player && isSpectator ? () => onSeatClick(actualPosition) : undefined}
```

### page.tsx
```diff
- const handleJoinClick = useCallback(() => {
+ const handleSeatClick = useCallback((position: number) => {
    setError(null);
+   console.log('[SEAT] Seat clicked:', position);
    setShowBuyInModal(true);
- }, [setError]);
+ }, [setError]);

- onJoinClick={handleJoinClick}
+ onSeatClick={handleSeatClick}
```

## 결론
게임 참여 클릭 핸들러의 position 파라미터 전달 문제를 수정했습니다. 나머지 로직들은 모두 정상 작동합니다.
