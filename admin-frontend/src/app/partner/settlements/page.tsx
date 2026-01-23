'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { partnerPortalApi } from '@/lib/partner-portal-api';
import type { PartnerSettlement, PartnerOverviewStats } from '@/types';
import { toast } from 'sonner';

function formatKRW(amount: number): string {
  return new Intl.NumberFormat('ko-KR').format(amount);
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
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

const statusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: '대기', color: 'bg-yellow-500' },
  approved: { label: '승인됨', color: 'bg-blue-500' },
  paid: { label: '지급완료', color: 'bg-green-500' },
  rejected: { label: '거절', color: 'bg-red-500' },
};

export default function PartnerSettlementsPage() {
  const [settlements, setSettlements] = useState<PartnerSettlement[]>([]);
  const [stats, setStats] = useState<PartnerOverviewStats | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;

    setIsLoading(true);
    try {
      const [settlementsRes, statsRes] = await Promise.all([
        partnerPortalApi.getSettlements(token, {
          page,
          pageSize,
          status: statusFilter !== 'all' ? statusFilter : undefined,
        }),
        partnerPortalApi.getStatsOverview(token),
      ]);
      setSettlements(settlementsRes.items);
      setTotal(settlementsRes.total);
      setStats(statsRes);
    } catch (error) {
      console.error('Failed to fetch settlements:', error);
      toast.error('정산 내역을 불러오는데 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, statusFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleStatusFilter = (value: string) => {
    setPage(1);
    setStatusFilter(value);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-800">정산 내역</h1>
        <Badge variant="secondary" className="text-sm">
          총 {total}건
        </Badge>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-amber-50 to-orange-50">
          <CardContent className="p-4">
            <p className="text-sm text-gray-500">누적 수수료</p>
            <p className="text-2xl font-bold text-amber-600">
              {formatKRW(stats?.totalCommission ?? 0)}원
            </p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-green-50 to-emerald-50">
          <CardContent className="p-4">
            <p className="text-sm text-gray-500">지급 완료</p>
            <p className="text-2xl font-bold text-green-600">
              {formatKRW(stats?.paidCommission ?? 0)}원
            </p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-blue-50 to-cyan-50">
          <CardContent className="p-4">
            <p className="text-sm text-gray-500">대기 중</p>
            <p className="text-2xl font-bold text-blue-600">
              {formatKRW(stats?.pendingCommission ?? 0)}원
            </p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-orange-50 to-red-50">
          <CardContent className="p-4">
            <p className="text-sm text-gray-500">이번 달</p>
            <p className="text-2xl font-bold text-orange-600">
              {formatKRW(stats?.thisMonthCommission ?? 0)}원
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filter */}
      <Card>
        <CardContent className="p-4">
          <div className="flex gap-4 items-center">
            <span className="text-sm text-gray-600">상태 필터:</span>
            <Select value={statusFilter} onValueChange={handleStatusFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="전체" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체</SelectItem>
                <SelectItem value="pending">대기</SelectItem>
                <SelectItem value="approved">승인됨</SelectItem>
                <SelectItem value="paid">지급완료</SelectItem>
                <SelectItem value="rejected">거절</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Settlements Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">정산 목록</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : settlements.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>정산 기간</TableHead>
                    <TableHead className="text-right">정산 금액</TableHead>
                    <TableHead className="text-right">레이크 기여</TableHead>
                    <TableHead>생성일</TableHead>
                    <TableHead>지급일</TableHead>
                    <TableHead className="text-center">상태</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {settlements.map((settlement) => {
                    const status = statusLabels[settlement.status] || {
                      label: settlement.status,
                      color: 'bg-gray-500',
                    };
                    return (
                      <TableRow key={settlement.id}>
                        <TableCell>
                          <div className="text-sm">
                            {formatDate(settlement.periodStart)} ~ {formatDate(settlement.periodEnd)}
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-bold text-amber-600">
                          {formatKRW(settlement.amount)}원
                        </TableCell>
                        <TableCell className="text-right text-gray-600">
                          {formatKRW(settlement.rakeContribution)}원
                        </TableCell>
                        <TableCell className="text-gray-500 text-sm">
                          {formatDateTime(settlement.createdAt)}
                        </TableCell>
                        <TableCell className="text-gray-500 text-sm">
                          {settlement.paidAt ? formatDateTime(settlement.paidAt) : '-'}
                        </TableCell>
                        <TableCell className="text-center">
                          <Badge className={status.color}>{status.label}</Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex justify-center gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(page - 1)}
                  >
                    이전
                  </Button>
                  <span className="flex items-center px-3 text-sm text-gray-600">
                    {page} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage(page + 1)}
                  >
                    다음
                  </Button>
                </div>
              )}
            </>
          ) : (
            <div className="py-12 text-center text-gray-500">
              {statusFilter !== 'all' ? '해당 상태의 정산 내역이 없습니다.' : '정산 내역이 없습니다.'}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="p-4">
          <div className="flex gap-3">
            <div className="text-2xl">💡</div>
            <div className="text-sm text-amber-800">
              <p className="font-medium mb-1">정산 안내</p>
              <ul className="list-disc list-inside space-y-1 text-amber-700">
                <li>정산은 매월 1일에 자동으로 생성됩니다.</li>
                <li>승인된 정산은 영업일 기준 3일 내에 지급됩니다.</li>
                <li>최소 정산 금액은 10,000원입니다.</li>
                <li>문의사항은 관리자에게 연락해 주세요.</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
