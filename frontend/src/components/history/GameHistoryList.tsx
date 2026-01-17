'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { historyApi, HandHistory } from '@/lib/api';
import GameHistoryItem from './GameHistoryItem';

export default function GameHistoryList() {
  const [hands, setHands] = useState<HandHistory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const loadHands = async (reset = false) => {
    try {
      setIsLoading(true);
      const currentOffset = reset ? 0 : offset;
      const response = await historyApi.getGameHistory(limit, currentOffset);
      const newHands = response.data;

      if (reset) {
        setHands(newHands);
        setOffset(limit);
      } else {
        setHands((prev) => [...prev, ...newHands]);
        setOffset((prev) => prev + limit);
      }

      setHasMore(newHands.length === limit);
      setError(null);
    } catch (err) {
      console.error('게임 기록 로딩 실패:', err);
      setError('게임 기록을 불러오는데 실패했습니다');
      // 에러 시 빈 배열 설정
      if (offset === 0) {
        setHands([]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHands(true);
  }, []);

  if (error && hands.length === 0) {
    return (
      <div
        style={{
          padding: '40px 20px',
          textAlign: 'center',
        }}
      >
        <p style={{ color: '#888', marginBottom: '16px' }}>{error}</p>
        <motion.button
          onClick={() => loadHands(true)}
          whileTap={{ scale: 0.95 }}
          style={{
            padding: '12px 24px',
            background: 'rgba(255,255,255,0.1)',
            border: 'none',
            borderRadius: '8px',
            color: 'white',
            cursor: 'pointer',
          }}
        >
          다시 시도
        </motion.button>
      </div>
    );
  }

  if (!isLoading && hands.length === 0) {
    return (
      <div
        style={{
          padding: '60px 20px',
          textAlign: 'center',
        }}
      >
        <svg
          width="64"
          height="64"
          viewBox="0 0 24 24"
          fill="rgba(255,255,255,0.2)"
          style={{ margin: '0 auto 16px' }}
        >
          <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 14l-5-5 1.41-1.41L12 14.17l4.59-4.58L18 11l-6 6z" />
        </svg>
        <p style={{ color: '#888' }}>게임 기록이 없습니다</p>
        <p style={{ color: '#666', fontSize: '14px', marginTop: '8px' }}>
          게임에 참여하면 기록이 표시됩니다
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '0 20px 20px' }}>
      {hands.map((hand) => (
        <GameHistoryItem key={hand.hand_id} hand={hand} />
      ))}

      {isLoading && (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <p style={{ color: '#888' }}>로딩 중...</p>
        </div>
      )}

      {!isLoading && hasMore && (
        <motion.button
          onClick={() => loadHands(false)}
          whileTap={{ scale: 0.95 }}
          style={{
            width: '100%',
            padding: '12px',
            background: 'rgba(255,255,255,0.1)',
            border: 'none',
            borderRadius: '8px',
            color: 'white',
            cursor: 'pointer',
            marginTop: '12px',
          }}
        >
          더 보기
        </motion.button>
      )}
    </div>
  );
}
