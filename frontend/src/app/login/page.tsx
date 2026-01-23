'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/stores/auth';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, signup, isLoading, error, clearError } = useAuthStore();

  const [isSignup, setIsSignup] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    nickname: '',
    confirmPassword: '',
    partnerCode: '',
  });

  // URL 쿼리 파라미터에서 추천 코드 읽기 (예: /login?ref=ABC123)
  useEffect(() => {
    const refCode = searchParams.get('ref');
    if (refCode) {
      setFormData(prev => ({ ...prev, partnerCode: refCode }));
      setIsSignup(true); // 추천 코드가 있으면 자동으로 회원가입 모드로 전환
    }
  }, [searchParams]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    clearError();
    setLocalError(null);
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    try {
      if (isSignup) {
        if (formData.password !== formData.confirmPassword) {
          setLocalError('비밀번호가 일치하지 않습니다.');
          return;
        }
        if (formData.password.length < 8) {
          setLocalError('비밀번호는 8자 이상이어야 합니다.');
          return;
        }
        await signup(formData.email, formData.password, formData.nickname, formData.partnerCode || undefined);
        router.push('/lobby');
      } else {
        await login(formData.email, formData.password);
        router.push('/lobby');
      }
    } catch {
      // Error is handled by store
    }
  };

  const displayError = localError || error;

  return (
    <div className="page-bg-gradient min-h-screen flex flex-col justify-center items-center p-5 relative overflow-hidden">
      {/* 노이즈 텍스처 */}
      <div className="noise-overlay" />

      {/* 배경 장식 원들 */}
      <div
        className="absolute top-[-20%] left-[-10%] w-[400px] h-[400px] rounded-full opacity-20"
        style={{
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.4) 0%, transparent 70%)',
          filter: 'blur(60px)',
        }}
      />
      <div
        className="absolute bottom-[-10%] right-[-10%] w-[300px] h-[300px] rounded-full opacity-15"
        style={{
          background: 'radial-gradient(circle, rgba(139, 92, 246, 0.5) 0%, transparent 70%)',
          filter: 'blur(50px)',
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-[360px] relative z-10"
      >
        {/* 로고 영역 */}
        <div className="text-center mb-8">
          {/* 카드 아이콘 */}
          <motion.div
            className="flex justify-center gap-2 mb-4"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.4 }}
          >
            {['♠', '♥', '♦', '♣'].map((suit, i) => (
              <motion.div
                key={suit}
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ delay: 0.3 + i * 0.1 }}
                className={`w-10 h-12 rounded-lg flex items-center justify-center text-xl font-bold shadow-lg ${
                  i % 2 === 0
                    ? 'bg-white text-gray-900'
                    : 'bg-white text-red-500'
                }`}
                style={{
                  boxShadow: '0 4px 15px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.8)',
                }}
              >
                {suit}
              </motion.div>
            ))}
          </motion.div>

          <h1 className="text-3xl font-bold mb-2">
            <span className="glow-text-blue">POKER</span>{' '}
            <span className="glow-text-gold">HOLDEM</span>
          </h1>
          <p className="text-sm text-gray-400">
            {isSignup ? '새 계정을 만들어보세요' : '로그인하여 게임을 시작하세요'}
          </p>
        </div>

        {/* 로그인 카드 */}
        <motion.div
          className="glass-card p-6"
          layout
        >
          {/* 에러 메시지 */}
          <AnimatePresence>
            {displayError && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm"
              >
                {displayError}
              </motion.div>
            )}
          </AnimatePresence>

          {/* 폼 */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium mb-2 text-gray-400">
                이메일
              </label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                className="glass-input w-full px-4 py-3 text-base"
                placeholder="이메일을 입력하세요"
                required
              />
            </div>

            <AnimatePresence>
              {isSignup && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <label className="block text-xs font-medium mb-2 text-gray-400">
                    닉네임
                  </label>
                  <input
                    type="text"
                    name="nickname"
                    value={formData.nickname}
                    onChange={handleChange}
                    className="glass-input w-full px-4 py-3 text-base"
                    placeholder="닉네임을 입력하세요"
                    required
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <div>
              <label className="block text-xs font-medium mb-2 text-gray-400">
                비밀번호
              </label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                className="glass-input w-full px-4 py-3 text-base"
                placeholder="비밀번호를 입력하세요"
                required
              />
            </div>

            <AnimatePresence>
              {isSignup && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <label className="block text-xs font-medium mb-2 text-gray-400">
                    비밀번호 확인
                  </label>
                  <input
                    type="password"
                    name="confirmPassword"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    className={`glass-input w-full px-4 py-3 text-base ${
                      formData.confirmPassword &&
                      formData.password !== formData.confirmPassword
                        ? 'border-red-500/50'
                        : ''
                    }`}
                    placeholder="비밀번호를 다시 입력하세요"
                    required
                  />
                  {formData.confirmPassword &&
                    formData.password !== formData.confirmPassword && (
                      <p className="mt-2 text-xs text-red-400">
                        비밀번호가 일치하지 않습니다
                      </p>
                    )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* 추천 코드 (회원가입 시에만 표시) */}
            <AnimatePresence>
              {isSignup && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <label className="block text-xs font-medium mb-2 text-gray-400">
                    추천 코드 (선택)
                  </label>
                  <input
                    type="text"
                    name="partnerCode"
                    value={formData.partnerCode}
                    onChange={handleChange}
                    className="glass-input w-full px-4 py-3 text-base"
                    placeholder="추천 코드가 있다면 입력하세요"
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <motion.button
              type="submit"
              disabled={isLoading}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="gradient-btn-primary w-full mt-2 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full"
                  />
                  처리 중...
                </>
              ) : isSignup ? (
                '회원가입'
              ) : (
                '로그인'
              )}
            </motion.button>
          </form>

          {/* 구분선 */}
          <div className="flex items-center gap-4 my-6">
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
            <span className="text-xs text-gray-500">또는</span>
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
          </div>

          {/* 토글 버튼 */}
          <button
            type="button"
            onClick={() => {
              setIsSignup(!isSignup);
              clearError();
              setLocalError(null);
            }}
            className="glass-btn w-full text-center"
          >
            {isSignup
              ? '이미 계정이 있으신가요? 로그인'
              : '계정이 없으신가요? 회원가입'}
          </button>
        </motion.div>

        {/* 하단 텍스트 */}
        <p className="text-center text-xs text-gray-500 mt-6">
          계속 진행하면 서비스 약관 및 개인정보 처리방침에 동의하는 것으로 간주됩니다.
        </p>
      </motion.div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="page-bg-gradient min-h-screen flex items-center justify-center">
        <div className="noise-overlay" />
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          className="w-8 h-8 border-2 border-white/30 border-t-white rounded-full"
        />
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}
