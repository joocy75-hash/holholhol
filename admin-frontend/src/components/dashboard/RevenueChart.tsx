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
import { Button } from '@/components/ui/button';
import { dashboardApi, DailyRevenue, RevenueSummary } from '@/lib/dashboard-api';

type DateRange = '7d' | '14d' | '30d' | '90d';

export function RevenueChart() {
  const [dailyData, setDailyData] = useState<DailyRevenue[]>([]);
  const [weeklyData, setWeeklyData] = useState<DailyRevenue[]>([]);
  const [monthlyData, setMonthlyData] = useState<DailyRevenue[]>([]);
  const [summary, setSummary] = useState<RevenueSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('daily');
  const [dateRange, setDateRange] = useState<DateRange>('14d');

  const getDaysFromRange = (range: DateRange): number => {
    switch (range) {
      case '7d': return 7;
      case '14d': return 14;
      case '30d': return 30;
      case '90d': return 90;
      default: return 14;
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const days = getDaysFromRange(dateRange);
        const weeks = Math.ceil(days / 7);
        const months = Math.ceil(days / 30);
        
        const [daily, weekly, monthly, sum] = await Promise.all([
          dashboardApi.getDailyRevenue(days),
          dashboardApi.getWeeklyRevenue(weeks),
          dashboardApi.getMonthlyRevenue(months),
          dashboardApi.getRevenueSummary(),
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
  }, [dateRange]);

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

  const dateRangeOptions: { value: DateRange; label: string }[] = [
    { value: '7d', label: '7일' },
    { value: '14d', label: '14일' },
    { value: '30d', label: '30일' },
    { value: '90d', label: '90일' },
  ];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>매출 현황 (레이크)</CardTitle>
        <div className="flex items-center gap-4">
          {/* Date Range Selector */}
          <div className="flex gap-1">
            {dateRangeOptions.map((option) => (
              <Button
                key={option.value}
                variant={dateRange === option.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => setDateRange(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
          {summary && (
            <span className="text-lg font-semibold text-green-600">
              총 {formatCurrency(summary.totalRake)} USDT
            </span>
          )}
        </div>
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
                  formatter={(value) => [`${Number(value).toLocaleString()} USDT`, '레이크']}
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
