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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  partnersApi,
  PaginatedSettlements,
  Settlement,
  SettlementStatus,
  SettlementPeriod,
  CommissionType,
} from '@/lib/partners-api';
import { toast } from 'sonner';
import { TableSkeleton } from '@/components/ui/table-skeleton';
import { GenerateSettlementDialog } from '@/components/partners/GenerateSettlementDialog';
import { SettlementDetailDialog } from '@/components/partners/SettlementDetailDialog';

const settlementStatusLabels: Record<SettlementStatus, { label: string; className: string }> = {
  [SettlementStatus.PENDING]: { label: '대기', className: 'bg-yellow-100 text-yellow-700' },
  [SettlementStatus.APPROVED]: { label: '승인', className: 'bg-blue-100 text-blue-700' },
  [SettlementStatus.REJECTED]: { label: '거부', className: 'bg-red-100 text-red-700' },
  [SettlementStatus.PAID]: { label: '지급완료', className: 'bg-green-100 text-green-700' },
};

const periodTypeLabels: Record<SettlementPeriod, string> = {
  [SettlementPeriod.DAILY]: '일간',
  [SettlementPeriod.WEEKLY]: '주간',
  [SettlementPeriod.MONTHLY]: '월간',
};

const commissionTypeLabels: Record<CommissionType, string> = {
  [CommissionType.RAKEBACK]: '레이크백',
  [CommissionType.REVSHARE]: '레브쉐어',
  [CommissionType.TURNOVER]: '턴오버',
};

export default function SettlementsPage() {
  const [settlements, setSettlements] = useState<PaginatedSettlements | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [periodFilter, setPeriodFilter] = useState<string>('all');
  const [page, setPage] = useState(1);

  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [selectedSettlement, setSelectedSettlement] = useState<Settlement | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);

  const fetchSettlements = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        status: statusFilter === 'all' ? undefined : (statusFilter as SettlementStatus),
        periodType: periodFilter === 'all' ? undefined : (periodFilter as SettlementPeriod),
        page,
        pageSize: 20,
      };
      const data = await partnersApi.listSettlements(params);
      setSettlements(data);
    } catch (error) {
      console.error('Failed to fetch settlements:', error);
      toast.error('정산 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, periodFilter, page]);

  useEffect(() => {
    fetchSettlements();
  }, [fetchSettlements]);

  const handleRowClick = (settlement: Settlement) => {
    setSelectedSettlement(settlement);
    setDetailDialogOpen(true);
  };

  const totalPages = settlements ? Math.ceil(settlements.total / 20) : 0;

  // 요약 통계 계산
  const stats = {
    pending: settlements?.items.filter(s => s.status === SettlementStatus.PENDING).length || 0,
    pendingAmount: settlements?.items
      .filter(s => s.status === SettlementStatus.PENDING)
      .reduce((sum, s) => sum + s.commissionAmount, 0) || 0,
    approved: settlements?.items.filter(s => s.status === SettlementStatus.APPROVED).length || 0,
    approvedAmount: settlements?.items
      .filter(s => s.status === SettlementStatus.APPROVED)
      .reduce((sum, s) => sum + s.commissionAmount, 0) || 0,
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">정산 관리</h1>
        <Button onClick={() => setGenerateDialogOpen(true)}>
          + 정산 생성
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">전체 정산</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{settlements?.total || 0}건</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">대기 중</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-yellow-600">{stats.pending}건</p>
            <p className="text-sm text-gray-500">{stats.pendingAmount.toLocaleString()}원</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">승인됨 (지급 대기)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-blue-600">{stats.approved}건</p>
            <p className="text-sm text-gray-500">{stats.approvedAmount.toLocaleString()}원</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">조치 필요</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-orange-600">{stats.pending + stats.approved}건</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="상태" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체 상태</SelectItem>
                <SelectItem value={SettlementStatus.PENDING}>대기</SelectItem>
                <SelectItem value={SettlementStatus.APPROVED}>승인</SelectItem>
                <SelectItem value={SettlementStatus.REJECTED}>거부</SelectItem>
                <SelectItem value={SettlementStatus.PAID}>지급완료</SelectItem>
              </SelectContent>
            </Select>
            <Select value={periodFilter} onValueChange={(v) => { setPeriodFilter(v); setPage(1); }}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="정산 주기" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체 주기</SelectItem>
                <SelectItem value={SettlementPeriod.DAILY}>일간</SelectItem>
                <SelectItem value={SettlementPeriod.WEEKLY}>주간</SelectItem>
                <SelectItem value={SettlementPeriod.MONTHLY}>월간</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={fetchSettlements}>
              새로고침
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Settlements Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            정산 목록 {settlements && `(${settlements.total}건)`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton
              columns={8}
              rows={10}
              headers={['파트너', '정산 기간', '주기', '수수료 타입', '기준 금액', '수수료', '상태', '생성일']}
            />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>파트너</TableHead>
                    <TableHead>정산 기간</TableHead>
                    <TableHead>주기</TableHead>
                    <TableHead>수수료 타입</TableHead>
                    <TableHead className="text-right">기준 금액</TableHead>
                    <TableHead className="text-right">수수료</TableHead>
                    <TableHead>상태</TableHead>
                    <TableHead>생성일</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {settlements?.items.map((settlement) => (
                    <TableRow
                      key={settlement.id}
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() => handleRowClick(settlement)}
                    >
                      <TableCell>
                        <div>
                          <p className="font-medium">{settlement.partnerName || '-'}</p>
                          <p className="text-xs text-gray-500 font-mono">{settlement.partnerCode || settlement.partnerId.slice(0, 8)}</p>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">
                        {new Date(settlement.periodStart).toLocaleDateString('ko-KR')} ~<br />
                        {new Date(settlement.periodEnd).toLocaleDateString('ko-KR')}
                      </TableCell>
                      <TableCell>{periodTypeLabels[settlement.periodType]}</TableCell>
                      <TableCell>{commissionTypeLabels[settlement.commissionType]}</TableCell>
                      <TableCell className="text-right">{settlement.baseAmount.toLocaleString()}원</TableCell>
                      <TableCell className="text-right font-medium">{settlement.commissionAmount.toLocaleString()}원</TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded text-xs ${settlementStatusLabels[settlement.status].className}`}>
                          {settlementStatusLabels[settlement.status].label}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {new Date(settlement.createdAt).toLocaleDateString('ko-KR')}
                      </TableCell>
                    </TableRow>
                  ))}
                  {settlements?.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8 text-gray-500">
                        정산 내역이 없습니다.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex justify-center gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                  >
                    이전
                  </Button>
                  <span className="px-4 py-2 text-sm">
                    {page} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === totalPages}
                    onClick={() => setPage(page + 1)}
                  >
                    다음
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Generate Settlement Dialog */}
      <GenerateSettlementDialog
        open={generateDialogOpen}
        onOpenChange={setGenerateDialogOpen}
        onSuccess={() => {
          fetchSettlements();
          toast.success('정산이 생성되었습니다.');
        }}
      />

      {/* Settlement Detail Dialog */}
      {selectedSettlement && (
        <SettlementDetailDialog
          open={detailDialogOpen}
          onOpenChange={setDetailDialogOpen}
          settlement={selectedSettlement}
          onSuccess={() => {
            fetchSettlements();
          }}
        />
      )}
    </div>
  );
}
