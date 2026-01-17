'use client';

import { motion } from 'framer-motion';
import { WalletTransaction } from '@/lib/api';

interface TransactionItemProps {
  transaction: WalletTransaction;
}

const txTypeLabels: Record<string, { label: string; icon: string; color: string }> = {
  crypto_deposit: { label: '입금', icon: '↓', color: '#22c55e' },
  crypto_withdrawal: { label: '출금', icon: '↑', color: '#ef4444' },
  buy_in: { label: '바이인', icon: '🎰', color: '#f59e0b' },
  cash_out: { label: '캐시아웃', icon: '💰', color: '#22c55e' },
  win: { label: '승리', icon: '🏆', color: '#22c55e' },
  lose: { label: '패배', icon: '📉', color: '#ef4444' },
  rake: { label: '레이크', icon: '🏦', color: '#888' },
  rakeback: { label: '레이크백', icon: '🎁', color: '#22c55e' },
  admin_adjust: { label: '관리자 조정', icon: '⚙️', color: '#3b82f6' },
  bonus: { label: '보너스', icon: '🎁', color: '#22c55e' },
};

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: '대기중', color: '#f59e0b' },
  processing: { label: '처리중', color: '#3b82f6' },
  completed: { label: '완료', color: '#22c55e' },
  failed: { label: '실패', color: '#ef4444' },
  cancelled: { label: '취소', color: '#888' },
};

export default function TransactionItem({ transaction }: TransactionItemProps) {
  const typeInfo = txTypeLabels[transaction.tx_type] || {
    label: transaction.tx_type,
    icon: '•',
    color: '#888',
  };
  const statusInfo = statusLabels[transaction.status] || {
    label: transaction.status,
    color: '#888',
  };

  const isPositive = transaction.krw_amount > 0;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
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
        border: '1px solid rgba(255,255,255,0.1)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        {/* 왼쪽: 아이콘 + 정보 */}
        <div style={{ display: 'flex', gap: '12px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: `${typeInfo.color}20`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px',
            }}
          >
            {typeInfo.icon}
          </div>
          <div>
            <p
              style={{
                margin: 0,
                fontWeight: 600,
                color: 'white',
                fontSize: '14px',
              }}
            >
              {typeInfo.label}
            </p>
            <p
              style={{
                margin: '4px 0 0',
                color: '#888',
                fontSize: '12px',
              }}
            >
              {formatDate(transaction.created_at)}
            </p>
            {transaction.crypto_type && (
              <p
                style={{
                  margin: '4px 0 0',
                  color: '#666',
                  fontSize: '11px',
                }}
              >
                {transaction.crypto_amount} {transaction.crypto_type.toUpperCase()}
              </p>
            )}
          </div>
        </div>

        {/* 오른쪽: 금액 + 상태 */}
        <div style={{ textAlign: 'right' }}>
          <p
            style={{
              margin: 0,
              fontWeight: 700,
              fontSize: '16px',
              color: isPositive ? '#22c55e' : '#ef4444',
            }}
          >
            {isPositive ? '+' : ''}{transaction.krw_amount.toLocaleString()}
          </p>
          <p
            style={{
              margin: '4px 0 0',
              fontSize: '11px',
              color: statusInfo.color,
            }}
          >
            {statusInfo.label}
          </p>
          {transaction.status === 'completed' && (
            <p
              style={{
                margin: '4px 0 0',
                color: '#666',
                fontSize: '11px',
              }}
            >
              잔액: {transaction.krw_balance_after.toLocaleString()}
            </p>
          )}
        </div>
      </div>

      {/* 설명 */}
      {transaction.description && (
        <p
          style={{
            margin: '12px 0 0',
            padding: '8px',
            background: 'rgba(255,255,255,0.05)',
            borderRadius: '6px',
            color: '#888',
            fontSize: '12px',
          }}
        >
          {transaction.description}
        </p>
      )}
    </motion.div>
  );
}
