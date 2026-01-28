'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { botsApi, BotStatus, BotInfo } from '@/lib/bots-api';
import { toast } from 'sonner';
import { RefreshCw, Bot, Play, Pause, UserMinus, Trash2 } from 'lucide-react';

export default function BotsPage() {
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [targetValue, setTargetValue] = useState(0);
  const [saving, setSaving] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await botsApi.getStatus();
      setStatus(data);
      setTargetValue(data.targetCount);
    } catch (error) {
      console.error('Failed to fetch bot status:', error);
      toast.error('봇 상태를 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleTargetChange = async () => {
    if (!status) return;
    if (targetValue === status.targetCount) return;

    setSaving(true);
    try {
      const result = await botsApi.setTargetCount(targetValue);
      if (result.success) {
        toast.success(`목표 봇 수가 ${result.newTarget}로 변경되었습니다.`);
        fetchStatus();
      }
    } catch (error) {
      console.error('Failed to set target:', error);
      toast.error('목표 봇 수 설정에 실패했습니다.');
    } finally {
      setSaving(false);
    }
  };

  const handleSpawnBot = async () => {
    try {
      const result = await botsApi.spawnBot();
      if (result.success) {
        toast.success('봇이 생성되었습니다.');
      } else {
        toast.error(result.message);
      }
      fetchStatus();
    } catch (error) {
      console.error('Failed to spawn bot:', error);
      toast.error('봇 생성에 실패했습니다.');
    }
  };

  const handleRetireBot = async (botId: string, nickname: string) => {
    try {
      const result = await botsApi.retireBot(botId);
      if (result.success) {
        toast.success(`${nickname} 봇 은퇴 요청이 등록되었습니다.`);
        fetchStatus();
      }
    } catch (error) {
      console.error('Failed to retire bot:', error);
      toast.error('봇 은퇴 요청에 실패했습니다.');
    }
  };

  const handleForceRemoveAll = async () => {
    if (!confirm('모든 봇을 즉시 삭제하시겠습니까? 진행 중인 게임에서도 즉시 제거됩니다.')) {
      return;
    }
    try {
      const result = await botsApi.forceRemoveAll();
      if (result.success) {
        toast.success(`${result.removedCount}개의 봇이 삭제되었습니다.`);
        fetchStatus();
      }
    } catch (error) {
      console.error('Failed to force remove all bots:', error);
      toast.error('봇 삭제에 실패했습니다.');
    }
  };

  const getStateBadge = (state: string) => {
    const styles: Record<string, string> = {
      IDLE: 'bg-gray-100 text-gray-700 border-gray-200',
      JOINING: 'bg-blue-100 text-blue-700 border-blue-200',
      PLAYING: 'bg-green-100 text-green-700 border-green-200',
      RESTING: 'bg-yellow-100 text-yellow-700 border-yellow-200',
      REBUYING: 'bg-purple-100 text-purple-700 border-purple-200',
      LEAVING: 'bg-orange-100 text-orange-700 border-orange-200',
    };
    const labels: Record<string, string> = {
      IDLE: '대기',
      JOINING: '입장중',
      PLAYING: '플레이중',
      RESTING: '휴식',
      REBUYING: '리바이',
      LEAVING: '퇴장중',
    };
    return (
      <Badge variant="outline" className={styles[state] || 'bg-gray-100'}>
        {labels[state] || state}
      </Badge>
    );
  };

  const getStrategyBadge = (strategy: string) => {
    const styles: Record<string, string> = {
      tight_aggressive: 'bg-red-100 text-red-700 border-red-200',
      loose_aggressive: 'bg-orange-100 text-orange-700 border-orange-200',
      tight_passive: 'bg-blue-100 text-blue-700 border-blue-200',
      loose_passive: 'bg-cyan-100 text-cyan-700 border-cyan-200',
      balanced: 'bg-green-100 text-green-700 border-green-200',
    };
    const labels: Record<string, string> = {
      tight_aggressive: 'TAG',
      loose_aggressive: 'LAG',
      tight_passive: 'TP',
      loose_passive: 'LP',
      balanced: 'BAL',
    };
    return (
      <Badge variant="outline" className={styles[strategy] || 'bg-gray-100'}>
        {labels[strategy] || strategy}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bot className="h-6 w-6" />
            Live Bot Management
          </h1>
          <p className="text-muted-foreground">
            살아있는 봇 시스템을 관리합니다.
          </p>
        </div>
        <Button variant="outline" onClick={fetchStatus}>
          <RefreshCw className="h-4 w-4 mr-2" />
          새로고침
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              시스템 상태
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {status?.running ? (
                <>
                  <Play className="h-5 w-5 text-green-500" />
                  <span className="text-lg font-bold text-green-600">실행 중</span>
                </>
              ) : (
                <>
                  <Pause className="h-5 w-5 text-gray-400" />
                  <span className="text-lg font-bold text-gray-500">중지됨</span>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              활성 봇
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-2xl font-bold">{status?.activeCount || 0}</span>
            <span className="text-muted-foreground"> / {status?.targetCount || 0}</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              전체 봇
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-2xl font-bold">{status?.totalCount || 0}</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              상태 분포
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1">
            {status?.stateCounts && Object.entries(status.stateCounts)
              .filter(([_, count]) => count > 0)
              .map(([state, count]) => (
                <Badge key={state} variant="secondary" className="text-xs">
                  {state}: {count}
                </Badge>
              ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>봇 수 조절</CardTitle>
          <CardDescription>
            슬라이더로 목표 봇 수를 조절합니다. 시스템이 자동으로 봇 수를 맞춥니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center gap-6">
            <div className="flex-1">
              <Slider
                value={[targetValue]}
                onValueChange={([value]) => setTargetValue(value)}
                max={50}
                step={1}
                className="w-full"
              />
            </div>
            <div className="text-center w-16">
              <div className="text-3xl font-bold">{targetValue}</div>
              <div className="text-xs text-muted-foreground">목표</div>
            </div>
            <Button
              onClick={handleTargetChange}
              disabled={saving || targetValue === status?.targetCount}
            >
              {saving ? '저장 중...' : '적용'}
            </Button>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={handleSpawnBot}>
              <Bot className="h-4 w-4 mr-2" />
              봇 1개 추가
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setTargetValue(0);
              }}
            >
              모든 봇 제거 (목표=0)
            </Button>
            <Button
              variant="destructive"
              onClick={handleForceRemoveAll}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              즉시 전체 삭제
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>봇 목록</CardTitle>
          <CardDescription>
            현재 시스템에서 관리 중인 모든 봇을 표시합니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {status?.bots && status.bots.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>닉네임</TableHead>
                  <TableHead>전략</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>방</TableHead>
                  <TableHead className="text-right">스택</TableHead>
                  <TableHead className="text-right">핸드</TableHead>
                  <TableHead className="text-right">손익</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {status.bots.map((bot: BotInfo) => (
                  <TableRow key={bot.botId}>
                    <TableCell className="font-medium">
                      {bot.nickname}
                      {bot.retireRequested && (
                        <Badge variant="destructive" className="ml-2 text-xs">
                          은퇴 예정
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>{getStrategyBadge(bot.strategy)}</TableCell>
                    <TableCell>{getStateBadge(bot.state)}</TableCell>
                    <TableCell>
                      {bot.roomId ? (
                        <span className="text-sm">
                          {bot.roomId.substring(0, 8)}...
                          <span className="text-muted-foreground ml-1">
                            (좌석 {bot.seat})
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {bot.stack.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {bot.handsPlayed}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      <span className={bot.totalWon - bot.totalLost >= 0 ? 'text-green-600' : 'text-red-600'}>
                        {(bot.totalWon - bot.totalLost).toLocaleString()}
                      </span>
                    </TableCell>
                    <TableCell>
                      {!bot.retireRequested && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRetireBot(bot.botId, bot.nickname)}
                        >
                          <UserMinus className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              현재 활성화된 봇이 없습니다.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
