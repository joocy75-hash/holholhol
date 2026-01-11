import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { useLobbyStore } from '@/stores/lobbyStore';
import { Button } from '@/components/common/Button';

const BLIND_OPTIONS = [
  { value: null, label: '전체' },
  { value: '10/20', label: '10/20' },
  { value: '25/50', label: '25/50' },
  { value: '50/100', label: '50/100' },
  { value: '100/200', label: '100/200' },
];

const SEAT_OPTIONS = [
  { value: null, label: '전체' },
  { value: 2, label: '2인' },
  { value: 6, label: '6인' },
  { value: 9, label: '9인' },
];

const STATUS_OPTIONS = [
  { value: null, label: '전체' },
  { value: 'waiting', label: '대기중' },
  { value: 'playing', label: '진행중' },
];

export function RoomFilter() {
  const { filters, setFilters, resetFilters } = useLobbyStore();
  const hasFilters = filters.search || filters.blinds || filters.seats || filters.status;

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted" />
        <input
          type="text"
          placeholder="방 이름 검색..."
          value={filters.search}
          onChange={(e) => setFilters({ search: e.target.value })}
          className="input pl-10"
        />
        {filters.search && (
          <button
            onClick={() => setFilters({ search: '' })}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-bg rounded"
          >
            <X className="w-4 h-4 text-text-muted" />
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        {/* Blinds */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-muted">블라인드:</span>
          <div className="flex gap-1">
            {BLIND_OPTIONS.map((option) => (
              <button
                key={option.value ?? 'all'}
                onClick={() => setFilters({ blinds: option.value })}
                className={cn(
                  'px-2 py-1 text-xs rounded transition-colors',
                  filters.blinds === option.value
                    ? 'bg-primary text-white'
                    : 'bg-surface text-text-muted hover:text-text'
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Seats */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-muted">인원:</span>
          <div className="flex gap-1">
            {SEAT_OPTIONS.map((option) => (
              <button
                key={option.value ?? 'all'}
                onClick={() => setFilters({ seats: option.value })}
                className={cn(
                  'px-2 py-1 text-xs rounded transition-colors',
                  filters.seats === option.value
                    ? 'bg-primary text-white'
                    : 'bg-surface text-text-muted hover:text-text'
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Status */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-muted">상태:</span>
          <div className="flex gap-1">
            {STATUS_OPTIONS.map((option) => (
              <button
                key={option.value ?? 'all'}
                onClick={() => setFilters({ status: option.value as 'waiting' | 'playing' | null })}
                className={cn(
                  'px-2 py-1 text-xs rounded transition-colors',
                  filters.status === option.value
                    ? 'bg-primary text-white'
                    : 'bg-surface text-text-muted hover:text-text'
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Reset */}
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={resetFilters}>
            <X className="w-4 h-4 mr-1" />
            필터 초기화
          </Button>
        )}
      </div>
    </div>
  );
}
