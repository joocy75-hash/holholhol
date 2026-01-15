'use client';

import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { dashboardApi, CCUHistoryItem } from '@/lib/dashboard-api';

interface CCUChartProps {
  refreshInterval?: number; // ms
}

export function CCUChart({ refreshInterval = 5000 }: CCUChartProps) {
  const [data, setData] = useState<CCUHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentCCU, setCurrentCCU] = useState(0);

  const fetchData = async () => {
    try {
      const [history, current] = await Promise.all([
        dashboardApi.getCCUHistory(24),
        dashboardApi.getCCU(),
      ]);
      setData(history);
      setCurrentCCU(current.ccu);
    } catch (error) {
      console.error('Failed to fetch CCU data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>CCU 추이</CardTitle>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <p className="text-gray-400">로딩 중...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>CCU 추이 (24시간)</CardTitle>
        <span className="text-2xl font-bold text-blue-600">
          {currentCCU.toLocaleString()}
        </span>
      </CardHeader>
      <CardContent className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="hour" 
              tick={{ fontSize: 12 }}
              interval="preserveStartEnd"
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip 
              formatter={(value) => [String(value).toLocaleString(), 'CCU']}
              labelFormatter={(label) => `시간: ${label}`}
            />
            <Line
              type="monotone"
              dataKey="ccu"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
