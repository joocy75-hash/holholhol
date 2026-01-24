'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/stores/auth';

// USDT 지갑 주소 유효성 검증 함수
function isValidWalletAddress(address: string, type: 'TRC20' | 'ERC20'): boolean {
  if (!address) return false;

  if (type === 'TRC20') {
    // TRC20 (Tron): T로 시작, Base58, 34자
    return /^T[1-9A-HJ-NP-Za-km-z]{33}$/.test(address);
  } else {
    // ERC20 (Ethereum): 0x로 시작, 16진수, 42자
    return /^0x[a-fA-F0-9]{40}$/.test(address);
  }
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, signup, isLoading, error, clearError } = useAuthStore();

  const [isSignup, setIsSignup] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    nickname: '',
    confirmPassword: '',
    partnerCode: '',
    usdtWalletAddress: '',
    usdtWalletType: 'TRC20' as 'TRC20' | 'ERC20',
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
        if (!formData.usdtWalletAddress) {
          setLocalError('USDT 지갑 주소는 필수입니다.');
          return;
        }
        if (!isValidWalletAddress(formData.usdtWalletAddress, formData.usdtWalletType)) {
          setLocalError(
            formData.usdtWalletType === 'TRC20'
              ? 'TRC20 주소는 T로 시작하는 34자여야 합니다.'
              : 'ERC20 주소는 0x로 시작하는 42자여야 합니다.'
          );
          return;
        }
        await signup(
          formData.username,
          formData.email,
          formData.password,
          formData.nickname,
          formData.partnerCode || undefined,
          formData.usdtWalletAddress,  // 필수 필드
          formData.usdtWalletType
        );
        router.push('/lobby');
      } else {
        await login(formData.username, formData.password);
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
            {/* 아이디 (로그인/회원가입 공통) */}
            <div>
              <label className="block text-xs font-medium mb-2 text-gray-400">
                아이디
              </label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                className="glass-input w-full px-4 py-3 text-base"
                placeholder="아이디를 입력하세요"
                minLength={4}
                maxLength={50}
                pattern="[a-zA-Z0-9_]+"
                title="영문, 숫자, 밑줄(_)만 사용 가능합니다"
                required
              />
            </div>

            {/* 회원가입 시에만 표시되는 필드들 */}
            <AnimatePresence>
              {isSignup && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-4"
                >
                  {/* 이메일 (회원가입만) */}
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

                  {/* 닉네임 */}
                  <div>
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
                  </div>
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

            {/* USDT 지갑 주소 (회원가입 시에만 표시) */}
            <AnimatePresence>
              {isSignup && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-4"
                >
                  {/* 지갑 타입 선택 */}
                  <div>
                    <label className="block text-xs font-medium mb-2 text-gray-400">
                      USDT 지갑 타입
                    </label>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          name="usdtWalletType"
                          value="TRC20"
                          checked={formData.usdtWalletType === 'TRC20'}
                          onChange={handleChange}
                          className="w-4 h-4 accent-blue-500"
                        />
                        <span className="text-sm text-gray-300">TRC20 (Tron)</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          name="usdtWalletType"
                          value="ERC20"
                          checked={formData.usdtWalletType === 'ERC20'}
                          onChange={handleChange}
                          className="w-4 h-4 accent-blue-500"
                        />
                        <span className="text-sm text-gray-300">ERC20 (Ethereum)</span>
                      </label>
                    </div>
                  </div>

                  {/* 지갑 주소 입력 */}
                  <div>
                    <label className="block text-xs font-medium mb-2 text-gray-400">
                      USDT 지갑 주소 <span className="text-red-400">*</span>
                    </label>
                    <input
                      type="text"
                      name="usdtWalletAddress"
                      value={formData.usdtWalletAddress}
                      onChange={handleChange}
                      className={`glass-input w-full px-4 py-3 font-mono text-sm ${
                        formData.usdtWalletAddress && !isValidWalletAddress(formData.usdtWalletAddress, formData.usdtWalletType)
                          ? 'border-red-500/50'
                          : ''
                      }`}
                      placeholder={formData.usdtWalletType === 'TRC20' ? 'T로 시작하는 34자 주소' : '0x로 시작하는 42자 주소'}
                      required
                    />
                    {formData.usdtWalletAddress && !isValidWalletAddress(formData.usdtWalletAddress, formData.usdtWalletType) && (
                      <p className="mt-1 text-xs text-red-400">
                        {formData.usdtWalletType === 'TRC20'
                          ? 'TRC20 주소는 T로 시작하는 34자여야 합니다'
                          : 'ERC20 주소는 0x로 시작하는 42자여야 합니다'}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-gray-500">
                      출금 시 사용할 USDT 지갑 주소입니다 (필수)
                    </p>
                  </div>
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
