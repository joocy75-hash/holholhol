'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import LobbyHeader from '@/components/lobby/LobbyHeader';
import BannerCarousel from '@/components/lobby/BannerCarousel';
import GameTabs, { TabType } from '@/components/lobby/GameTabs';
import TournamentCard from '@/components/lobby/TournamentCard';
import HoldemCard from '@/components/lobby/HoldemCard';
import BottomNavigation from '@/components/lobby/BottomNavigation';
// import QuickJoinButton from '@/components/lobby/QuickJoinButton'; // 임시 숨김
import { tablesApi } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

type GameType = 'tournament' | 'holdem';

interface Room {
  id: string;
  name: string;
  blinds: string;
  maxSeats: number;
  playerCount: number;
  status: string;
  isPrivate: boolean;
  buyInMin: number;
  buyInMax: number;
  roomType?: 'cash' | 'tournament'; // 백엔드에서 제공
  gameType?: GameType; // UI 표시용
}

// 게임 타입 결정 (roomType=tournament 우선, 그 외는 이름 기반 판단)
function determineGameType(room: Room): GameType {
  // 백엔드에서 tournament로 명시적 지정된 경우
  if (room.roomType === 'tournament') {
    return 'tournament';
  }

  // 이름 기반 판단 (기존 방들은 roomType="cash"가 기본값이라 이름으로 판단)
  const name = room.name.toLowerCase();
  if (
    name.includes('토너먼트') ||
    name.includes('tournament') ||
    name.includes('프리롤') ||
    name.includes('freeroll') ||
    name.includes('gtd') ||
    name.includes('하이퍼') ||
    name.includes('turbo')
  ) {
    return 'tournament';
  }
  return 'holdem';
}

export default function LobbyPage() {
  const router = useRouter();
  const { fetchUser } = useAuthStore();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('all');

  // 유저 정보 로드 (새로고침 시 필요)
  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const fetchRooms = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await tablesApi.list();
      setRooms(response.data.rooms || []);
    } catch (err) {
      const errorMessage = err instanceof Error
        ? err.message
        : '방 목록을 불러오는데 실패했습니다';
      setError(errorMessage);
      console.error('방 목록 로드 실패:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRooms();
  }, [fetchRooms]);

  // 필터링된 방 목록
  const filteredRooms = useMemo(() => {
    return rooms.map(room => ({
      ...room,
      gameType: determineGameType(room),
    }));
  }, [rooms]);

  // 탭에 따라 표시할 방 분류
  const { tournamentRooms, holdemRooms } = useMemo(() => {
    const tournament = filteredRooms.filter(r => r.gameType === 'tournament');
    const holdem = filteredRooms.filter(r => r.gameType === 'holdem');
    return { tournamentRooms: tournament, holdemRooms: holdem };
  }, [filteredRooms]);

  // 탭에 따른 표시 여부
  const showTournament = activeTab === 'all' || activeTab === 'tournament';
  const showHoldem = activeTab === 'all' || activeTab === 'holdem';

  const handleJoinRoom = (roomId: string) => {
    router.push(`/table/${roomId}`);
  };

  const handleRetry = () => {
    fetchRooms();
  };

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
  };

  // 에러 상태 UI
  if (error) {
    return (
      <div
        style={{
          position: 'relative',
          width: '390px',
          minHeight: '858px',
          margin: '0 auto',
          background: 'var(--figma-bg-main)',
        }}
      >
        {/* 헤더 */}
        <div style={{ position: 'absolute', left: 0, top: 0, zIndex: 1 }}>
          <LobbyHeader />
        </div>

        {/* 에러 메시지 */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4 p-6 text-center">
            <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
              <svg
                className="w-8 h-8 text-red-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-primary mb-2">
                연결 오류
              </h3>
              <p className="text-sm text-text-secondary mb-4">
                {error}
              </p>
            </div>
            <button
              onClick={handleRetry}
              className="px-6 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
            >
              다시 시도
            </button>
          </div>
        </div>

        {/* 하단 네비게이션 */}
        <BottomNavigation />
      </div>
    );
  }

  // 로딩 중이면 스켈레톤 UI 표시
  if (loading) {
    return (
      <div
        style={{
          position: 'relative',
          width: '390px',
          minHeight: '858px',
          margin: '0 auto',
          background: 'var(--figma-bg-main)',
        }}
      >
        {/* 헤더 스켈레톤 */}
        <div style={{ padding: '16px' }}>
          <div className="flex justify-between items-center mb-4">
            <div className="w-24 h-8 bg-surface animate-pulse rounded-md" />
            <div className="flex gap-2">
              <div className="w-8 h-8 bg-surface animate-pulse rounded-full" />
              <div className="w-8 h-8 bg-surface animate-pulse rounded-full" />
            </div>
          </div>
        </div>

        {/* 배너 스켈레톤 */}
        <div style={{ position: 'absolute', left: '8px', top: '156px', right: '8px' }}>
          <div className="w-full h-[180px] bg-surface animate-pulse rounded-xl" />
        </div>

        {/* 탭 스켈레톤 */}
        <div style={{ position: 'absolute', left: '10px', top: '358px' }}>
          <div className="flex gap-4">
            <div className="w-16 h-8 bg-surface animate-pulse rounded-md" />
            <div className="w-16 h-8 bg-surface animate-pulse rounded-md" />
            <div className="w-16 h-8 bg-surface animate-pulse rounded-md" />
          </div>
        </div>

        {/* 카드 스켈레톤들 */}
        <div style={{ position: 'absolute', left: '10px', top: '392px', right: '10px' }}>
          <div className="w-full h-[120px] bg-surface animate-pulse rounded-xl mb-4" />
          <div className="w-full h-[120px] bg-surface animate-pulse rounded-xl" />
        </div>

        {/* 중앙 로딩 인디케이터 */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span className="text-text-secondary text-sm">테이블 목록 로딩 중...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'relative',
        width: '390px',
        minHeight: '858px',
        margin: '0 auto',
        background: 'var(--figma-bg-main)',
      }}
    >
      {/* 배경 이미지 (opacity 50%) - 맨 뒤 레이어 */}
      <div
        style={{
          position: 'absolute',
          left: '2px',
          top: '88px',
          width: '388px',
          height: '687px',
          opacity: 0.3,
          pointerEvents: 'none',
          zIndex: 0,
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="https://www.figma.com/api/mcp/asset/8f7b90fa-8a33-4ede-997d-20831e008a85"
          alt="background"
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
      </div>

      {/* 헤더 (0-148px) */}
      <div style={{ position: 'absolute', left: 0, top: 0, zIndex: 1 }}>
        <LobbyHeader />
      </div>

      {/* 배너 (156-348px) */}
      <div style={{ position: 'absolute', left: '8px', top: '156px', zIndex: 1 }}>
        <BannerCarousel />
      </div>

      {/* 게임 탭 */}
      <div style={{ position: 'absolute', left: '10px', top: '358px', zIndex: 1 }}>
        <GameTabs onTabChange={handleTabChange} />
      </div>

      {/* 방 목록 - 스크롤 가능한 영역 */}
      <div
        style={{
          position: 'absolute',
          left: '10px',
          top: '392px',
          right: '10px',
          bottom: 0,
          overflowY: 'auto',
          overflowX: 'hidden',
          zIndex: 1,
          scrollbarWidth: 'none', // Firefox
          msOverflowStyle: 'none', // IE/Edge
        }}
        className="hide-scrollbar"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingBottom: '110px' }}>
          {/* 토너먼트 카드들 */}
          {showTournament && tournamentRooms.map((room) => (
            <TournamentCard
              key={room.id}
              roomId={room.id}
              name={room.name}
              buyIn={room.buyInMin}
              onJoin={handleJoinRoom}
            />
          ))}

          {/* 토너먼트 표시인데 방이 없을 때 기본 카드 표시 */}
          {showTournament && tournamentRooms.length === 0 && (
            <TournamentCard />
          )}

          {/* 홀덤 카드들 */}
          {showHoldem && holdemRooms.map((room) => (
            <HoldemCard
              key={room.id}
              roomId={room.id}
              name={room.name}
              maxSeats={room.maxSeats}
              buyIn={room.buyInMin}
              onJoin={handleJoinRoom}
            />
          ))}

          {/* 홀덤 표시인데 방이 없을 때 기본 카드 표시 */}
          {showHoldem && holdemRooms.length === 0 && (
            <HoldemCard />
          )}
        </div>
      </div>

      {/* 하단 네비게이션 (fixed) */}
      <BottomNavigation />
    </div>
  );
}
