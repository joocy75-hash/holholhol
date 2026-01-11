import { Link } from '@tanstack/react-router';
import { User, LogOut, Settings } from 'lucide-react';
import { useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { Avatar } from '@/components/common/Avatar';
import { Button } from '@/components/common/Button';
import { formatDollars } from '@/lib/utils/currencyFormatter';

interface HeaderProps {
  showBackButton?: boolean;
  title?: string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps) {
  const { user, isAuthenticated, logout } = useAuthStore();
  const [showMenu, setShowMenu] = useState(false);

  return (
    <header className="sticky top-0 z-40 bg-bg-dark border-b border-surface">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo & Title */}
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold text-text">
            <span className="text-2xl">🃏</span>
            <span className="hidden sm:inline">홀덤 1등</span>
          </Link>

          {title && (
            <div className="hidden sm:block pl-4 border-l border-surface">
              <h1 className="text-sm font-medium text-text">{title}</h1>
              {subtitle && <p className="text-xs text-text-muted">{subtitle}</p>}
            </div>
          )}
        </div>

        {/* Navigation & User */}
        {isAuthenticated && user ? (
          <div className="flex items-center gap-4">
            {/* Balance */}
            <div className="hidden sm:block px-3 py-1.5 bg-surface rounded-full">
              <span className="text-sm font-medium text-success">
                {formatDollars(user.balance)}
              </span>
            </div>

            {/* User Menu */}
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="flex items-center gap-2 p-1.5 rounded-full hover:bg-surface transition-colors"
              >
                <Avatar name={user.nickname} src={user.avatarUrl} size="sm" />
                <span className="hidden sm:inline text-sm text-text">{user.nickname}</span>
              </button>

              {showMenu && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setShowMenu(false)}
                  />
                  <div className="absolute right-0 top-full mt-2 w-48 bg-surface rounded-card shadow-modal z-20">
                    <div className="p-2">
                      <Link
                        to="/profile"
                        className="flex items-center gap-2 px-3 py-2 text-sm text-text rounded hover:bg-bg transition-colors"
                        onClick={() => setShowMenu(false)}
                      >
                        <User className="w-4 h-4" />
                        프로필
                      </Link>
                      <Link
                        to="/profile/settings"
                        className="flex items-center gap-2 px-3 py-2 text-sm text-text rounded hover:bg-bg transition-colors"
                        onClick={() => setShowMenu(false)}
                      >
                        <Settings className="w-4 h-4" />
                        설정
                      </Link>
                      <hr className="my-2 border-bg" />
                      <button
                        onClick={() => {
                          logout();
                          setShowMenu(false);
                        }}
                        className="flex items-center gap-2 px-3 py-2 text-sm text-danger rounded hover:bg-bg transition-colors w-full"
                      >
                        <LogOut className="w-4 h-4" />
                        로그아웃
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Link to="/auth/login">
              <Button variant="ghost" size="sm">
                로그인
              </Button>
            </Link>
            <Link to="/auth/register">
              <Button variant="primary" size="sm">
                회원가입
              </Button>
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
