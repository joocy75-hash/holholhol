'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { useAuthStore } from '@/stores/authStore';
import { authApi } from '@/lib/auth-api';
import type { AdminRole } from '@/types';

const loginSchema = z.object({
  email: z.string().email('유효한 이메일을 입력하세요'),
  password: z.string().min(1, '비밀번호를 입력하세요'),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [requires2FA, setRequires2FA] = useState(false);
  const [twoFactorToken, setTwoFactorToken] = useState<string | null>(null);
  const [twoFactorCode, setTwoFactorCode] = useState('');

  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await authApi.login(data);

      if (response.requiresTwoFactor && response.twoFactorToken) {
        setRequires2FA(true);
        setTwoFactorToken(response.twoFactorToken);
        setIsLoading(false);
        return;
      }

      // Get user info
      const user = await authApi.getCurrentUser(response.accessToken);
      setAuth(user, response.accessToken);
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : '로그인 중 오류가 발생했습니다');
    } finally {
      setIsLoading(false);
    }
  };

  const handle2FASubmit = async () => {
    if (!twoFactorToken || !twoFactorCode) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await authApi.verify2FA(twoFactorCode, twoFactorToken);
      const user = await authApi.getCurrentUser(response.accessToken);
      setAuth(user, response.accessToken);
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : '2FA 인증 실패');
    } finally {
      setIsLoading(false);
    }
  };

  if (requires2FA) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">🔐 2단계 인증</CardTitle>
            <p className="text-sm text-gray-500">
              인증 앱에서 6자리 코드를 입력하세요
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              type="text"
              placeholder="000000"
              value={twoFactorCode}
              onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="text-center text-2xl tracking-widest"
              maxLength={6}
            />

            {error && (
              <p className="text-sm text-red-500 text-center">{error}</p>
            )}

            <Button
              onClick={handle2FASubmit}
              className="w-full"
              disabled={isLoading || twoFactorCode.length !== 6}
            >
              {isLoading ? '확인 중...' : '확인'}
            </Button>

            <Button
              variant="ghost"
              className="w-full"
              onClick={() => {
                setRequires2FA(false);
                setTwoFactorToken(null);
                setTwoFactorCode('');
              }}
            >
              뒤로 가기
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">🎰 Admin Login</CardTitle>
          <p className="text-sm text-gray-500">Holdem Management System</p>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>이메일</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        placeholder="admin@holdem.com"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>비밀번호</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="••••••••" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {error && (
                <p className="text-sm text-red-500 text-center">{error}</p>
              )}

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? '로그인 중...' : '로그인'}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
