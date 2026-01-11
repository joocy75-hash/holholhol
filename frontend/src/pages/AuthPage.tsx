import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Mail, Lock, User, ArrowRight } from 'lucide-react';
import { Button } from '@/components/common/Button';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/uiStore';

type AuthMode = 'login' | 'register';

export function AuthPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, register, isLoading, error, clearError } = useAuthStore();

  const isRegisterPage = location.pathname === '/auth/register';
  const [mode, setMode] = useState<AuthMode>(isRegisterPage ? 'register' : 'login');

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    nickname: '',
    confirmPassword: '',
  });

  const [validationError, setValidationError] = useState<string | null>(null);

  const handleModeChange = (newMode: AuthMode) => {
    setMode(newMode);
    clearError();
    setValidationError(null);
    navigate(newMode === 'register' ? '/auth/register' : '/auth/login', { replace: true });
  };

  const validateForm = (): boolean => {
    if (!formData.email || !formData.password) {
      setValidationError('이메일과 비밀번호를 입력해주세요');
      return false;
    }

    if (!formData.email.includes('@')) {
      setValidationError('올바른 이메일 형식이 아닙니다');
      return false;
    }

    if (formData.password.length < 6) {
      setValidationError('비밀번호는 6자 이상이어야 합니다');
      return false;
    }

    if (mode === 'register') {
      if (!formData.nickname) {
        setValidationError('닉네임을 입력해주세요');
        return false;
      }

      if (formData.nickname.length < 2 || formData.nickname.length > 20) {
        setValidationError('닉네임은 2-20자여야 합니다');
        return false;
      }

      if (formData.password !== formData.confirmPassword) {
        setValidationError('비밀번호가 일치하지 않습니다');
        return false;
      }
    }

    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!validateForm()) return;

    try {
      if (mode === 'login') {
        await login({ email: formData.email, password: formData.password });
        toast.success('로그인 성공!');
      } else {
        await register({
          email: formData.email,
          password: formData.password,
          nickname: formData.nickname,
        });
        toast.success('회원가입 성공!');
      }
      navigate('/lobby');
    } catch {
      // Error is handled by store
    }
  };

  const displayError = validationError || error;

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <span className="text-6xl">🃏</span>
          <h1 className="text-3xl font-bold text-text mt-4">홀덤 1등</h1>
          <p className="text-text-muted mt-2">텍사스 홀덤 포커 게임</p>
        </div>

        {/* Auth Card */}
        <div className="card p-6">
          {/* Mode Tabs */}
          <div className="flex mb-6 bg-bg rounded-lg p-1">
            <button
              onClick={() => handleModeChange('login')}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'login'
                  ? 'bg-surface text-text'
                  : 'text-text-muted hover:text-text'
              }`}
            >
              로그인
            </button>
            <button
              onClick={() => handleModeChange('register')}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'register'
                  ? 'bg-surface text-text'
                  : 'text-text-muted hover:text-text'
              }`}
            >
              회원가입
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-text mb-1">이메일</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData((prev) => ({ ...prev, email: e.target.value }))}
                  placeholder="your@email.com"
                  className="input pl-10"
                  autoComplete="email"
                />
              </div>
            </div>

            {/* Nickname (Register only) */}
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium text-text mb-1">닉네임</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input
                    type="text"
                    value={formData.nickname}
                    onChange={(e) => setFormData((prev) => ({ ...prev, nickname: e.target.value }))}
                    placeholder="게임에서 사용할 닉네임"
                    className="input pl-10"
                    maxLength={20}
                  />
                </div>
              </div>
            )}

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-text mb-1">비밀번호</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData((prev) => ({ ...prev, password: e.target.value }))}
                  placeholder="••••••••"
                  className="input pl-10"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
              </div>
            </div>

            {/* Confirm Password (Register only) */}
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-medium text-text mb-1">비밀번호 확인</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
                  <input
                    type="password"
                    value={formData.confirmPassword}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, confirmPassword: e.target.value }))
                    }
                    placeholder="••••••••"
                    className="input pl-10"
                    autoComplete="new-password"
                  />
                </div>
              </div>
            )}

            {/* Error */}
            {displayError && (
              <div className="p-3 bg-danger/10 border border-danger/30 rounded text-sm text-danger">
                {displayError}
              </div>
            )}

            {/* Submit */}
            <Button type="submit" fullWidth loading={isLoading} className="mt-6">
              {mode === 'login' ? '로그인' : '회원가입'}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-text-muted text-sm mt-6">
          계속 진행하면 이용약관에 동의하는 것으로 간주됩니다.
        </p>
      </div>
    </div>
  );
}
