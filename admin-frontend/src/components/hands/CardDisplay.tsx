'use client';

interface CardDisplayProps {
  card: string;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * 포커 카드 표시 컴포넌트
 * 카드 형식: "As" (에이스 스페이드), "Kh" (킹 하트) 등
 */
export function CardDisplay({ card, size = 'md' }: CardDisplayProps) {
  // Parse card string (e.g., "As" -> rank: "A", suit: "s")
  const rank = card.slice(0, -1);
  const suit = card.slice(-1).toLowerCase();

  // Suit colors and symbols
  const suitConfig: Record<string, { symbol: string; color: string }> = {
    s: { symbol: '♠', color: 'text-gray-900' }, // Spades
    h: { symbol: '♥', color: 'text-red-500' }, // Hearts
    d: { symbol: '♦', color: 'text-red-500' }, // Diamonds
    c: { symbol: '♣', color: 'text-gray-900' }, // Clubs
  };

  const sizeClasses = {
    sm: 'w-8 h-11 text-xs',
    md: 'w-12 h-16 text-sm',
    lg: 'w-16 h-22 text-lg',
  };

  const config = suitConfig[suit] || { symbol: '?', color: 'text-gray-500' };

  return (
    <div
      className={`
        ${sizeClasses[size]}
        bg-white border-2 border-gray-200 rounded-md shadow-sm
        flex flex-col items-center justify-center
        font-bold ${config.color}
      `}
    >
      <span>{rank}</span>
      <span>{config.symbol}</span>
    </div>
  );
}
