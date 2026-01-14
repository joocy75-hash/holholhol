'use client';

import { useState, useEffect, useCallback } from 'react';

// ========================================
// 칩 애니메이션 테스트 페이지
// ========================================

// 좌석 위치 (9인 테이블)
const SEAT_POSITIONS = [
  { top: '70%', left: '50%' },   // 0 - bottom center (ME)
  { top: '60%', left: '10%' },   // 1 - lower left
  { top: '60%', left: '90%' },   // 2 - lower right
  { top: '38%', left: '10%' },   // 3 - mid left
  { top: '38%', left: '90%' },   // 4 - mid right
  { top: '25%', left: '18%' },   // 5 - upper left
  { top: '25%', left: '82%' },   // 6 - upper right
  { top: '17%', left: '35%' },   // 7 - top left
  { top: '17%', left: '65%' },   // 8 - top right
];

// 칩 베팅 위치 (플레이어와 중앙 사이)
const CHIP_POSITIONS = [
  { top: '62%', left: '50%' },   // 0
  { top: '55%', left: '18%' },   // 1
  { top: '55%', left: '82%' },   // 2
  { top: '42%', left: '18%' },   // 3
  { top: '42%', left: '82%' },   // 4
  { top: '32%', left: '25%' },   // 5
  { top: '32%', left: '75%' },   // 6
  { top: '26%', left: '40%' },   // 7
  { top: '26%', left: '60%' },   // 8
];

// POT 위치 (중앙)
const POT_POSITION = { top: '45%', left: '50%' };

// 칩 색상 (금액에 따라)
const CHIP_COLORS = [
  { min: 0, max: 25, color: 'bg-gray-400', label: '1' },
  { min: 25, max: 100, color: 'bg-red-500', label: '25' },
  { min: 100, max: 500, color: 'bg-green-500', label: '100' },
  { min: 500, max: 1000, color: 'bg-blue-500', label: '500' },
  { min: 1000, max: Infinity, color: 'bg-purple-500', label: '1K' },
];

// 금액에 따른 칩 스택 계산
function calculateChipStack(amount: number): { color: string; count: number; label: string }[] {
  if (amount <= 0) return [];

  const stack: { color: string; count: number; label: string }[] = [];
  let remaining = amount;

  // 큰 단위부터 계산
  const denominations = [1000, 500, 100, 25, 1];
  const colorMap: Record<number, { color: string; label: string }> = {
    1000: { color: 'bg-purple-500', label: '1K' },
    500: { color: 'bg-blue-500', label: '500' },
    100: { color: 'bg-green-500', label: '100' },
    25: { color: 'bg-red-500', label: '25' },
    1: { color: 'bg-gray-400', label: '1' },
  };

  for (const denom of denominations) {
    const count = Math.floor(remaining / denom);
    if (count > 0) {
      // 최대 5개까지만 표시 (시각적)
      stack.push({
        ...colorMap[denom],
        count: Math.min(count, 5)
      });
      remaining -= count * denom;
    }
  }

  return stack.slice(0, 3); // 최대 3종류 칩만 표시
}

// 칩 스택 컴포넌트
function ChipStack({
  amount,
  position,
  animatingTo,
  onAnimationEnd,
}: {
  amount: number;
  position: { top: string; left: string };
  animatingTo?: { top: string; left: string } | null;
  onAnimationEnd?: () => void;
}) {
  const [isAnimating, setIsAnimating] = useState(false);
  const [currentPos, setCurrentPos] = useState(position);

  useEffect(() => {
    if (animatingTo) {
      setIsAnimating(true);
      // 약간의 딜레이 후 위치 변경 (애니메이션 트리거)
      const timer = setTimeout(() => {
        setCurrentPos(animatingTo);
      }, 50);

      // 애니메이션 종료 처리
      const endTimer = setTimeout(() => {
        setIsAnimating(false);
        onAnimationEnd?.();
      }, 600);

      return () => {
        clearTimeout(timer);
        clearTimeout(endTimer);
      };
    } else {
      setCurrentPos(position);
    }
  }, [animatingTo, position, onAnimationEnd]);

  const chips = calculateChipStack(amount);
  if (chips.length === 0) return null;

  return (
    <div
      className={`absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center transition-all duration-500 ease-out ${isAnimating ? 'z-50' : 'z-10'}`}
      style={{
        top: currentPos.top,
        left: currentPos.left,
      }}
    >
      {/* 칩 스택 (3D 효과) */}
      <div className="relative">
        {chips.map((chip, stackIndex) => (
          <div key={stackIndex} className="flex flex-col-reverse">
            {Array.from({ length: chip.count }).map((_, i) => (
              <div
                key={i}
                className={`w-8 h-2 ${chip.color} rounded-full border border-white/30 shadow-md`}
                style={{
                  marginTop: i > 0 ? '-4px' : '0',
                  marginLeft: stackIndex * 12,
                }}
              />
            ))}
          </div>
        ))}
      </div>
      {/* 금액 표시 */}
      <div className="mt-1 px-2 py-0.5 bg-black/70 rounded text-white text-xs font-bold">
        {amount.toLocaleString()}
      </div>
    </div>
  );
}

// 플레이어 컴포넌트
function Player({
  position,
  seatIndex,
  name,
  stack,
  bet,
  isWinner,
}: {
  position: { top: string; left: string };
  seatIndex: number;
  name: string;
  stack: number;
  bet: number;
  isWinner?: boolean;
}) {
  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
      style={position}
    >
      <div className={`w-12 h-12 rounded-full bg-slate-700 border-2 ${isWinner ? 'border-yellow-400 shadow-lg shadow-yellow-400/50' : 'border-slate-500'} flex items-center justify-center text-white font-bold`}>
        {name.charAt(0)}
      </div>
      <div className="mt-1 text-center">
        <div className="text-white text-xs font-medium">{name}</div>
        <div className="text-yellow-400 text-xs">{stack.toLocaleString()}</div>
      </div>
      {isWinner && (
        <div className="absolute -top-8 px-2 py-1 bg-yellow-500 text-black text-xs font-bold rounded">
          WIN!
        </div>
      )}
    </div>
  );
}

// 메인 테스트 페이지
export default function ChipTestPage() {
  // 플레이어 상태
  const [players, setPlayers] = useState([
    { seat: 0, name: 'Me', stack: 1000, bet: 0 },
    { seat: 1, name: 'Bot1', stack: 800, bet: 0 },
    { seat: 4, name: 'Bot2', stack: 1200, bet: 0 },
    { seat: 7, name: 'Bot3', stack: 950, bet: 0 },
  ]);

  const [pot, setPot] = useState(0);
  const [phase, setPhase] = useState<'betting' | 'collecting' | 'distributing' | 'idle'>('idle');
  const [winner, setWinner] = useState<number | null>(null);

  // 칩 애니메이션 상태
  const [collectingChips, setCollectingChips] = useState<{ seat: number; amount: number; animatingTo: typeof POT_POSITION | null }[]>([]);
  const [distributingChip, setDistributingChip] = useState<{ amount: number; toSeat: number } | null>(null);

  // 베팅 시뮬레이션
  const simulateBetting = useCallback(() => {
    setPhase('betting');
    setWinner(null);
    setPot(0);

    // 각 플레이어 랜덤 베팅
    setPlayers(prev => prev.map(p => ({
      ...p,
      bet: Math.floor(Math.random() * 100 + 20),
      stack: p.stack - Math.floor(Math.random() * 100 + 20),
    })));
  }, []);

  // 칩 수집 (중앙으로)
  const collectChips = useCallback(() => {
    setPhase('collecting');

    // 베팅한 칩들을 애니메이션용 상태로 설정
    const chipsToCollect = players
      .filter(p => p.bet > 0)
      .map(p => ({
        seat: p.seat,
        amount: p.bet,
        animatingTo: null as typeof POT_POSITION | null,
      }));

    setCollectingChips(chipsToCollect);

    // 순차적으로 칩 수집 애니메이션
    chipsToCollect.forEach((chip, index) => {
      setTimeout(() => {
        setCollectingChips(prev =>
          prev.map(c =>
            c.seat === chip.seat
              ? { ...c, animatingTo: POT_POSITION }
              : c
          )
        );
      }, index * 200);
    });

    // 모든 칩 수집 완료 후
    setTimeout(() => {
      const totalPot = players.reduce((sum, p) => sum + p.bet, 0);
      setPot(totalPot);
      setPlayers(prev => prev.map(p => ({ ...p, bet: 0 })));
      setCollectingChips([]);
      setPhase('idle');
    }, chipsToCollect.length * 200 + 600);
  }, [players]);

  // 승자에게 칩 분배
  const distributeToWinner = useCallback(() => {
    if (pot <= 0) return;

    setPhase('distributing');

    // 랜덤 승자 선택
    const winnerIndex = Math.floor(Math.random() * players.length);
    const winnerSeat = players[winnerIndex].seat;
    setWinner(winnerSeat);

    // 칩 이동 애니메이션
    setDistributingChip({ amount: pot, toSeat: winnerSeat });

    // 애니메이션 완료 후
    setTimeout(() => {
      setPlayers(prev => prev.map(p =>
        p.seat === winnerSeat
          ? { ...p, stack: p.stack + pot }
          : p
      ));
      setPot(0);
      setDistributingChip(null);
      setPhase('idle');

      // 승자 표시 잠시 후 제거
      setTimeout(() => setWinner(null), 2000);
    }, 600);
  }, [pot, players]);

  // 전체 시뮬레이션
  const runFullSimulation = useCallback(async () => {
    // 1. 베팅
    simulateBetting();

    // 2. 1.5초 후 칩 수집
    setTimeout(() => {
      collectChips();
    }, 1500);

    // 3. 칩 수집 완료 후 승자에게 분배 (타이밍 계산)
    setTimeout(() => {
      distributeToWinner();
    }, 1500 + players.filter(p => p.bet > 0 || true).length * 200 + 1000);
  }, [simulateBetting, collectChips, distributeToWinner, players]);

  return (
    <div className="min-h-screen bg-slate-900 p-4">
      <h1 className="text-white text-2xl font-bold text-center mb-4">
        칩 애니메이션 테스트
      </h1>

      {/* 컨트롤 버튼 */}
      <div className="flex justify-center gap-4 mb-8">
        <button
          onClick={simulateBetting}
          disabled={phase !== 'idle'}
          className="px-4 py-2 bg-blue-500 text-white rounded disabled:opacity-50"
        >
          1. 베팅 시뮬레이션
        </button>
        <button
          onClick={collectChips}
          disabled={phase !== 'idle' || players.every(p => p.bet === 0)}
          className="px-4 py-2 bg-green-500 text-white rounded disabled:opacity-50"
        >
          2. 칩 수집 (→ POT)
        </button>
        <button
          onClick={distributeToWinner}
          disabled={phase !== 'idle' || pot === 0}
          className="px-4 py-2 bg-yellow-500 text-black rounded disabled:opacity-50"
        >
          3. 승자에게 분배
        </button>
        <button
          onClick={runFullSimulation}
          disabled={phase !== 'idle'}
          className="px-4 py-2 bg-purple-500 text-white rounded disabled:opacity-50"
        >
          전체 시뮬레이션
        </button>
      </div>

      {/* 테이블 영역 */}
      <div className="relative w-full max-w-4xl mx-auto aspect-[4/3] bg-green-800 rounded-[50%] border-8 border-amber-900">
        {/* POT 표시 */}
        <div
          className="absolute -translate-x-1/2 -translate-y-1/2 text-center"
          style={POT_POSITION}
        >
          <div className="text-white/70 text-sm">POT</div>
          <div className="text-white font-bold text-xl">{pot.toLocaleString()}</div>
        </div>

        {/* 플레이어들 */}
        {players.map(player => (
          <Player
            key={player.seat}
            position={SEAT_POSITIONS[player.seat]}
            seatIndex={player.seat}
            name={player.name}
            stack={player.stack}
            bet={player.bet}
            isWinner={winner === player.seat}
          />
        ))}

        {/* 베팅 칩 (플레이어 앞) */}
        {players.map(player => (
          player.bet > 0 && !collectingChips.find(c => c.seat === player.seat) && (
            <ChipStack
              key={`bet-${player.seat}`}
              amount={player.bet}
              position={CHIP_POSITIONS[player.seat]}
            />
          )
        ))}

        {/* 수집 중인 칩 (애니메이션) */}
        {collectingChips.map(chip => (
          <ChipStack
            key={`collecting-${chip.seat}`}
            amount={chip.amount}
            position={CHIP_POSITIONS[chip.seat]}
            animatingTo={chip.animatingTo}
          />
        ))}

        {/* 분배 중인 칩 (POT → 승자) */}
        {distributingChip && (
          <ChipStack
            amount={distributingChip.amount}
            position={POT_POSITION}
            animatingTo={CHIP_POSITIONS[distributingChip.toSeat]}
          />
        )}
      </div>

      {/* 상태 표시 */}
      <div className="mt-4 text-center text-white">
        <p>Phase: <span className="font-bold text-yellow-400">{phase}</span></p>
      </div>
    </div>
  );
}
