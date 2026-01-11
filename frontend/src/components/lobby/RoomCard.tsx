import { Users, Eye, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { Button } from '@/components/common/Button';
import type { LobbyRoom } from '@/types/websocket';

interface RoomCardProps {
  room: LobbyRoom;
  onJoin: (roomId: string) => void;
  onSpectate: (roomId: string) => void;
}

const statusConfig = {
  waiting: {
    label: '대기중',
    color: 'bg-warning/10 text-warning',
    dot: 'bg-warning',
  },
  playing: {
    label: '진행중',
    color: 'bg-success/10 text-success',
    dot: 'bg-success',
  },
  full: {
    label: '가득참',
    color: 'bg-danger/10 text-danger',
    dot: 'bg-danger',
  },
};

export function RoomCard({ room, onJoin, onSpectate }: RoomCardProps) {
  const status = statusConfig[room.status];
  const isFull = room.status === 'full';

  return (
    <div className="card p-4 hover:ring-2 hover:ring-primary/50 transition-all">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <h3 className="font-semibold text-text truncate flex-1 mr-2">{room.name}</h3>
        <span
          className={cn(
            'flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
            status.color
          )}
        >
          <span className={cn('w-1.5 h-1.5 rounded-full', status.dot)} />
          {status.label}
        </span>
      </div>

      {/* Info */}
      <div className="space-y-2 mb-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-text-muted">블라인드</span>
          <span className="font-medium text-text">{room.blinds}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-text-muted flex items-center gap-1">
            <Users className="w-4 h-4" />
            플레이어
          </span>
          <span className="font-medium text-text">
            {room.playerCount} / {room.maxSeats}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onSpectate(room.id)}
          className="flex-1"
        >
          <Eye className="w-4 h-4 mr-1" />
          관전
        </Button>
        <Button
          variant="primary"
          size="sm"
          onClick={() => onJoin(room.id)}
          disabled={isFull}
          className="flex-1"
        >
          입장
          <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}
