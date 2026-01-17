'use client';

import { TimelineAction } from '@/lib/hands-api';
import { Badge } from '@/components/ui/badge';

interface HandReplayTimelineProps {
  timeline: TimelineAction[];
  currentStep: number;
  onStepClick: (step: number) => void;
}

/**
 * 핸드 리플레이 타임라인 컴포넌트
 */
export function HandReplayTimeline({
  timeline,
  currentStep,
  onStepClick,
}: HandReplayTimelineProps) {
  // Get action display info
  const getActionInfo = (action: TimelineAction) => {
    const { eventType, amount, cards, playerNickname, playerSeat } = action;

    // Format player name
    const player = playerNickname || (playerSeat !== null ? `좌석 ${playerSeat}` : '');

    switch (eventType) {
      case 'post_blind':
        return {
          icon: '💰',
          text: `${player} 블라인드 ${amount?.toLocaleString()}`,
          color: 'bg-gray-100 text-gray-700',
        };
      case 'deal_hole_cards':
        return {
          icon: '🃏',
          text: '홀카드 딜',
          color: 'bg-blue-100 text-blue-700',
        };
      case 'deal_flop':
        return {
          icon: '🎴',
          text: `플랍 [${cards?.join(' ') || ''}]`,
          color: 'bg-purple-100 text-purple-700',
        };
      case 'deal_turn':
        return {
          icon: '🎴',
          text: `턴 [${cards?.[0] || ''}]`,
          color: 'bg-purple-100 text-purple-700',
        };
      case 'deal_river':
        return {
          icon: '🎴',
          text: `리버 [${cards?.[0] || ''}]`,
          color: 'bg-purple-100 text-purple-700',
        };
      case 'fold':
        return {
          icon: '❌',
          text: `${player} 폴드`,
          color: 'bg-gray-100 text-gray-700',
        };
      case 'check':
        return {
          icon: '✓',
          text: `${player} 체크`,
          color: 'bg-green-100 text-green-700',
        };
      case 'call':
        return {
          icon: '📞',
          text: `${player} 콜 ${amount?.toLocaleString()}`,
          color: 'bg-green-100 text-green-700',
        };
      case 'bet':
        return {
          icon: '💵',
          text: `${player} 베팅 ${amount?.toLocaleString()}`,
          color: 'bg-yellow-100 text-yellow-700',
        };
      case 'raise':
        return {
          icon: '⬆️',
          text: `${player} 레이즈 ${amount?.toLocaleString()}`,
          color: 'bg-orange-100 text-orange-700',
        };
      case 'all_in':
        return {
          icon: '🔥',
          text: `${player} 올인 ${amount?.toLocaleString()}`,
          color: 'bg-red-100 text-red-700',
        };
      case 'showdown':
        return {
          icon: '👀',
          text: '쇼다운',
          color: 'bg-indigo-100 text-indigo-700',
        };
      case 'pot_won':
        return {
          icon: '🏆',
          text: `${player} 팟 획득 ${amount?.toLocaleString()}`,
          color: 'bg-green-100 text-green-700',
        };
      case 'hand_end':
        return {
          icon: '🏁',
          text: '핸드 종료',
          color: 'bg-gray-100 text-gray-700',
        };
      default:
        return {
          icon: '•',
          text: `${player} ${eventType} ${amount ? amount.toLocaleString() : ''}`,
          color: 'bg-gray-100 text-gray-700',
        };
    }
  };

  // Get phase badge
  const getPhaseBadge = (phase: string | null) => {
    if (!phase) return null;

    const phaseLabels: Record<string, { label: string; variant: 'default' | 'secondary' | 'outline' }> = {
      preflop: { label: 'PREFLOP', variant: 'outline' },
      flop: { label: 'FLOP', variant: 'secondary' },
      turn: { label: 'TURN', variant: 'secondary' },
      river: { label: 'RIVER', variant: 'secondary' },
      showdown: { label: 'SHOWDOWN', variant: 'default' },
      finished: { label: 'FINISHED', variant: 'default' },
    };

    const config = phaseLabels[phase];
    if (!config) return null;

    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  // Group timeline by phase
  const groupedTimeline = timeline.reduce((acc, action, index) => {
    const phase = action.phase || 'preflop';
    if (!acc[phase]) {
      acc[phase] = [];
    }
    acc[phase].push({ ...action, originalIndex: index });
    return acc;
  }, {} as Record<string, (TimelineAction & { originalIndex: number })[]>);

  const phaseOrder = ['preflop', 'flop', 'turn', 'river', 'showdown', 'finished'];

  return (
    <div className="space-y-4">
      {phaseOrder.map((phase) => {
        const actions = groupedTimeline[phase];
        if (!actions || actions.length === 0) return null;

        return (
          <div key={phase} className="space-y-2">
            <div className="flex items-center gap-2 mb-2">
              {getPhaseBadge(phase)}
              <span className="text-sm text-gray-500">
                ({actions.length}개 액션)
              </span>
            </div>
            <div className="pl-4 border-l-2 border-gray-200 space-y-2">
              {actions.map((action) => {
                const info = getActionInfo(action);
                const isActive = action.originalIndex === currentStep;
                const isPast = action.originalIndex < currentStep;

                return (
                  <div
                    key={action.originalIndex}
                    onClick={() => onStepClick(action.originalIndex)}
                    className={`
                      flex items-center gap-3 p-2 rounded cursor-pointer
                      transition-all duration-200
                      ${isActive ? 'ring-2 ring-blue-500 bg-blue-50' : ''}
                      ${isPast ? 'opacity-60' : ''}
                      hover:bg-gray-50
                    `}
                  >
                    <span className="text-sm text-gray-400 w-6 text-right">
                      #{action.seqNo}
                    </span>
                    <span className="text-lg">{info.icon}</span>
                    <span
                      className={`
                        px-2 py-1 rounded text-sm
                        ${info.color}
                      `}
                    >
                      {info.text}
                    </span>
                    {action.timestamp && (
                      <span className="text-xs text-gray-400 ml-auto">
                        {new Date(action.timestamp).toLocaleTimeString('ko-KR')}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
