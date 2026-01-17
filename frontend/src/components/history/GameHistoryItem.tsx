'use client';

import { motion } from 'framer-motion';
import { HandHistory } from '@/lib/api';

interface GameHistoryItemProps {
  hand: HandHistory;
}

// 카드 렌더링 헬퍼
function renderCard(card: string) {
  const suit = card.slice(-1);
  const rank = card.slice(0, -1);

  const suitColors: Record<string, string> = {
    'h': '#ef4444',
    'd': '#3b82f6',
    'c': '#22c55e',
    's': '#1f2937',
  };

  const suitSymbols: Record<string, string> = {
    'h': '♥',
    'd': '♦',
    'c': '♣',
    's': '♠',
  };

  return (
    <span
      key={card}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '24px',
        height: '32px',
        background: 'white',
        borderRadius: '4px',
        fontSize: '12px',
        fontWeight: 700,
        color: suitColors[suit] || '#000',
        marginRight: '2px',
      }}
    >
      {rank}{suitSymbols[suit]}
    </span>
  );
}

export default function GameHistoryItem({ hand }: GameHistoryItemProps) {
  const isWin = hand.net_result > 0;
  const isLose = hand.net_result < 0;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const actionLabels: Record<string, string> = {
    'fold': '폴드',
    'showdown': '쇼다운',
    'all_in_won': '올인 승리',
    'timeout': '타임아웃',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: 'rgba(255,255,255,0.05)',
        borderRadius: '12px',
        padding: '16px',
        marginBottom: '12px',
        border: `1px solid ${isWin ? 'rgba(34, 197, 94, 0.3)' : isLose ? 'rgba(239, 68, 68, 0.3)' : 'rgba(255,255,255,0.1)'}`,
      }}
    >
      {/* 헤더 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px',
        }}
      >
        <div>
          <span style={{ color: '#888', fontSize: '12px' }}>핸드 #{hand.hand_number}</span>
          <span style={{ color: '#666', fontSize: '12px', marginLeft: '8px' }}>
            {formatDate(hand.started_at)}
          </span>
        </div>
        <span
          style={{
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 600,
            background: isWin
              ? 'rgba(34, 197, 94, 0.2)'
              : isLose
              ? 'rgba(239, 68, 68, 0.2)'
              : 'rgba(255,255,255,0.1)',
            color: isWin ? '#22c55e' : isLose ? '#ef4444' : '#888',
          }}
        >
          {actionLabels[hand.user_final_action] || hand.user_final_action}
        </span>
      </div>

      {/* 카드 */}
      <div style={{ marginBottom: '12px' }}>
        <div style={{ marginBottom: '8px' }}>
          <span style={{ color: '#888', fontSize: '11px', marginRight: '8px' }}>홀카드</span>
          {hand.user_hole_cards?.map(renderCard)}
        </div>
        {hand.community_cards && hand.community_cards.length > 0 && (
          <div>
            <span style={{ color: '#888', fontSize: '11px', marginRight: '8px' }}>커뮤니티</span>
            {hand.community_cards.map(renderCard)}
          </div>
        )}
      </div>

      {/* 결과 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingTop: '12px',
          borderTop: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <div>
          <span style={{ color: '#888', fontSize: '12px' }}>베팅: </span>
          <span style={{ color: 'white', fontSize: '14px' }}>
            {hand.user_bet_amount.toLocaleString()}
          </span>
        </div>
        <div>
          <span style={{ color: '#888', fontSize: '12px' }}>결과: </span>
          <span
            style={{
              color: isWin ? '#22c55e' : isLose ? '#ef4444' : 'white',
              fontSize: '16px',
              fontWeight: 700,
            }}
          >
            {hand.net_result > 0 ? '+' : ''}{hand.net_result.toLocaleString()}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
