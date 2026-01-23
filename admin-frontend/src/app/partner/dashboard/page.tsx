'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { partnerPortalApi } from '@/lib/partner-portal-api';
import type { PartnerInfo, PartnerOverviewStats, PartnerDailyStat } from '@/types';
import { toast } from 'sonner';

function formatKRW(amount: number): string {
  return new Intl.NumberFormat('ko-KR').format(amount);
}

function getAccessToken(): string | null {
  try {
    const stored = localStorage.getItem('admin-auth');
    if (stored) {
      const parsed = JSON.parse(stored);
      return parsed.state?.accessToken || null;
    }
  } catch {
    // ignore
  }
  return null;
}

export default function PartnerDashboardPage() {
  const [partnerInfo, setPartnerInfo] = useState<PartnerInfo | null>(null);
  const [stats, setStats] = useState<PartnerOverviewStats | null>(null);
  const [dailyStats, setDailyStats] = useState<PartnerDailyStat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      const token = getAccessToken();
      if (!token) return;

      try {
        const [info, overview, daily] = await Promise.all([
          partnerPortalApi.getMyInfo(token),
          partnerPortalApi.getStatsOverview(token),
          partnerPortalApi.getDailyStats(token, 14),
        ]);

        setPartnerInfo(info);
        setStats(overview);
        setDailyStats(daily);
      } catch (error) {
        console.error('Failed to fetch partner data:', error);
        toast.error('데이터를 불러오는데 실패했습니다.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleCopyCode = () => {
    if (partnerInfo?.partnerCode) {
      navigator.clipboard.writeText(partnerInfo.partnerCode);
      setIsCopied(true);
      toast.success('파트너 코드가 복사되었습니다.');
      setTimeout(() => setIsCopied(false), 2000);
    }
  };

  const getCommissionModelLabel = (model: string) => {
    switch (model) {
      case 'RAKEBACK':
        return '레이크백';
      case 'REVSHARE':
        return '수익 분배';
      case 'TURNOVER':
        return '턴오버';
      default:
        return model;
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">대시보드</h1>

      {/* Partner Code Card */}
      <Card className="bg-gradient-to-r from-amber-500 to-orange-500 text-white">
        <CardContent className="p-6">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm opacity-90">내 파트너 코드</p>
              <p className="text-3xl font-bold tracking-wider mt-1">
                {partnerInfo?.partnerCode || '---'}
              </p>
              <p className="text-sm mt-2 opacity-90">
                수수료 모델: {getCommissionModelLabel(partnerInfo?.commissionType || '')} ({partnerInfo?.commissionRate || 0}%)
              </p>
            </div>
            <Button
              onClick={handleCopyCode}
              variant="secondary"
              className="bg-white/20 hover:bg-white/30 text-white border-0"
            >
              {isCopied ? '복사됨!' : '코드 복사'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              총 추천 회원
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-800">
              {stats?.totalReferrals ?? 0}명
            </div>
            <p className="text-xs text-gray-500 mt-1">
              활성: {stats?.activeReferrals ?? 0}명
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              누적 수수료
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {formatKRW(stats?.totalCommission ?? 0)}원
            </div>
            <p className="text-xs text-gray-500 mt-1">
              지급 완료: {formatKRW(stats?.paidCommission ?? 0)}원
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              이번 달 수수료
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatKRW(stats?.thisMonthCommission ?? 0)}원
            </div>
            <p className="text-xs text-gray-500 mt-1">
              대기 중: {formatKRW(stats?.pendingCommission ?? 0)}원
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              총 레이크 기여
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-800">
              {formatKRW(stats?.totalRakeContribution ?? 0)}원
            </div>
            <p className="text-xs text-gray-500 mt-1">
              추천 회원들의 총 레이크
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Daily Stats Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">최근 14일 수수료 현황</CardTitle>
        </CardHeader>
        <CardContent>
          {dailyStats.length > 0 ? (
            <div className="space-y-4">
              {/* Simple bar chart */}
              <div className="flex items-end gap-1 h-40">
                {dailyStats.map((stat, index) => {
                  const maxCommission = Math.max(...dailyStats.map(s => s.commission), 1);
                  const height = (stat.commission / maxCommission) * 100;
                  return (
                    <div
                      key={index}
                      className="flex-1 flex flex-col items-center gap-1"
                    >
                      <div
                        className="w-full bg-gradient-to-t from-amber-500 to-orange-400 rounded-t transition-all hover:from-amber-600 hover:to-orange-500"
                        style={{ height: `${Math.max(height, 2)}%` }}
                        title={`${stat.date}: ${formatKRW(stat.commission)}원`}
                      />
                      <span className="text-[10px] text-gray-400 -rotate-45 origin-left whitespace-nowrap">
                        {stat.date.slice(5)}
                      </span>
                    </div>
                  );
                })}
              </div>
              {/* Legend */}
              <div className="flex justify-between text-sm text-gray-500 pt-4 border-t">
                <span>총 수수료: {formatKRW(dailyStats.reduce((sum, s) => sum + s.commission, 0))}원</span>
                <span>신규 회원: {dailyStats.reduce((sum, s) => sum + s.newReferrals, 0)}명</span>
              </div>
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-gray-400">
              데이터가 없습니다
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => window.location.href = '/partner/referrals'}>
          <CardContent className="p-6 flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center">
              <span className="text-2xl">👥</span>
            </div>
            <div>
              <h3 className="font-medium text-gray-800">추천 회원 관리</h3>
              <p className="text-sm text-gray-500">회원 목록 및 활동 현황 보기</p>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => window.location.href = '/partner/settlements'}>
          <CardContent className="p-6 flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
              <span className="text-2xl">💰</span>
            </div>
            <div>
              <h3 className="font-medium text-gray-800">정산 내역</h3>
              <p className="text-sm text-gray-500">정산 현황 및 지급 내역 확인</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
