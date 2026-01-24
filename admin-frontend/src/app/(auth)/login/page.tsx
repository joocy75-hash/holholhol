'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { authApi } from '@/lib/auth-api';
import { logger } from '@/lib/logger';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState('Ready');

  const handleLogin = async () => {
    logger.log('[Login] Button clicked');
    setStatus('Logging in...');

    if (!username || !password) {
      setError('아이디와 비밀번호를 입력하세요');
      setStatus('Validation failed');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      setStatus('Calling API...');

      // authApi를 사용하여 로그인
      const loginResponse = await authApi.login({ username, password });
      setStatus('Login successful, getting user...');

      // 2FA 필요 시 처리 (향후 구현)
      if (loginResponse.requiresTwoFactor) {
        setError('2FA 인증이 필요합니다. (미구현)');
        setStatus('2FA required');
        return;
      }

      const accessToken = loginResponse.accessToken;

      // authApi를 사용하여 사용자 정보 조회
      const user = await authApi.getCurrentUser(accessToken);
      setStatus('Saving to localStorage...');

      // Save to localStorage
      // JWT 토큰 만료 시간: 24시간 (밀리초)
      const tokenExpiryMs = 24 * 60 * 60 * 1000;
      const tokenExpiry = Date.now() + tokenExpiryMs;

      const authData = {
        state: {
          user: {
            id: user.id,
            username: user.username,
            email: user.email,
            role: user.role || 'admin',
          },
          accessToken: accessToken,
          tokenExpiry: tokenExpiry,
          isAuthenticated: true,
        },
        version: 0,
      };
      localStorage.setItem('admin-auth', JSON.stringify(authData));

      setStatus('Redirecting...');

      // Redirect
      setTimeout(() => {
        window.location.href = '/';
      }, 500);

    } catch (err) {
      logger.error('[Login] Error:', err);
      setError(err instanceof Error ? err.message : '로그인 실패');
      setStatus('Error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Admin Login</CardTitle>
          <p className="text-sm text-gray-500">Status: {status}</p>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">아이디</label>
              <input
                type="text"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">비밀번호</label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>

            {error && (
              <p className="text-sm text-red-500 text-center">{error}</p>
            )}

            <button
              type="button"
              onClick={handleLogin}
              disabled={isLoading}
              className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? '로그인 중...' : '로그인'}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
