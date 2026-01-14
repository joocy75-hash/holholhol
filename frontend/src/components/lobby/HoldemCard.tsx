'use client';

interface Table {
  id: string;
  name: string;
  blinds: string;
  maxSeats: number;
  playerCount: number;
  status: 'waiting' | 'playing' | 'finished';
  isPrivate: boolean;
  buyInMin: number;
  buyInMax: number;
}

interface HoldemCardProps {
  table: Table;
  onJoin: (table: Table) => void;
  onReset?: (tableId: string) => void;
  isLoading?: boolean;
  isResetting?: boolean;
}

// Card icon with gradient - SVG 필터 제거 (CSS drop-shadow로 대체)
function CardIcon() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="card-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#a855f7"/>
          <stop offset="50%" stopColor="#9333ea"/>
          <stop offset="100%" stopColor="#7c3aed"/>
        </linearGradient>
      </defs>
      <g>
        {/* Back card */}
        <rect x="6" y="4" width="16" height="22" rx="2" fill="url(#card-gradient)" opacity="0.6"/>
        {/* Front card */}
        <rect x="14" y="10" width="16" height="22" rx="2" fill="url(#card-gradient)"/>
        <text x="22" y="24" textAnchor="middle" fill="white" fontSize="12" fontWeight="bold">A</text>
        <text x="17" y="15" fill="white" fontSize="8">♠</text>
      </g>
    </svg>
  );
}

// Gold coin icon - SVG 필터 제거
function GoldIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="gold-coin" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#fcd34d"/>
          <stop offset="50%" stopColor="#fbbf24"/>
          <stop offset="100%" stopColor="#f59e0b"/>
        </linearGradient>
      </defs>
      <circle cx="8" cy="8" r="7" fill="url(#gold-coin)"/>
      <circle cx="8" cy="8" r="5.5" stroke="#d97706" strokeWidth="0.5" fill="none"/>
      <text x="8" y="11" textAnchor="middle" fill="#92400e" fontSize="7" fontWeight="bold">G</text>
    </svg>
  );
}

export default function HoldemCard({ table, onJoin, onReset, isLoading = false, isResetting = false }: HoldemCardProps) {
  const isFull = table.playerCount >= table.maxSeats;

  const formatBuyIn = (amount: number) => {
    if (amount >= 10000) {
      return `${(amount / 10000).toFixed(0)}만`;
    }
    return amount.toLocaleString();
  };

  return (
    <div className="game-card holdem">
      {/* Left Section */}
      <div className="game-card-left">
        <div className="game-card-icon">
          <CardIcon />
        </div>
        <div className="game-card-type">홀덤</div>
      </div>

      {/* Divider */}
      <div className="game-card-divider" />

      {/* Right Section */}
      <div className="game-card-right">
        {/* Title Row */}
        <div className="flex items-center gap-2">
          <span className="game-card-seats">
            {table.maxSeats}인
          </span>
          <span className="text-[var(--text-muted)]">|</span>
          <span className="game-card-title truncate">{table.name}</span>
          {table.isPrivate && (
            <span className="text-[var(--warning)] text-sm">🔒</span>
          )}
        </div>

        {/* Info Row */}
        <div className="game-card-info">
          <span className="text-[var(--text-muted)]">블라인드</span>
          <span className="game-card-blinds">{table.blinds}</span>
          <span className="game-card-dot">•</span>
          <span className={`game-card-players ${table.status === 'playing' ? 'playing' : ''}`}>
            {table.playerCount}/{table.maxSeats}명
          </span>
        </div>

        {/* Buy-in Row */}
        <div className="game-card-buyin">
          <div className="game-card-buyin-info">
            <span className="game-card-buyin-label">바이인</span>
            <span className="game-card-buyin-value">
              <GoldIcon />
              <span>{formatBuyIn(table.buyInMin)}</span>
              {table.buyInMax !== table.buyInMin && (
                <span> ~ {formatBuyIn(table.buyInMax)}</span>
              )}
            </span>
          </div>

          <div className="flex gap-2">
            {/* DEV: 리셋 버튼 (만석일 때만 표시) */}
            {isFull && onReset && (
              <button
                onClick={() => onReset(table.id)}
                disabled={isResetting}
                className="px-3 py-2 rounded-lg bg-red-500/80 hover:bg-red-500 text-white text-sm font-medium transition-colors disabled:opacity-50"
              >
                {isResetting ? '...' : '리셋'}
              </button>
            )}
            <button
              onClick={() => onJoin(table)}
              disabled={isLoading || isFull}
              className="btn-join"
            >
              <span className="btn-join-arrow">&gt;</span>
              <span>{isFull ? '만석' : '참여하기'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
