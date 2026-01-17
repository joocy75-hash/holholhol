'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CCUChart, DAUChart, RevenueChart, ServerHealthCard, MetricCard } from '@/components/dashboard';
import { dashboardApi, DashboardSummary, UserStatisticsSummary, GameStatistics } from '@/lib/dashboard-api';
import { useDashboardStore } from '@/stores/dashboardStore';

export default function DashboardPage() {
  const { exchangeRate } = useDashboardStore();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [userStats, setUserStats] = useState<UserStatisticsSummary | null>(null);
  const [gameStats, setGameStats] = useState<GameStatistics | null>(null);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const data = await dashboardApi.getSummary();
        setSummary(data);
      } catch (error) {
        console.error('Failed to fetch dashboard summary:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
    const interval = setInterval(fetchSummary, 5000);
    return () => clearInterval(interval);
  }, []);

  // 사용자 통계 (CCU/DAU/WAU/MAU) 가져오기
  useEffect(() => {
    const fetchUserStats = async () => {
      try {
        const data = await dashboardApi.getUserStatisticsSummary();
        setUserStats(data);
      } catch (error) {
        console.error('Failed to fetch user statistics:', error);
      }
    };

    fetchUserStats();
    const interval = setInterval(fetchUserStats, 30000); // 30초마다 갱신
    return () => clearInterval(interval);
  }, []);

  // 게임 통계 가져오기
  useEffect(() => {
    const fetchGameStats = async () => {
      try {
        const data = await dashboardApi.getGameStatistics();
        setGameStats(data);
      } catch (error) {
        console.error('Failed to fetch game statistics:', error);
      }
    };

    fetchGameStats();
    const interval = setInterval(fetchGameStats, 60000); // 1분마다 갱신
    return () => clearInterval(interval);
  }, []);

  // Fallback data
  const displaySummary = summary || {
    ccu: 0,
    dau: 0,
    activeRooms: 0,
    totalPlayers: 0,
    serverHealth: {
      cpu: 0,
      memory: 0,
      latency: 0,
      status: 'unknown' as const,
    },
  };

  const displayRate = exchangeRate || {
    rate: 1380,
    source: 'Upbit',
    timestamp: new Date().toISOString(),
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">대시보드</h1>
        <p className="text-sm text-gray-500">
          {currentTime.toLocaleString('ko-KR')}
        </p>
      </div>

      {/* Key Metrics - CCU, DAU, WAU, MAU */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="동시 접속자 (CCU)"
          value={userStats?.ccu ?? displaySummary.ccu}
          icon="👥"
        />
        <MetricCard
          title="일일 활성 사용자 (DAU)"
          value={userStats?.dau ?? displaySummary.dau}
          icon="📊"
        />
        <MetricCard
          title="주간 활성 사용자 (WAU)"
          value={userStats?.wau ?? 0}
          icon="📈"
        />
        <MetricCard
          title="월간 활성 사용자 (MAU)"
          value={userStats?.mau ?? 0}
          icon="📆"
        />
      </div>

      {/* Room & Exchange Rate */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="활성 방"
          value={displaySummary.activeRooms}
          subtitle={`${displaySummary.totalPlayers}명 플레이 중`}
          icon="🎮"
        />
        <MetricCard
          title="USDT/KRW 환율"
          value={`₩${displayRate.rate.toLocaleString()}`}
          subtitle={`출처: ${displayRate.source}`}
          icon="💱"
        />
        <MetricCard
          title="오늘 핸드 수"
          value={gameStats?.today?.hands ?? 0}
          icon="🃏"
        />
        <MetricCard
          title="오늘 레이크"
          value={`${(gameStats?.today?.rake ?? 0).toLocaleString()} 칩`}
          icon="💰"
        />
      </div>

      {/* Server Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <CCUChart refreshInterval={5000} />
        </div>
        <ServerHealthCard refreshInterval={10000} />
      </div>

      {/* DAU Chart */}
      <DAUChart refreshInterval={60000} days={14} />

      {/* Revenue Chart */}
      <RevenueChart />

      {/* Game Statistics Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              전체 핸드 수
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {(gameStats?.total?.hands ?? 0).toLocaleString()}
            </p>
            <p className="text-xs text-gray-400">누적</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              전체 레이크
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {(gameStats?.total?.rake ?? 0).toLocaleString()}
            </p>
            <p className="text-xs text-gray-400">누적 칩</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              오늘 활성 방
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {gameStats?.today?.rooms ?? 0}
            </p>
            <p className="text-xs text-gray-400">오늘 게임이 진행된 방</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              서버 상태
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${
              displaySummary.serverHealth.status === 'healthy' ? 'text-green-500' :
              displaySummary.serverHealth.status === 'warning' ? 'text-yellow-500' :
              displaySummary.serverHealth.status === 'critical' ? 'text-red-500' :
              'text-gray-500'
            }`}>
              {displaySummary.serverHealth.status === 'healthy' ? '정상' :
               displaySummary.serverHealth.status === 'warning' ? '주의' :
               displaySummary.serverHealth.status === 'critical' ? '위험' :
               '알 수 없음'}
            </p>
            <p className="text-xs text-gray-400">
              CPU: {displaySummary.serverHealth.cpu}% / MEM: {displaySummary.serverHealth.memory}%
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
