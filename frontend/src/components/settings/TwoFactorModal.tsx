'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { twoFactorApi, TwoFactorSetupResponse } from '@/lib/api';

interface TwoFactorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
  isEnabled: boolean;
}

export default function TwoFactorModal({
  isOpen,
  onClose,
  onComplete,
  isEnabled,
}: TwoFactorModalProps) {
  const [step, setStep] = useState<'setup' | 'verify' | 'backup' | 'disable'>('setup');
  const [setupData, setSetupData] = useState<TwoFactorSetupResponse | null>(null);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSetup = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await twoFactorApi.setup();
      setSetupData(response.data);
      setStep('verify');
    } catch (err) {
      setError('2FA 설정을 시작할 수 없습니다');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerify = async () => {
    if (code.length !== 6) {
      setError('6자리 코드를 입력해주세요');
      return;
    }

    setIsLoading(true);
    setError('');
    try {
      await twoFactorApi.verify(code);
      setStep('backup');
    } catch (err) {
      setError('코드가 올바르지 않습니다');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisable = async () => {
    if (code.length !== 6) {
      setError('6자리 코드를 입력해주세요');
      return;
    }

    setIsLoading(true);
    setError('');
    try {
      await twoFactorApi.disable(code);
      onComplete();
    } catch (err) {
      setError('코드가 올바르지 않습니다');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setStep(isEnabled ? 'disable' : 'setup');
    setSetupData(null);
    setCode('');
    setError('');
    onClose();
  };

  const handleComplete = () => {
    handleClose();
    onComplete();
  };

  // 모달 열릴 때 초기 상태 설정
  useState(() => {
    if (isOpen) {
      setStep(isEnabled ? 'disable' : 'setup');
    }
  });

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
              maxHeight: '80vh',
              overflow: 'auto',
            }}
          >
            {/* 설정 시작 */}
            {step === 'setup' && !isEnabled && (
              <>
                <h3 style={{ color: 'white', fontSize: '20px', margin: '0 0 16px', textAlign: 'center' }}>
                  2단계 인증 설정
                </h3>
                <p style={{ color: '#888', fontSize: '14px', marginBottom: '24px', textAlign: 'center' }}>
                  Google Authenticator 또는 다른 인증 앱을 사용하여 계정을 보호하세요.
                </p>
                <motion.button
                  onClick={handleSetup}
                  disabled={isLoading}
                  whileTap={{ scale: 0.98 }}
                  style={{
                    width: '100%',
                    padding: '14px',
                    background: 'var(--figma-charge-btn-bg)',
                    border: 'none',
                    borderRadius: '8px',
                    color: 'white',
                    fontSize: '16px',
                    fontWeight: 600,
                    cursor: isLoading ? 'not-allowed' : 'pointer',
                  }}
                >
                  {isLoading ? '로딩 중...' : '설정 시작'}
                </motion.button>
              </>
            )}

            {/* QR 코드 + 코드 입력 */}
            {step === 'verify' && setupData && (
              <>
                <h3 style={{ color: 'white', fontSize: '20px', margin: '0 0 16px', textAlign: 'center' }}>
                  QR 코드 스캔
                </h3>
                <p style={{ color: '#888', fontSize: '14px', marginBottom: '16px', textAlign: 'center' }}>
                  인증 앱에서 아래 QR 코드를 스캔하세요
                </p>
                <div
                  style={{
                    background: 'white',
                    padding: '16px',
                    borderRadius: '12px',
                    marginBottom: '16px',
                    textAlign: 'center',
                  }}
                >
                  <img
                    src={setupData.qr_code}
                    alt="2FA QR Code"
                    style={{ width: '180px', height: '180px' }}
                  />
                </div>
                <p style={{ color: '#666', fontSize: '12px', marginBottom: '16px', textAlign: 'center' }}>
                  또는 수동으로 입력: <code style={{ color: '#f59e0b' }}>{setupData.secret}</code>
                </p>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="6자리 코드 입력"
                  style={{
                    width: '100%',
                    padding: '14px',
                    background: 'rgba(255,255,255,0.1)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    borderRadius: '8px',
                    color: 'white',
                    fontSize: '20px',
                    textAlign: 'center',
                    letterSpacing: '8px',
                    marginBottom: '16px',
                    boxSizing: 'border-box',
                  }}
                />
                {error && (
                  <p style={{ color: '#ef4444', fontSize: '14px', textAlign: 'center', marginBottom: '16px' }}>
                    {error}
                  </p>
                )}
                <motion.button
                  onClick={handleVerify}
                  disabled={isLoading || code.length !== 6}
                  whileTap={{ scale: 0.98 }}
                  style={{
                    width: '100%',
                    padding: '14px',
                    background: code.length === 6 ? 'var(--figma-charge-btn-bg)' : 'rgba(255,255,255,0.2)',
                    border: 'none',
                    borderRadius: '8px',
                    color: 'white',
                    fontSize: '16px',
                    fontWeight: 600,
                    cursor: code.length === 6 ? 'pointer' : 'not-allowed',
                  }}
                >
                  {isLoading ? '확인 중...' : '확인'}
                </motion.button>
              </>
            )}

            {/* 백업 코드 표시 */}
            {step === 'backup' && setupData && (
              <>
                <h3 style={{ color: '#22c55e', fontSize: '20px', margin: '0 0 16px', textAlign: 'center' }}>
                  2FA 활성화 완료!
                </h3>
                <p style={{ color: '#888', fontSize: '14px', marginBottom: '16px', textAlign: 'center' }}>
                  아래 백업 코드를 안전한 곳에 보관하세요. 인증 앱을 사용할 수 없을 때 사용할 수 있습니다.
                </p>
                <div
                  style={{
                    background: 'rgba(255,255,255,0.05)',
                    padding: '16px',
                    borderRadius: '8px',
                    marginBottom: '16px',
                  }}
                >
                  {setupData.backup_codes.map((code, i) => (
                    <p
                      key={i}
                      style={{
                        color: 'white',
                        fontFamily: 'monospace',
                        fontSize: '14px',
                        margin: '4px 0',
                        textAlign: 'center',
                      }}
                    >
                      {code}
                    </p>
                  ))}
                </div>
                <motion.button
                  onClick={handleComplete}
                  whileTap={{ scale: 0.98 }}
                  style={{
                    width: '100%',
                    padding: '14px',
                    background: 'var(--figma-charge-btn-bg)',
                    border: 'none',
                    borderRadius: '8px',
                    color: 'white',
                    fontSize: '16px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  완료
                </motion.button>
              </>
            )}

            {/* 2FA 비활성화 */}
            {(step === 'disable' || (step === 'setup' && isEnabled)) && (
              <>
                <h3 style={{ color: 'white', fontSize: '20px', margin: '0 0 16px', textAlign: 'center' }}>
                  2단계 인증 해제
                </h3>
                <p style={{ color: '#888', fontSize: '14px', marginBottom: '16px', textAlign: 'center' }}>
                  2FA를 해제하려면 인증 앱의 코드를 입력하세요
                </p>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="6자리 코드 입력"
                  style={{
                    width: '100%',
                    padding: '14px',
                    background: 'rgba(255,255,255,0.1)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    borderRadius: '8px',
                    color: 'white',
                    fontSize: '20px',
                    textAlign: 'center',
                    letterSpacing: '8px',
                    marginBottom: '16px',
                    boxSizing: 'border-box',
                  }}
                />
                {error && (
                  <p style={{ color: '#ef4444', fontSize: '14px', textAlign: 'center', marginBottom: '16px' }}>
                    {error}
                  </p>
                )}
                <div style={{ display: 'flex', gap: '12px' }}>
                  <motion.button
                    onClick={handleClose}
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
                    onClick={handleDisable}
                    disabled={isLoading || code.length !== 6}
                    whileTap={{ scale: 0.98 }}
                    style={{
                      flex: 1,
                      padding: '14px',
                      background: code.length === 6 ? '#ef4444' : 'rgba(255,255,255,0.2)',
                      border: 'none',
                      borderRadius: '8px',
                      color: 'white',
                      fontSize: '16px',
                      fontWeight: 600,
                      cursor: code.length === 6 ? 'pointer' : 'not-allowed',
                    }}
                  >
                    {isLoading ? '해제 중...' : '해제'}
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
