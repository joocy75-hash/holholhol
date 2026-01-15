'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CCUChart, RevenueChart, ServerHealthCard, MetricCard } from '@/components/dashboard';
import { dashboardApi, DashboardSummary } from '@/lib/dashboard-api';
import { useDashboardStore } from '@/stores/dashboardStore';

export default function DashboardPage() {
  const { exchangeRate } = useDashboardStore();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
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

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="동시 접속자 (CCU)"
          value={displaySummary.ccu}
          icon="👥"
        />
        <MetricCard
          title="일일 활성 사용자 (DAU)"
          value={displaySummary.dau}
          icon="📊"
        />
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
      </div>

      {/* Server Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <CCUChart refreshInterval={5000} />
        </div>
        <ServerHealthCard refreshInterval={10000} />
      </div>

      {/* Revenue Chart */}
      <RevenueChart />

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              오늘 핸드 수
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">-</p>
            <p className="text-xs text-gray-400">통계 API 연동 후 표시</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              오늘 레이크
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">-</p>
            <p className="text-xs text-gray-400">통계 API 연동 후 표시</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              대기 중 출금
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">-</p>
            <p className="text-xs text-gray-400">암호화폐 API 연동 후 표시</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
