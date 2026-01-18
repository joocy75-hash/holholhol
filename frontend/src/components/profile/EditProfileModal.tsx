'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UserProfile } from '@/lib/api';
import { AvatarSelector } from '@/components/common';
import { DEFAULT_AVATAR_ID } from '@/constants/avatars';

interface EditProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: { nickname: string; avatar_url: string }) => Promise<void>;
  user: UserProfile | null;
  isLoading: boolean;
}

export default function EditProfileModal({
  isOpen,
  onClose,
  onSave,
  user,
  isLoading,
}: EditProfileModalProps) {
  const [nickname, setNickname] = useState('');
  const [selectedAvatarId, setSelectedAvatarId] = useState<number>(DEFAULT_AVATAR_ID);
  const [error, setError] = useState('');

  useEffect(() => {
    if (user) {
      setNickname(user.nickname || '');
      // avatar_url이 숫자 문자열이면 파싱, 아니면 기본값
      const avatarId = parseInt(user.avatar_url || '', 10);
      setSelectedAvatarId(isNaN(avatarId) || avatarId < 1 || avatarId > 10 ? DEFAULT_AVATAR_ID : avatarId);
    }
  }, [user]);

  const handleSubmit = async () => {
    setError('');

    if (!nickname.trim()) {
      setError('닉네임을 입력해주세요');
      return;
    }

    if (nickname.length < 2 || nickname.length > 20) {
      setError('닉네임은 2-20자 사이여야 합니다');
      return;
    }

    try {
      // avatar_url 필드에 아바타 ID를 문자열로 저장
      await onSave({ nickname: nickname.trim(), avatar_url: String(selectedAvatarId) });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장에 실패했습니다');
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 200,
            padding: '20px',
          }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%',
              maxWidth: '350px',
              background: 'var(--figma-bg-main)',
              borderRadius: '16px',
              padding: '24px',
              border: '1px solid rgba(255,255,255,0.1)',
            }}
          >
            <h3
              style={{
                fontSize: '20px',
                fontWeight: 700,
                color: 'white',
                margin: '0 0 24px 0',
                textAlign: 'center',
              }}
            >
              프로필 수정
            </h3>

            {/* 아바타 선택 */}
            <div style={{ marginBottom: '20px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  color: '#888',
                  marginBottom: '12px',
                }}
              >
                아바타 선택
              </label>
              <AvatarSelector
                selectedId={selectedAvatarId}
                onSelect={setSelectedAvatarId}
                disabled={isLoading}
              />
            </div>

            {/* 닉네임 입력 */}
            <div style={{ marginBottom: '20px' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  color: '#888',
                  marginBottom: '8px',
                }}
              >
                닉네임
              </label>
              <input
                type="text"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder="닉네임을 입력하세요"
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  background: 'rgba(255,255,255,0.1)',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '16px',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            {/* 에러 메시지 */}
            {error && (
              <p
                style={{
                  color: '#ef4444',
                  fontSize: '14px',
                  marginBottom: '16px',
                  textAlign: 'center',
                }}
              >
                {error}
              </p>
            )}

            {/* 버튼 */}
            <div style={{ display: 'flex', gap: '12px' }}>
              <motion.button
                onClick={onClose}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                style={{
                  flex: 1,
                  padding: '14px',
                  background: 'rgba(255,255,255,0.1)',
                  border: 'none',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '16px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                취소
              </motion.button>
              <motion.button
                onClick={handleSubmit}
                disabled={isLoading}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                style={{
                  flex: 1,
                  padding: '14px',
                  background: isLoading
                    ? 'rgba(255,255,255,0.2)'
                    : 'var(--figma-charge-btn-bg)',
                  border: 'none',
                  borderRadius: '8px',
                  color: 'white',
                  fontSize: '16px',
                  fontWeight: 600,
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                  opacity: isLoading ? 0.7 : 1,
                }}
              >
                {isLoading ? '저장 중...' : '저장'}
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
