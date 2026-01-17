'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface ChangePasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { current_password: string; new_password: string }) => Promise<void>;
  isLoading: boolean;
}

export default function ChangePasswordModal({
  isOpen,
  onClose,
  onSubmit,
  isLoading,
}: ChangePasswordModalProps) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async () => {
    setError('');
    setSuccess(false);

    if (!currentPassword) {
      setError('현재 비밀번호를 입력해주세요');
      return;
    }

    if (!newPassword) {
      setError('새 비밀번호를 입력해주세요');
      return;
    }

    if (newPassword.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('새 비밀번호가 일치하지 않습니다');
      return;
    }

    try {
      await onSubmit({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setSuccess(true);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => {
        onClose();
        setSuccess(false);
      }, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : '비밀번호 변경에 실패했습니다');
    }
  };

  const handleClose = () => {
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setError('');
    setSuccess(false);
    onClose();
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
          onClick={handleClose}
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
              비밀번호 변경
            </h3>

            {success ? (
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                style={{ textAlign: 'center', padding: '20px 0' }}
              >
                <div
                  style={{
                    width: '60px',
                    height: '60px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
                    margin: '0 auto 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="white">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                  </svg>
                </div>
                <p style={{ color: '#22c55e', fontWeight: 600 }}>비밀번호가 변경되었습니다</p>
              </motion.div>
            ) : (
              <>
                {/* 현재 비밀번호 */}
                <div style={{ marginBottom: '16px' }}>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '14px',
                      color: '#888',
                      marginBottom: '8px',
                    }}
                  >
                    현재 비밀번호
                  </label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="현재 비밀번호"
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

                {/* 새 비밀번호 */}
                <div style={{ marginBottom: '16px' }}>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '14px',
                      color: '#888',
                      marginBottom: '8px',
                    }}
                  >
                    새 비밀번호
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="새 비밀번호 (8자 이상)"
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

                {/* 새 비밀번호 확인 */}
                <div style={{ marginBottom: '20px' }}>
                  <label
                    style={{
                      display: 'block',
                      fontSize: '14px',
                      color: '#888',
                      marginBottom: '8px',
                    }}
                  >
                    새 비밀번호 확인
                  </label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="새 비밀번호 확인"
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
                    onClick={handleClose}
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
                    {isLoading ? '변경 중...' : '변경'}
                  </motion.button>
                </div>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
