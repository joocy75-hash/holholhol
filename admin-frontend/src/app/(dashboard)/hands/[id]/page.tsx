'use client';

import { useEffect, useState, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { handsApi, HandDetail, TimelineAction } from '@/lib/hands-api';
import { HandReplayTimeline } from '@/components/hands/HandReplayTimeline';
import { CardDisplay } from '@/components/hands/CardDisplay';

export default function HandDetailPage() {
  const params = useParams();
  const router = useRouter();
  const handId = params.id as string;

  const [hand, setHand] = useState<HandDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Replay state
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    const fetchHand = async () => {
      try {
        const data = await handsApi.getHandDetail(handId);
        setHand(data);
      } catch (err) {
        console.error('Failed to fetch hand:', err);
        setError('핸드를 찾을 수 없습니다');
      } finally {
        setLoading(false);
      }
    };
    fetchHand();
  }, [handId]);

  // Auto-play effect
  useEffect(() => {
    if (!isPlaying || !hand) return;

    const timer = setTimeout(() => {
      if (currentStep < hand.timeline.length - 1) {
        setCurrentStep((prev) => prev + 1);
      } else {
        setIsPlaying(false);
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [isPlaying, currentStep, hand]);

  // Calculate visible community cards at current step
  const visibleCommunityCards = useMemo(() => {
    if (!hand) return [];

    const currentActions = hand.timeline.slice(0, currentStep + 1);
    const cards: string[] = [];

    for (const action of currentActions) {
      if (action.eventType === 'deal_flop' && action.cards) {
        cards.push(...action.cards);
      } else if ((action.eventType === 'deal_turn' || action.eventType === 'deal_river') && action.cards) {
        cards.push(...action.cards);
      }
    }

    return cards;
  }, [hand, currentStep]);

  // Current phase
  const currentPhase = useMemo(() => {
    if (!hand || currentStep < 0) return 'preflop';
    return hand.timeline[currentStep]?.phase || 'preflop';
  }, [hand, currentStep]);

  const handleExport = async (format: 'json' | 'text') => {
    try {
      const data = await handsApi.exportHand(handId, format);
      const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `hand-${handId}.${format === 'json' ? 'json' : 'txt'}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export hand:', err);
    }
  };

  if (loading) {
    return <div className="text-center py-8">로딩 중...</div>;
  }

  if (error || !hand) {
    return (
      <div className="text-center py-8">
        <p className="text-red-500 mb-4">{error}</p>
        <Button variant="outline" onClick={() => router.back()}>
          뒤로 가기
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.back()}>
            ← 뒤로
          </Button>
          <h1 className="text-2xl font-bold">핸드 #{hand.handNumber}</h1>
          <Badge variant="outline">{currentPhase.toUpperCase()}</Badge>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => handleExport('json')}>
            JSON 내보내기
          </Button>
          <Button variant="outline" onClick={() => handleExport('text')}>
            텍스트 내보내기
          </Button>
        </div>
      </div>

      {/* Hand Info Card */}
      <Card>
        <CardHeader>
          <CardTitle>핸드 정보</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <p className="text-sm text-gray-500">핸드 ID</p>
              <p className="font-mono text-sm">{hand.id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">테이블</p>
              <p>{hand.tableName || '알 수 없음'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">블라인드</p>
              <p>
                {hand.initialState?.smallBlind || 0}/{hand.initialState?.bigBlind || 0}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">총 팟</p>
              <p className="text-xl font-bold">{hand.potSize.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">시작 시간</p>
              <p className="text-sm">
                {hand.startedAt
                  ? new Date(hand.startedAt).toLocaleString('ko-KR')
                  : '-'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Community Cards & Replay Controls */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>커뮤니티 카드</CardTitle>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={currentStep === 0}
                onClick={() => setCurrentStep(0)}
              >
                ⏮ 처음
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={currentStep === 0}
                onClick={() => setCurrentStep((prev) => Math.max(0, prev - 1))}
              >
                ◀ 이전
              </Button>
              <Button
                size="sm"
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? '⏸ 일시정지' : '▶ 재생'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={currentStep >= hand.timeline.length - 1}
                onClick={() => setCurrentStep((prev) => Math.min(hand.timeline.length - 1, prev + 1))}
              >
                다음 ▶
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={currentStep >= hand.timeline.length - 1}
                onClick={() => setCurrentStep(hand.timeline.length - 1)}
              >
                끝 ⏭
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3 justify-center py-4 min-h-24">
            {visibleCommunityCards.length === 0 ? (
              <p className="text-gray-400">커뮤니티 카드가 아직 없습니다</p>
            ) : (
              visibleCommunityCards.map((card, i) => (
                <CardDisplay key={i} card={card} size="lg" />
              ))
            )}
          </div>
          {/* Progress bar */}
          <div className="mt-4">
            <input
              type="range"
              min={0}
              max={hand.timeline.length - 1}
              value={currentStep}
              onChange={(e) => setCurrentStep(parseInt(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>시작</span>
              <span>{currentStep + 1} / {hand.timeline.length}</span>
              <span>종료</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Participants */}
      <Card>
        <CardHeader>
          <CardTitle>참가자 ({hand.participants.length}명)</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>좌석</TableHead>
                <TableHead>플레이어</TableHead>
                <TableHead>홀카드</TableHead>
                <TableHead className="text-right">베팅</TableHead>
                <TableHead className="text-right">획득</TableHead>
                <TableHead className="text-right">순수익</TableHead>
                <TableHead>최종 액션</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {hand.participants
                .sort((a, b) => a.seat - b.seat)
                .map((p) => (
                  <TableRow
                    key={p.userId}
                    className={p.netResult > 0 ? 'bg-green-50' : p.netResult < 0 ? 'bg-red-50' : ''}
                  >
                    <TableCell className="font-medium">
                      {p.seat}
                      {hand.initialState?.dealerPosition === p.seat && (
                        <Badge variant="secondary" className="ml-2">D</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div>
                        <p>{p.nickname || 'Unknown'}</p>
                        <p className="text-xs text-gray-500 font-mono">
                          {p.userId.slice(0, 8)}...
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {p.holeCards?.map((card, i) => (
                          <CardDisplay key={i} card={card} size="sm" />
                        )) || '-'}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      {p.betAmount.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {p.wonAmount.toLocaleString()}
                    </TableCell>
                    <TableCell className={`text-right font-medium ${
                      p.netResult > 0 ? 'text-green-600' : p.netResult < 0 ? 'text-red-600' : ''
                    }`}>
                      {p.netResult > 0 ? '+' : ''}{p.netResult.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.finalAction === 'fold' ? 'secondary' : 'default'}>
                        {p.finalAction}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>타임라인</CardTitle>
        </CardHeader>
        <CardContent>
          <HandReplayTimeline
            timeline={hand.timeline}
            currentStep={currentStep}
            onStepClick={setCurrentStep}
          />
        </CardContent>
      </Card>

      {/* Winners */}
      {hand.result?.winners && hand.result.winners.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>승자</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              {hand.result.winners.map((winner, i) => {
                const participant = hand.participants.find(p => p.userId === winner.userId);
                return (
                  <div key={i} className="bg-green-100 rounded-lg p-4">
                    <p className="font-medium">{participant?.nickname || 'Unknown'}</p>
                    <p className="text-sm text-gray-500">좌석 {winner.seat}</p>
                    <p className="text-xl font-bold text-green-600">
                      +{winner.amount.toLocaleString()}
                    </p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
