'use client';

import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { statisticsApi, DailyRevenue, RevenueSummary } from '@/lib/dashboard-api';

export function RevenueChart() {
  const [dailyData, setDailyData] = useState<DailyRevenue[]>([]);
  const [weeklyData, setWeeklyData] = useState<DailyRevenue[]>([]);
  const [monthlyData, setMonthlyData] = useState<DailyRevenue[]>([]);
  const [summary, setSummary] = useState<RevenueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('daily');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [daily, weekly, monthly, sum] = await Promise.all([
          statisticsApi.getDailyRevenue(14),
          statisticsApi.getWeeklyRevenue(8),
          statisticsApi.getMonthlyRevenue(6),
          statisticsApi.getRevenueSummary(),
        ]);
        setDailyData(daily);
        setWeeklyData(weekly);
        setMonthlyData(monthly);
        setSummary(sum);
      } catch (error) {
        console.error('Failed to fetch revenue data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const formatCurrency = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`;
    }
    if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toFixed(0);
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>매출 현황</CardTitle>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <p className="text-gray-400">로딩 중...</p>
        </CardContent>
      </Card>
    );
  }

  const getChartData = () => {
    switch (activeTab) {
      case 'weekly':
        return weeklyData;
      case 'monthly':
        return monthlyData;
      default:
        return dailyData;
    }
  };

  const getXAxisKey = () => {
    switch (activeTab) {
      case 'weekly':
        return 'week_start';
      case 'monthly':
        return 'month';
      default:
        return 'date';
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>매출 현황 (레이크)</CardTitle>
        {summary && (
          <span className="text-lg font-semibold text-green-600">
            총 {formatCurrency(summary.totalRake)} USDT
          </span>
        )}
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="daily">일별</TabsTrigger>
            <TabsTrigger value="weekly">주별</TabsTrigger>
            <TabsTrigger value="monthly">월별</TabsTrigger>
          </TabsList>
          
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={getChartData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey={getXAxisKey()}
                  tick={{ fontSize: 11 }}
                  interval="preserveStartEnd"
                />
                <YAxis 
                  tick={{ fontSize: 11 }}
                  tickFormatter={formatCurrency}
                />
                <Tooltip 
                  formatter={(value) => [`${String(value).toLocaleString()} USDT`, '레이크']}
                />
                <Bar 
                  dataKey="rake" 
                  fill="#10b981" 
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Tabs>
      </CardContent>
    </Card>
  );
}
