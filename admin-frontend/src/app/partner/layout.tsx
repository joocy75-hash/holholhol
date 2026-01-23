'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
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
import { AdminRole } from '@/types';

const navItems = [
  { href: '/partner/dashboard', label: '대시보드', icon: '📊' },
  { href: '/partner/referrals', label: '추천 회원', icon: '👥' },
  { href: '/partner/settlements', label: '정산 내역', icon: '💰' },
];

interface AuthState {
  user: {
    id: string;
    username: string;
    email: string;
    role: string;
    partnerId?: string;
    partnerCode?: string;
  } | null;
  accessToken: string | null;
  isAuthenticated: boolean;
}

export default function PartnerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [authState, setAuthState] = useState<AuthState | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Handle auth errors (401) globally
  const handleAuthError = useCallback(() => {
    console.log('[PartnerLayout] Auth error received, logging out');
    localStorage.removeItem('admin-auth');
    toast.error('세션이 만료되었습니다. 다시 로그인해주세요.');
    router.replace('/partner-login');
  }, [router]);

  // Subscribe to auth errors
  useEffect(() => {
    const unsubscribe = onAuthError(handleAuthError);
    return () => unsubscribe();
  }, [handleAuthError]);

  useEffect(() => {
    // Read auth state directly from localStorage
    const checkAuth = () => {
      try {
        const stored = localStorage.getItem('admin-auth');
        console.log('[PartnerLayout] Checking auth, stored:', stored ? 'exists' : 'null');

        if (stored) {
          const parsed = JSON.parse(stored);
          console.log('[PartnerLayout] Parsed role:', parsed.state?.user?.role);

          // Check if authenticated and has partner role
          if (
            parsed.state?.isAuthenticated &&
            parsed.state?.accessToken &&
            parsed.state?.user?.role === AdminRole.PARTNER
          ) {
            console.log('[PartnerLayout] Partner auth valid, showing portal');
            setAuthState(parsed.state);
            setIsLoading(false);
            return;
          }

          // If authenticated but not partner, redirect to appropriate page
          if (parsed.state?.isAuthenticated && parsed.state?.user?.role !== AdminRole.PARTNER) {
            console.log('[PartnerLayout] Not a partner, redirecting to admin dashboard');
            router.replace('/');
            return;
          }
        }

        console.log('[PartnerLayout] Not authenticated, redirecting to partner login');
        router.replace('/partner-login');
      } catch (e) {
        console.error('[PartnerLayout] Error:', e);
        router.replace('/partner-login');
      }
    };

    // Small delay to ensure localStorage is available
    const timer = setTimeout(checkAuth, 100);
    return () => clearTimeout(timer);
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('admin-auth');
    router.replace('/partner-login');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-amber-50 to-orange-100">
        <div className="text-gray-600">로딩 중...</div>
      </div>
    );
  }

  if (!authState?.isAuthenticated) {
    return null;
  }

  return (
    <div className="flex h-screen bg-gradient-to-br from-amber-50 to-orange-100">
      {/* Sidebar */}
      <aside className="w-64 bg-white shadow-lg">
        <div className="p-4">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-800">파트너 포털</h1>
              <p className="text-xs text-gray-500">{authState?.user?.partnerCode || 'Partner'}</p>
            </div>
          </div>
        </div>
        <Separator />
        <nav className="p-2">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors ${
                  isActive
                    ? 'bg-gradient-to-r from-amber-100 to-orange-100 text-amber-800 font-medium'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white shadow-sm px-6 py-4 flex justify-between items-center">
          <div className="text-sm text-gray-500">
            안녕하세요, <span className="font-medium text-gray-800">{authState?.user?.username}</span>님
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="flex items-center gap-2">
                <Avatar className="h-8 w-8 bg-gradient-to-br from-amber-400 to-orange-500">
                  <AvatarFallback className="bg-transparent text-white">
                    {authState?.user?.username?.charAt(0).toUpperCase() || 'P'}
                  </AvatarFallback>
                </Avatar>
                <span className="text-sm">{authState?.user?.username}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem disabled className="text-xs text-gray-500">
                파트너 코드: {authState?.user?.partnerCode}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleLogout}>
                로그아웃
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
