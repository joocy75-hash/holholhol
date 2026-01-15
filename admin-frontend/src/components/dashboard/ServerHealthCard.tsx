'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { dashboardApi, ServerHealth } from '@/lib/dashboard-api';
import { cn } from '@/lib/utils';

interface ServerHealthCardProps {
  refreshInterval?: number;
}

export function ServerHealthCard({ refreshInterval = 10000 }: ServerHealthCardProps) {
  const [health, setHealth] = useState<ServerHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await dashboardApi.getServerHealth();
        setHealth(data);
      } catch (error) {
        console.error('Failed to fetch server health:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-100';
      case 'warning':
        return 'text-yellow-600 bg-yellow-100';
      case 'critical':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'healthy':
        return '정상';
      case 'warning':
        return '주의';
      case 'critical':
        return '위험';
      default:
        return '알 수 없음';
    }
  };

  const getProgressColor = (value: number) => {
    if (value > 90) return 'bg-red-500';
    if (value > 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  if (loading || !health) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>서버 상태</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-32">
          <p className="text-gray-400">로딩 중...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle>서버 상태</CardTitle>
        <span className={cn(
          'px-2 py-1 rounded-full text-xs font-medium',
          getStatusColor(health.status)
        )}>
          {getStatusText(health.status)}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* CPU */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-500">CPU</span>
            <span className="font-medium">{health.cpu.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={cn('h-2 rounded-full transition-all', getProgressColor(health.cpu))}
              style={{ width: `${Math.min(health.cpu, 100)}%` }}
            />
          </div>
        </div>

        {/* Memory */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-500">메모리</span>
            <span className="font-medium">{health.memory.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={cn('h-2 rounded-full transition-all', getProgressColor(health.memory))}
              style={{ width: `${Math.min(health.memory, 100)}%` }}
            />
          </div>
        </div>

        {/* Latency */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-500">레이턴시</span>
            <span className={cn(
              'font-medium',
              health.latency > 200 ? 'text-red-600' : 
              health.latency > 100 ? 'text-yellow-600' : 'text-green-600'
            )}>
              {health.latency.toFixed(0)}ms
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
