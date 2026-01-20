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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  withdrawalsApi,
  WithdrawalListItem,
  PaginatedWithdrawals,
  WithdrawalStats,
  WithdrawalDetail,
} from '@/lib/withdrawals-api';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';

type WithdrawalStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'rejected';

const STATUS_LABELS: Record<WithdrawalStatus, string> = {
  pending: '대기중',
  processing: '처리중',
  completed: '완료',
  failed: '실패',
  rejected: '거부',
};

const STATUS_COLORS: Record<WithdrawalStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  processing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  rejected: 'bg-gray-100 text-gray-700',
};

const STATUS_ICONS: Record<WithdrawalStatus, React.ReactNode> = {
  pending: <Clock className="w-4 h-4" />,
  processing: <AlertCircle className="w-4 h-4" />,
  completed: <CheckCircle className="w-4 h-4" />,
  failed: <XCircle className="w-4 h-4" />,
  rejected: <XCircle className="w-4 h-4" />,
};

export default function WithdrawalsPage() {
  const [withdrawals, setWithdrawals] = useState<PaginatedWithdrawals | null>(null);
  const [stats, setStats] = useState<WithdrawalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);

  // Modal states
  const [selectedWithdrawal, setSelectedWithdrawal] = useState<WithdrawalDetail | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [twoFactorCode, setTwoFactorCode] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const fetchWithdrawals = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        status: statusFilter === 'all' ? undefined : statusFilter,
        page,
        pageSize: 20,
      };
      const data = await withdrawalsApi.listWithdrawals(params);
      setWithdrawals(data);
    } catch (error) {
      console.error('Failed to fetch withdrawals:', error);
      toast.error('출금 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  const fetchStats = useCallback(async () => {
    try {
      const data = await withdrawalsApi.getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  }, []);

  useEffect(() => {
    fetchWithdrawals();
    fetchStats();
  }, [fetchWithdrawals, fetchStats]);

  const handleRowClick = async (withdrawal: WithdrawalListItem) => {
    try {
      const detail = await withdrawalsApi.getWithdrawal(withdrawal.id);
      setSelectedWithdrawal(detail);
      setDetailModalOpen(true);
    } catch (err) {
      console.error('Failed to fetch withdrawal detail:', err);
      toast.error('출금 상세 정보를 불러오는데 실패했습니다.');
    }
  };

  const handleApprove = async () => {
    if (!selectedWithdrawal) return;
    if (!twoFactorCode.trim()) {
      toast.error('2FA 코드를 입력해주세요.');
      return;
    }

    setActionLoading(true);
    try {
      await withdrawalsApi.approveWithdrawal(selectedWithdrawal.id, {
        twoFactorCode: twoFactorCode.trim(),
      });
      toast.success('출금이 승인되었습니다.');
      setApproveModalOpen(false);
      setDetailModalOpen(false);
      setTwoFactorCode('');
      fetchWithdrawals();
      fetchStats();
    } catch (err) {
      console.error('Failed to approve withdrawal:', err);
      const errorMessage = err instanceof Error ? err.message : '출금 승인에 실패했습니다.';
      toast.error(errorMessage);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedWithdrawal) return;
    if (!twoFactorCode.trim()) {
      toast.error('2FA 코드를 입력해주세요.');
      return;
    }
    if (!rejectReason.trim()) {
      toast.error('거부 사유를 입력해주세요.');
      return;
    }

    setActionLoading(true);
    try {
      await withdrawalsApi.rejectWithdrawal(selectedWithdrawal.id, {
        twoFactorCode: twoFactorCode.trim(),
        reason: rejectReason.trim(),
      });
      toast.success('출금이 거부되었습니다. 사용자 잔액이 환불됩니다.');
      setRejectModalOpen(false);
      setDetailModalOpen(false);
      setTwoFactorCode('');
      setRejectReason('');
      fetchWithdrawals();
      fetchStats();
    } catch (err) {
      console.error('Failed to reject withdrawal:', err);
      const errorMessage = err instanceof Error ? err.message : '출금 거부에 실패했습니다.';
      toast.error(errorMessage);
    } finally {
      setActionLoading(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ko-KR').format(amount);
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">출금 관리</h1>
          <p className="text-muted-foreground">USDT 출금 요청 승인/거부 관리</p>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">대기중</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.pendingCount}</div>
              <p className="text-xs text-muted-foreground">
                {formatCurrency(stats.pendingAmountKrw)} KRW
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">처리중</CardTitle>
              <AlertCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.processingCount}</div>
              <p className="text-xs text-muted-foreground">블록체인 처리중</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">오늘 완료</CardTitle>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.todayCompletedCount}</div>
              <p className="text-xs text-muted-foreground">
                {formatCurrency(stats.todayCompletedAmountKrw)} KRW
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">전체 완료</CardTitle>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalCompletedCount}</div>
              <p className="text-xs text-muted-foreground">
                {formatCurrency(stats.totalCompletedAmountKrw)} KRW
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>출금 목록</CardTitle>
            <Select value={statusFilter} onValueChange={(value) => { setStatusFilter(value); setPage(1); }}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="상태 필터" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체</SelectItem>
                <SelectItem value="pending">대기중</SelectItem>
                <SelectItem value="processing">처리중</SelectItem>
                <SelectItem value="completed">완료</SelectItem>
                <SelectItem value="rejected">거부</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8">로딩중...</div>
          ) : withdrawals && withdrawals.items.length > 0 ? (
            <div className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>사용자</TableHead>
                    <TableHead>출금 주소</TableHead>
                    <TableHead className="text-right">금액 (USDT)</TableHead>
                    <TableHead className="text-right">금액 (KRW)</TableHead>
                    <TableHead>상태</TableHead>
                    <TableHead>요청 시간</TableHead>
                    <TableHead>승인자</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {withdrawals.items.map((withdrawal) => (
                    <TableRow
                      key={withdrawal.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleRowClick(withdrawal)}
                    >
                      <TableCell className="font-medium">{withdrawal.username}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {withdrawal.toAddress.slice(0, 10)}...{withdrawal.toAddress.slice(-8)}
                      </TableCell>
                      <TableCell className="text-right">
                        {withdrawal.amountUsdt.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(withdrawal.amountKrw)}
                      </TableCell>
                      <TableCell>
                        <Badge className={STATUS_COLORS[withdrawal.status as WithdrawalStatus]}>
                          <span className="flex items-center gap-1">
                            {STATUS_ICONS[withdrawal.status as WithdrawalStatus]}
                            {STATUS_LABELS[withdrawal.status as WithdrawalStatus]}
                          </span>
                        </Badge>
                      </TableCell>
                      <TableCell>{formatDateTime(withdrawal.requestedAt)}</TableCell>
                      <TableCell>{withdrawal.approvedBy || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  전체 {withdrawals.total}건 중 {(page - 1) * 20 + 1} - {Math.min(page * 20, withdrawals.total)}건
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                  >
                    이전
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= withdrawals.totalPages}
                    onClick={() => setPage(page + 1)}
                  >
                    다음
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              출금 내역이 없습니다.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Modal */}
      <Dialog open={detailModalOpen} onOpenChange={setDetailModalOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>출금 상세 정보</DialogTitle>
            <DialogDescription>출금 요청의 상세 정보를 확인하고 승인/거부할 수 있습니다.</DialogDescription>
          </DialogHeader>
          {selectedWithdrawal && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm text-muted-foreground">사용자</Label>
                  <p className="font-medium">{selectedWithdrawal.username}</p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">상태</Label>
                  <Badge className={STATUS_COLORS[selectedWithdrawal.status as WithdrawalStatus]}>
                    {STATUS_LABELS[selectedWithdrawal.status as WithdrawalStatus]}
                  </Badge>
                </div>
                <div className="col-span-2">
                  <Label className="text-sm text-muted-foreground">출금 주소</Label>
                  <p className="font-mono text-sm break-all">{selectedWithdrawal.toAddress}</p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">출금 금액 (USDT)</Label>
                  <p className="font-medium">{selectedWithdrawal.amountUsdt.toFixed(6)} USDT</p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">출금 금액 (KRW)</Label>
                  <p className="font-medium">{formatCurrency(selectedWithdrawal.amountKrw)} KRW</p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">네트워크 수수료</Label>
                  <p className="text-sm">{selectedWithdrawal.networkFeeUsdt.toFixed(6)} USDT ({formatCurrency(selectedWithdrawal.networkFeeKrw)} KRW)</p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">순 출금액</Label>
                  <p className="font-medium text-green-600">
                    {selectedWithdrawal.netAmountUsdt.toFixed(6)} USDT ({formatCurrency(selectedWithdrawal.netAmountKrw)} KRW)
                  </p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">환율</Label>
                  <p className="text-sm">{selectedWithdrawal.exchangeRate.toFixed(2)} KRW/USDT</p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">요청 시간</Label>
                  <p className="text-sm">{formatDateTime(selectedWithdrawal.requestedAt)}</p>
                </div>
                {selectedWithdrawal.txHash && (
                  <div className="col-span-2">
                    <Label className="text-sm text-muted-foreground">트랜잭션 해시</Label>
                    <p className="font-mono text-xs break-all">{selectedWithdrawal.txHash}</p>
                  </div>
                )}
                {selectedWithdrawal.rejectionReason && (
                  <div className="col-span-2">
                    <Label className="text-sm text-muted-foreground">거부 사유</Label>
                    <p className="text-sm">{selectedWithdrawal.rejectionReason}</p>
                  </div>
                )}
              </div>

              {selectedWithdrawal.status === 'pending' && (
                <DialogFooter className="gap-2">
                  <Button variant="outline" onClick={() => setDetailModalOpen(false)}>
                    닫기
                  </Button>
                  <Button variant="destructive" onClick={() => { setDetailModalOpen(false); setRejectModalOpen(true); }}>
                    거부
                  </Button>
                  <Button onClick={() => { setDetailModalOpen(false); setApproveModalOpen(true); }}>
                    승인
                  </Button>
                </DialogFooter>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Approve Modal */}
      <Dialog open={approveModalOpen} onOpenChange={setApproveModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>출금 승인</DialogTitle>
            <DialogDescription>
              출금을 승인하시겠습니까? 블록체인 트랜잭션이 자동으로 실행됩니다.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="2fa-approve">2FA 코드</Label>
              <Input
                id="2fa-approve"
                placeholder="6자리 코드"
                maxLength={6}
                value={twoFactorCode}
                onChange={(e) => setTwoFactorCode(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApproveModalOpen(false)} disabled={actionLoading}>
              취소
            </Button>
            <Button onClick={handleApprove} disabled={actionLoading}>
              {actionLoading ? '처리중...' : '승인'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Modal */}
      <Dialog open={rejectModalOpen} onOpenChange={setRejectModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>출금 거부</DialogTitle>
            <DialogDescription>
              출금을 거부하시겠습니까? 사용자 잔액이 자동으로 환불됩니다.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="2fa-reject">2FA 코드</Label>
              <Input
                id="2fa-reject"
                placeholder="6자리 코드"
                maxLength={6}
                value={twoFactorCode}
                onChange={(e) => setTwoFactorCode(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="reject-reason">거부 사유 *</Label>
              <Textarea
                id="reject-reason"
                placeholder="거부 사유를 입력하세요"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRejectModalOpen(false)} disabled={actionLoading}>
              취소
            </Button>
            <Button variant="destructive" onClick={handleReject} disabled={actionLoading}>
              {actionLoading ? '처리중...' : '거부'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
