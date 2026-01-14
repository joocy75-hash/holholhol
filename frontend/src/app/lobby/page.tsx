'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { useGameStore, Table } from '@/stores/game';
import {
  LobbyHeader,
  BottomNavigation,
  GameTabs,
  HoldemCard,
  BannerCarousel,
  TournamentCard,
} from '@/components/lobby';
import type { GameTabType, NavTab } from '@/components/lobby';

// Mock tournament data (준비중)
const mockTournaments = [
  {
    id: 't1',
    name: '프리롤 하이퍼터보 1000만 GTD',
    type: 'tournament' as const,
    status: 'registering' as const,
    startTime: new Date(Date.now() + 8 * 60 * 1000 + 43 * 1000),
    prizePool: 10000000,
    buyIn: 0,
  },
  {
    id: 't2',
    name: '바운티 헌터 하이퍼터보 4.5억 GTD',
    type: 'bounty' as const,
    status: 'registering' as const,
    startTime: new Date(Date.now() + 38 * 60 * 1000 + 43 * 1000),
    prizePool: 600000000,
    buyIn: 50000000,
  },
];

export default function LobbyPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading, fetchUser, logout } = useAuthStore();
  const { tables, seatedRoomIds, isLoading, error, fetchTables, fetchMySeats, leaveTable, clearError } = useGameStore();

  const [activeGameTab, setActiveGameTab] = useState<GameTabType>('all');
  const [activeNavTab, setActiveNavTab] = useState<NavTab>('lobby');
  const [resettingTableId, setResettingTableId] = useState<string | null>(null);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchTables();
      fetchMySeats();
      const interval = setInterval(() => {
        fetchTables();
        fetchMySeats();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, fetchTables, fetchMySeats]);

  // Get the table name for seated room
  const seatedTable = seatedRoomIds.length > 0
    ? tables.find(t => seatedRoomIds.includes(t.id))
    : null;

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  const handleJoinClick = (table: Table) => {
    clearError();
    router.push(`/table/${table.id}`);
  };

  const handleContinueToTable = () => {
    if (seatedRoomIds.length > 0) {
      router.push(`/table/${seatedRoomIds[0]}`);
    }
  };

  const handleNavTabChange = (tab: NavTab) => {
    setActiveNavTab(tab);
    // 다른 탭 클릭 시 준비중 알림 (로비 제외)
    if (tab !== 'lobby') {
      alert('준비중입니다');
      setActiveNavTab('lobby');
    }
  };

  const handleTournamentJoin = () => {
    alert('토너먼트 기능은 준비중입니다');
  };

  // [DEV] 테이블 리셋 핸들러 (로비에서 만석 방 리셋)
  const handleResetTable = async (tableId: string) => {
    if (resettingTableId) return;
    setResettingTableId(tableId);
    try {
      const token = localStorage.getItem('access_token');
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

      // 1. 봇 제거
      await fetch(`${baseUrl}/api/v1/rooms/${tableId}/dev/remove-bots`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      // 2. 테이블 리셋
      await fetch(`${baseUrl}/api/v1/rooms/${tableId}/dev/reset`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      // 테이블 목록 새로고침
      await fetchTables();
    } catch (err) {
      console.error('테이블 리셋 실패:', err);
    } finally {
      setResettingTableId(null);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center lobby-bg">
        <div className="animate-spin h-8 w-8 border-4 border-[var(--neon-purple)] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="min-h-dvh flex justify-center lobby-bg">
      {/* Mobile container */}
      <div className="w-full max-w-[500px] min-h-dvh flex flex-col relative">
        {/* Header */}
        <LobbyHeader
          user={user}
          onLogout={handleLogout}
        />

        {/* Main Content - Scrollable */}
        <main
          className="flex-1 overflow-y-auto scroll-container"
          style={{ paddingBottom: 'calc(var(--lobby-bottom-nav-height) + var(--safe-area-bottom))' }}
        >
          {/* Banner Carousel */}
          <BannerCarousel banners={[]} />

          {/* Game Tabs */}
          <GameTabs activeTab={activeGameTab} onTabChange={setActiveGameTab} />

          {/* Seated Room Banner */}
          {seatedTable && (
            <div className="mx-4 mb-4 p-3 rounded-xl bg-[var(--neon-purple)]/10 border border-[var(--neon-purple)]/50 animate-fade-in">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-[var(--neon-purple-light)]">
                    현재 게임 중인 테이블이 있습니다
                  </p>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                    {seatedTable.name} ({seatedTable.blinds})
                  </p>
                </div>
                <button
                  onClick={handleContinueToTable}
                  className="btn-join"
                >
                  계속하기
                </button>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mx-4 mb-4 p-3 rounded-xl bg-[var(--error)]/10 text-[var(--error)] text-sm border border-[var(--error)]/30">
              {error}
            </div>
          )}

          {/* Game List */}
          <div className="px-4 space-y-3 pb-4">
            {activeGameTab === 'all' ? (
              // 전체 채널 - 토너먼트 + 홀덤 함께 표시
              <>
                {/* 토너먼트 섹션 */}
                <div className="text-center py-3 mb-2">
                  <span className="px-4 py-1 rounded-full bg-[var(--neon-purple)]/20 text-[var(--neon-purple-light)] text-sm font-medium">
                    토너먼트 (준비중)
                  </span>
                </div>
                {mockTournaments.map((tournament) => (
                  <TournamentCard
                    key={tournament.id}
                    {...tournament}
                    onJoin={handleTournamentJoin}
                    disabled={true}
                  />
                ))}

                {/* 홀덤 섹션 */}
                {tables.length > 0 && (
                  <>
                    <div className="text-center py-3 mt-4 mb-2">
                      <span className="px-4 py-1 rounded-full bg-[var(--neon-purple)]/20 text-[var(--neon-purple-light)] text-sm font-medium">
                        홀덤
                      </span>
                    </div>
                    {tables.slice(0, 2).map((table) => (
                      <HoldemCard
                        key={table.id}
                        table={table}
                        onJoin={handleJoinClick}
                        onReset={handleResetTable}
                        isLoading={isLoading}
                        isResetting={resettingTableId === table.id}
                      />
                    ))}
                  </>
                )}
              </>
            ) : activeGameTab === 'holdem' ? (
              // 홀덤 채널
              tables.length > 0 ? (
                tables.slice(0, 2).map((table) => (
                  <HoldemCard
                    key={table.id}
                    table={table}
                    onJoin={handleJoinClick}
                    onReset={handleResetTable}
                    isLoading={isLoading}
                    isResetting={resettingTableId === table.id}
                  />
                ))
              ) : (
                <div className="text-center py-12">
                  <div className="text-4xl mb-3">🃏</div>
                  <h3 className="text-base font-bold mb-1">테이블이 없습니다</h3>
                  <p className="text-xs text-[var(--text-secondary)]">
                    현재 열려 있는 테이블이 없습니다
                  </p>
                </div>
              )
            ) : (
              // 토너먼트 채널 (준비중 - mock data)
              <>
                <div className="text-center py-4 mb-2">
                  <span className="px-4 py-1 rounded-full bg-[var(--neon-purple)]/20 text-[var(--neon-purple-light)] text-sm font-medium">
                    토너먼트 준비중 (미리보기)
                  </span>
                </div>
                {mockTournaments.map((tournament) => (
                  <TournamentCard
                    key={tournament.id}
                    {...tournament}
                    onJoin={handleTournamentJoin}
                    disabled={true}
                  />
                ))}
              </>
            )}
          </div>

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex justify-center py-4">
              <div className="animate-spin h-6 w-6 border-3 border-[var(--neon-purple)] border-t-transparent rounded-full" />
            </div>
          )}
        </main>

        {/* Bottom Navigation */}
        <BottomNavigation
          activeTab={activeNavTab}
          onTabChange={handleNavTabChange}
          badges={{
            shop: true,
            mission: true,
          }}
        />
      </div>
    </div>
  );
}
