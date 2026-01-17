'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { historyApi, WalletTransaction } from '@/lib/api';
import TransactionItem from './TransactionItem';

const filterOptions = [
  { value: '', label: '전체' },
  { value: 'crypto_deposit', label: '입금' },
  { value: 'crypto_withdrawal', label: '출금' },
  { value: 'buy_in', label: '바이인' },
  { value: 'cash_out', label: '캐시아웃' },
];

export default function TransactionList() {
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const loadTransactions = async (reset = false, txType?: string) => {
    try {
      setIsLoading(true);
      const currentOffset = reset ? 0 : offset;
      const response = await historyApi.getTransactions(
        txType || undefined,
        limit,
        currentOffset
      );
      const newTransactions = response.data;

      if (reset) {
        setTransactions(newTransactions);
        setOffset(limit);
      } else {
        setTransactions((prev) => [...prev, ...newTransactions]);
        setOffset((prev) => prev + limit);
      }

      setHasMore(newTransactions.length === limit);
      setError(null);
    } catch (err) {
      console.error('거래 내역 로딩 실패:', err);
      setError('거래 내역을 불러오는데 실패했습니다');
      if (offset === 0) {
        setTransactions([]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions(true, filter);
  }, [filter]);

  const handleFilterChange = (newFilter: string) => {
    setFilter(newFilter);
    setOffset(0);
  };

  if (error && transactions.length === 0) {
    return (
      <div style={{ padding: '40px 20px', textAlign: 'center' }}>
        <p style={{ color: '#888', marginBottom: '16px' }}>{error}</p>
        <motion.button
          onClick={() => loadTransactions(true, filter)}
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

  return (
    <div>
      {/* 필터 */}
      <div
        style={{
          padding: '0 20px 16px',
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
        }}
      >
        {filterOptions.map((option) => (
          <motion.button
            key={option.value}
            onClick={() => handleFilterChange(option.value)}
            whileTap={{ scale: 0.95 }}
            style={{
              padding: '8px 16px',
              background:
                filter === option.value
                  ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                  : 'rgba(255,255,255,0.1)',
              border: 'none',
              borderRadius: '20px',
              color: 'white',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {option.label}
          </motion.button>
        ))}
      </div>

      {/* 리스트 */}
      <div style={{ padding: '0 20px 20px' }}>
        {!isLoading && transactions.length === 0 ? (
          <div style={{ padding: '40px 0', textAlign: 'center' }}>
            <svg
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="rgba(255,255,255,0.2)"
              style={{ margin: '0 auto 16px' }}
            >
              <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10H7v-2h10v2z" />
            </svg>
            <p style={{ color: '#888' }}>거래 내역이 없습니다</p>
          </div>
        ) : (
          <>
            {transactions.map((tx) => (
              <TransactionItem key={tx.id} transaction={tx} />
            ))}

            {isLoading && (
              <div style={{ textAlign: 'center', padding: '20px' }}>
                <p style={{ color: '#888' }}>로딩 중...</p>
              </div>
            )}

            {!isLoading && hasMore && (
              <motion.button
                onClick={() => loadTransactions(false, filter)}
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
          </>
        )}
      </div>
    </div>
  );
}
