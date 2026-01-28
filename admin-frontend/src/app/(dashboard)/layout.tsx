'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import { onAuthError } from '@/lib/api';
import { toast } from 'sonner';

const navItems = [
  { href: '/', label: '대시보드', icon: '📊' },
  { href: '/users', label: '사용자', icon: '👥' },
  { href: '/rooms', label: '방 관리', icon: '🎮' },
  { href: '/hands', label: '핸드 기록', icon: '🃏' },
  { href: '/bots', label: 'Live 봇', icon: '🤖' },
  { href: '/bans', label: '제재 관리', icon: '🚫' },
  { href: '/deposits', label: '입금 관리', icon: '📥' },
  { href: '/partners', label: '파트너 관리', icon: '🤝' },
  { href: '/settlements', label: '정산 관리', icon: '💰' },
  { href: '/suspicious', label: '의심 사용자', icon: '⚠️' },
  { href: '/announcements', label: '이벤트/공지', icon: '📢' },
];

interface AuthState {
  user: {
    id: string;
    username: string;
    email: string;
    role: string;
  } | null;
  accessToken: string | null;
  tokenExpiry: number | null;
  isAuthenticated: boolean;
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [authState, setAuthState] = useState<AuthState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMounted, setIsMounted] = useState(false);

  // Handle auth errors (401) globally
  const handleAuthError = useCallback(() => {
    console.log('[DashboardLayout] Auth error received, logging out');
    localStorage.removeItem('admin-auth');
    toast.error('세션이 만료되었습니다. 다시 로그인해주세요.');
    router.replace('/login');
  }, [router]);

  // Subscribe to auth errors
  useEffect(() => {
    const unsubscribe = onAuthError(handleAuthError);
    return () => unsubscribe();
  }, [handleAuthError]);

  useEffect(() => {
    setIsMounted(true);

    // Read auth state directly from localStorage
    const checkAuth = () => {
      try {
        const stored = localStorage.getItem('admin-auth');
        console.log('[DashboardLayout] Checking auth, stored:', stored ? 'exists' : 'null');

        if (stored) {
          const parsed = JSON.parse(stored);
          console.log('[DashboardLayout] Parsed:', JSON.stringify(parsed.state, null, 2));

          if (parsed.state?.isAuthenticated && parsed.state?.accessToken) {
            // tokenExpiry 검증 (있는 경우에만)
            if (parsed.state.tokenExpiry && Date.now() > parsed.state.tokenExpiry) {
              console.log('[DashboardLayout] Token expired, redirecting to login');
              localStorage.removeItem('admin-auth');
              router.replace('/login');
              return;
            }

            console.log('[DashboardLayout] Auth valid, showing dashboard');
            setAuthState(parsed.state);
            setIsLoading(false);
            return;
          }
        }

        console.log('[DashboardLayout] Not authenticated, redirecting to login');
        router.replace('/login');
      } catch (e) {
        console.error('[DashboardLayout] Error:', e);
        router.replace('/login');
      }
    };

    checkAuth();
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('admin-auth');
    router.replace('/login');
  };

  // 서버/클라이언트 하이드레이션 불일치 방지를 위해
  // 마운트 전에는 전체 레이아웃 구조를 동일하게 유지
  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar - 항상 렌더링 */}
      <aside className="w-64 bg-white shadow-md flex flex-col h-full overflow-hidden">
        <div className="p-4">
          <h1 className="text-xl font-bold text-gray-800">🎰 Admin</h1>
          <p className="text-sm text-gray-500">Holdem Management</p>
        </div>
        <Separator />
        <nav className="p-2 flex-1 overflow-y-auto">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 rounded-md hover:bg-gray-100"
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white shadow-sm px-6 py-4 flex justify-between items-center">
          <div />
          {isMounted && authState?.isAuthenticated ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="flex items-center gap-2">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback>
                      {authState?.user?.username?.charAt(0).toUpperCase() || 'A'}
                    </AvatarFallback>
                  </Avatar>
                  <span className="text-sm">{authState?.user?.username}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem disabled>
                  역할: {authState?.user?.role}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleLogout}>
                  로그아웃
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <div className="h-8 w-24 bg-gray-100 rounded animate-pulse" />
          )}
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-gray-500">로딩 중...</div>
            </div>
          ) : authState?.isAuthenticated ? (
            children
          ) : null}
        </main>
      </div>
    </div>
  );
}
