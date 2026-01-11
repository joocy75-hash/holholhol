import { Gamepad2, Plus } from 'lucide-react';
import { useLobbyStore } from '@/stores/lobbyStore';
import { useUIStore } from '@/stores/uiStore';
import { RoomCard } from './RoomCard';
import { SkeletonCard } from '@/components/common/Loading';
import { Button } from '@/components/common/Button';

interface RoomListProps {
  onJoinRoom: (roomId: string) => void;
  onSpectateRoom: (roomId: string) => void;
}

export function RoomList({ onJoinRoom, onSpectateRoom }: RoomListProps) {
  const { isLoading, getFilteredRooms } = useLobbyStore();
  const openModal = useUIStore((s) => s.openModal);
  const rooms = getFilteredRooms();

  // Loading state
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  // Empty state
  if (rooms.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Gamepad2 className="w-16 h-16 text-text-muted mb-4" />
        <h3 className="text-lg font-semibold text-text mb-2">
          현재 열린 방이 없습니다
        </h3>
        <p className="text-text-muted mb-6">
          새로운 방을 만들어 게임을 시작하세요!
        </p>
        <Button onClick={() => openModal('create-room')}>
          <Plus className="w-4 h-4 mr-2" />
          방 만들기
        </Button>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {rooms.map((room) => (
        <RoomCard
          key={room.id}
          room={room}
          onJoin={onJoinRoom}
          onSpectate={onSpectateRoom}
        />
      ))}
    </div>
  );
}
