'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  cryptoDashboardApi,
  CryptoSummaryStats,
  DailyStat,
  TrendAnalysis,
  WalletBalance,
  WalletAlertStatus,
  AutomationStatus,
  TopUser,
} from '@/lib/crypto-dashboard-api';
import { toast } from 'sonner';
import {
  WalletIcon,
  RefreshCwIcon,
  AlertTriangleIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  MinusIcon,
  CircleDollarSignIcon,
  SendIcon,
  DownloadIcon,
  ActivityIcon,
  UsersIcon,
} from 'lucide-react';
import Link from 'next/link';

export default function CryptoDashboardPage() {
  const [summaryStats, setSummaryStats] = useState<CryptoSummaryStats | null>(null);
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([]);
  const [trendAnalysis, setTrendAnalysis] = useState<TrendAnalysis | null>(null);
  const [walletBalance, setWalletBalance] = useState<WalletBalance | null>(null);
  const [alertStatus, setAlertStatus] = useState<WalletAlertStatus | null>(null);
  const [automationStatus, setAutomationStatus] = useState<AutomationStatus | null>(null);
  const [topUsers, setTopUsers] = useState<TopUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [periodDays, setPeriodDays] = useState('30');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [summary, daily, trend, wallet, alerts, automation, users] = await Promise.all([
        cryptoDashboardApi.getSummaryStats(parseInt(periodDays)),
        cryptoDashboardApi.getDailyStats(parseInt(periodDays)),
        cryptoDashboardApi.getTrendAnalysis(7),
        cryptoDashboardApi.getWalletBalance().catch(() => null),
        cryptoDashboardApi.getWalletAlertStatus().catch(() => null),
        cryptoDashboardApi.getAutomationStatus().catch(() => null),
        cryptoDashboardApi.getTopUsers(parseInt(periodDays), 5),
      ]);

      setSummaryStats(summary);
      setDailyStats(daily.items);
      setTrendAnalysis(trend);
      setWalletBalance(wallet);
      setAlertStatus(alerts);
      setAutomationStatus(automation);
      setTopUsers(users.items);
    } catch (error) {
      console.error('Failed to fetch crypto dashboard data:', error);
      toast.error('데이터를 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [periodDays]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleForceCheck = async () => {
    try {
      await cryptoDashboardApi.forceWalletCheck();
      toast.success('지갑 잔액 체크가 완료되었습니다.');
      fetchData();
    } catch (error) {
      toast.error('지갑 잔액 체크에 실패했습니다.');
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ko-KR').format(Math.round(amount));
  };

  const formatUsdt = (amount: number) => {
    return amount.toFixed(2);
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing':
        return <TrendingUpIcon className="w-4 h-4 text-green-500" />;
      case 'decreasing':
        return <TrendingDownIcon className="w-4 h-4 text-red-500" />;
      default:
        return <MinusIcon className="w-4 h-4 text-gray-500" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <RefreshCwIcon className="w-8 h-8 animate-spin mx-auto mb-2 text-muted-foreground" />
          <p className="text-muted-foreground">로딩중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">암호화폐 대시보드</h1>
          <p className="text-muted-foreground">입출금 통계 및 지갑 모니터링</p>
        </div>
        <div className="flex gap-2">
          <Select value={periodDays} onValueChange={setPeriodDays}>
            <SelectTrigger className="w-[130px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">7일</SelectItem>
              <SelectItem value="30">30일</SelectItem>
              <SelectItem value="90">90일</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={fetchData}>
            <RefreshCwIcon className="w-4 h-4 mr-2" />
            새로고침
          </Button>
        </div>
      </div>

      {/* Wallet Alert Banner */}
      {alertStatus && (alertStatus.is_critical_balance || alertStatus.is_low_balance) && (
        <Card className={alertStatus.is_critical_balance ? 'border-red-500 bg-red-50' : 'border-yellow-500 bg-yellow-50'}>
          <CardContent className="py-4">
            <div className="flex items-center gap-3">
              <AlertTriangleIcon className={alertStatus.is_critical_balance ? 'w-6 h-6 text-red-500' : 'w-6 h-6 text-yellow-500'} />
              <div>
                <p className={`font-medium ${alertStatus.is_critical_balance ? 'text-red-700' : 'text-yellow-700'}`}>
                  {alertStatus.is_critical_balance ? '지갑 잔액 위험' : '지갑 잔액 부족 경고'}
                </p>
                <p className="text-sm text-muted-foreground">
                  {alertStatus.is_critical_balance
                    ? '즉시 지갑 충전이 필요합니다!'
                    : '지갑 잔액이 임계값 이하입니다. 충전을 권장합니다.'}
                </p>
              </div>
              <Button variant="outline" size="sm" className="ml-auto" onClick={handleForceCheck}>
                잔액 체크
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Total Deposits */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">총 입금</CardTitle>
            <DownloadIcon className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summaryStats ? formatUsdt(summaryStats.deposits.total_usdt) : '0'} USDT
            </div>
            <p className="text-xs text-muted-foreground">
              {summaryStats ? formatCurrency(summaryStats.deposits.total_krw) : '0'} KRW ({summaryStats?.deposits.total_count || 0}건)
            </p>
          </CardContent>
        </Card>

        {/* Total Withdrawals */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">총 출금</CardTitle>
            <SendIcon className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summaryStats ? formatUsdt(summaryStats.withdrawals.total_usdt) : '0'} USDT
            </div>
            <p className="text-xs text-muted-foreground">
              {summaryStats ? formatCurrency(summaryStats.withdrawals.total_krw) : '0'} KRW ({summaryStats?.withdrawals.total_count || 0}건)
            </p>
          </CardContent>
        </Card>

        {/* Net Flow */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">순유입</CardTitle>
            <CircleDollarSignIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${(summaryStats?.net_flow_usdt || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {(summaryStats?.net_flow_usdt || 0) >= 0 ? '+' : ''}{summaryStats ? formatUsdt(summaryStats.net_flow_usdt) : '0'} USDT
            </div>
            <p className="text-xs text-muted-foreground">
              {(summaryStats?.net_flow_krw || 0) >= 0 ? '+' : ''}{summaryStats ? formatCurrency(summaryStats.net_flow_krw) : '0'} KRW
            </p>
          </CardContent>
        </Card>

        {/* Wallet Balance */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">지갑 잔액</CardTitle>
            <WalletIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {walletBalance ? formatUsdt(walletBalance.balance_usdt) : '0'} USDT
            </div>
            <p className="text-xs text-muted-foreground">
              가용: {walletBalance ? formatUsdt(walletBalance.available_usdt) : '0'} USDT
              {walletBalance && walletBalance.pending_withdrawals_count > 0 && (
                <span className="text-yellow-600"> (대기: {walletBalance.pending_withdrawals_count}건)</span>
              )}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Today Stats & Trend */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Today Stats */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ActivityIcon className="w-5 h-5" />
              오늘 현황
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">입금</span>
                <span className="font-medium">
                  {summaryStats?.today.deposits_usdt.toFixed(2) || '0'} USDT ({summaryStats?.today.deposits_count || 0}건)
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">출금</span>
                <span className="font-medium">
                  {summaryStats?.today.withdrawals_usdt.toFixed(2) || '0'} USDT ({summaryStats?.today.withdrawals_count || 0}건)
                </span>
              </div>
              <div className="flex justify-between items-center border-t pt-2">
                <span className="text-sm font-medium">순유입</span>
                <span className={`font-bold ${(summaryStats?.today.net_flow_usdt || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {(summaryStats?.today.net_flow_usdt || 0) >= 0 ? '+' : ''}{summaryStats?.today.net_flow_usdt.toFixed(2) || '0'} USDT
                </span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">대기 출금</span>
                <Badge variant="outline">
                  {summaryStats?.pending.withdrawals_count || 0}건
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Trend Analysis */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {trendAnalysis && getTrendIcon(trendAnalysis.overall_trend)}
              트렌드 분석 (7일)
            </CardTitle>
            <CardDescription>이전 7일 대비 변화</CardDescription>
          </CardHeader>
          <CardContent>
            {trendAnalysis && (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">입금 건수</span>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{trendAnalysis.deposits.current_count}건</span>
                    <Badge className={trendAnalysis.deposits.change_percent >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                      {trendAnalysis.deposits.change_percent >= 0 ? '+' : ''}{trendAnalysis.deposits.change_percent.toFixed(1)}%
                    </Badge>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">입금 볼륨</span>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{trendAnalysis.deposits.current_usdt.toFixed(2)} USDT</span>
                    <Badge className={trendAnalysis.deposits.volume_change_percent >= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                      {trendAnalysis.deposits.volume_change_percent >= 0 ? '+' : ''}{trendAnalysis.deposits.volume_change_percent.toFixed(1)}%
                    </Badge>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">출금 건수</span>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{trendAnalysis.withdrawals.current_count}건</span>
                    <Badge className={trendAnalysis.withdrawals.change_percent <= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                      {trendAnalysis.withdrawals.change_percent >= 0 ? '+' : ''}{trendAnalysis.withdrawals.change_percent.toFixed(1)}%
                    </Badge>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">출금 볼륨</span>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{trendAnalysis.withdrawals.current_usdt.toFixed(2)} USDT</span>
                    <Badge className={trendAnalysis.withdrawals.volume_change_percent <= 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                      {trendAnalysis.withdrawals.volume_change_percent >= 0 ? '+' : ''}{trendAnalysis.withdrawals.volume_change_percent.toFixed(1)}%
                    </Badge>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Automation Status & Top Users */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Automation Status */}
        <Card>
          <CardHeader>
            <CardTitle>자동화 상태</CardTitle>
            <CardDescription>출금 자동 처리 시스템</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm">자동화</span>
                <Badge variant={automationStatus?.executor_enabled ? 'default' : 'secondary'}>
                  {automationStatus?.executor_enabled ? '활성화' : '비활성화'}
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">실행기 상태</span>
                <Badge variant={automationStatus?.executor_running ? 'default' : 'outline'}>
                  {automationStatus?.executor_running ? '실행중' : '중지됨'}
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">모니터 상태</span>
                <Badge variant={automationStatus?.monitor_running ? 'default' : 'outline'}>
                  {automationStatus?.monitor_running ? '실행중' : '중지됨'}
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">대기 큐</span>
                <span className="font-medium">{automationStatus?.executor_pending_count || 0}건</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">오늘 자동 완료</span>
                <span className="font-medium">{automationStatus?.monitor_today_completed || 0}건</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">자동 처리 임계값</span>
                <span className="font-medium">{automationStatus?.executor_auto_threshold_usdt || 0} USDT</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Top Users */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UsersIcon className="w-5 h-5" />
              상위 거래자 (볼륨 기준)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topUsers.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>사용자</TableHead>
                    <TableHead className="text-right">거래량</TableHead>
                    <TableHead className="text-right">순유입</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {topUsers.map((user, idx) => (
                    <TableRow key={user.user_id}>
                      <TableCell className="font-mono text-sm">
                        #{idx + 1} {user.user_id.slice(0, 8)}...
                      </TableCell>
                      <TableCell className="text-right">
                        {formatUsdt(user.total_volume_usdt)} USDT
                      </TableCell>
                      <TableCell className={`text-right ${user.net_flow_usdt >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {user.net_flow_usdt >= 0 ? '+' : ''}{formatUsdt(user.net_flow_usdt)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-center text-muted-foreground py-4">데이터 없음</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Daily Stats */}
      <Card>
        <CardHeader>
          <CardTitle>최근 일별 통계</CardTitle>
          <CardDescription>최근 7일간 입출금 현황</CardDescription>
        </CardHeader>
        <CardContent>
          {dailyStats.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>날짜</TableHead>
                  <TableHead className="text-right">입금 (USDT)</TableHead>
                  <TableHead className="text-right">입금 건수</TableHead>
                  <TableHead className="text-right">출금 (USDT)</TableHead>
                  <TableHead className="text-right">출금 건수</TableHead>
                  <TableHead className="text-right">순유입 (USDT)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dailyStats.slice(0, 7).map((stat) => (
                  <TableRow key={stat.date}>
                    <TableCell>{stat.date}</TableCell>
                    <TableCell className="text-right text-green-600">
                      +{formatUsdt(stat.deposits_usdt)}
                    </TableCell>
                    <TableCell className="text-right">{stat.deposits_count}</TableCell>
                    <TableCell className="text-right text-red-600">
                      -{formatUsdt(stat.withdrawals_usdt)}
                    </TableCell>
                    <TableCell className="text-right">{stat.withdrawals_count}</TableCell>
                    <TableCell className={`text-right font-medium ${stat.net_flow_usdt >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {stat.net_flow_usdt >= 0 ? '+' : ''}{formatUsdt(stat.net_flow_usdt)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center text-muted-foreground py-8">데이터 없음</p>
          )}
        </CardContent>
      </Card>

      {/* Quick Links */}
      <div className="grid gap-4 md:grid-cols-3">
        <Link href="/deposits">
          <Card className="hover:bg-muted/50 cursor-pointer transition-colors">
            <CardContent className="py-6 flex items-center gap-4">
              <DownloadIcon className="w-8 h-8 text-green-500" />
              <div>
                <p className="font-medium">입금 관리</p>
                <p className="text-sm text-muted-foreground">입금 내역 및 처리</p>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link href="/withdrawals">
          <Card className="hover:bg-muted/50 cursor-pointer transition-colors">
            <CardContent className="py-6 flex items-center gap-4">
              <SendIcon className="w-8 h-8 text-red-500" />
              <div>
                <p className="font-medium">출금 관리</p>
                <p className="text-sm text-muted-foreground">
                  대기: {summaryStats?.pending.withdrawals_count || 0}건
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Card className="hover:bg-muted/50 cursor-pointer transition-colors" onClick={handleForceCheck}>
          <CardContent className="py-6 flex items-center gap-4">
            <WalletIcon className="w-8 h-8 text-blue-500" />
            <div>
              <p className="font-medium">지갑 잔액 체크</p>
              <p className="text-sm text-muted-foreground">
                {walletBalance ? `${formatUsdt(walletBalance.available_usdt)} USDT 가용` : '조회 필요'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
