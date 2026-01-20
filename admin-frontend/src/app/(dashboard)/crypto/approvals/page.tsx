'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  multiApprovalApi,
  ApprovalRequest,
  ApprovalStats,
  ApprovalPolicy,
} from '@/lib/multi-approval-api';
import { toast } from 'sonner';
import {
  RefreshCwIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ShieldCheckIcon,
  UsersIcon,
} from 'lucide-react';
import Link from 'next/link';

export default function MultiApprovalPage() {
  const [pendingRequests, setPendingRequests] = useState<ApprovalRequest[]>([]);
  const [stats, setStats] = useState<ApprovalStats | null>(null);
  const [policies, setPolicies] = useState<ApprovalPolicy[]>([]);
  const [loading, setLoading] = useState(true);

  // Dialog states
  const [selectedRequest, setSelectedRequest] = useState<ApprovalRequest | null>(null);
  const [actionType, setActionType] = useState<'approve' | 'reject' | null>(null);
  const [actionNote, setActionNote] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [pendingRes, statsRes, policiesRes] = await Promise.all([
        multiApprovalApi.listPendingRequests(50),
        multiApprovalApi.getStats(),
        multiApprovalApi.listPolicies(),
      ]);

      setPendingRequests(pendingRes.items);
      setStats(statsRes);
      setPolicies(policiesRes.items);
    } catch (error) {
      console.error('Failed to fetch approval data:', error);
      toast.error('데이터를 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleApprove = async () => {
    if (!selectedRequest) return;

    setActionLoading(true);
    try {
      const result = await multiApprovalApi.approve(selectedRequest.id, actionNote || undefined);
      toast.success(result.message);

      if (result.is_fully_approved) {
        toast.success('모든 승인이 완료되었습니다. 출금이 자동 실행됩니다.');
      }

      setSelectedRequest(null);
      setActionType(null);
      setActionNote('');
      fetchData();
    } catch (error: any) {
      toast.error(error.message || '승인 처리에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedRequest || !actionNote) {
      toast.error('거부 사유를 입력해주세요.');
      return;
    }

    setActionLoading(true);
    try {
      const result = await multiApprovalApi.reject(selectedRequest.id, actionNote);
      toast.success(result.message);

      setSelectedRequest(null);
      setActionType(null);
      setActionNote('');
      fetchData();
    } catch (error: any) {
      toast.error(error.message || '거부 처리에 실패했습니다.');
    } finally {
      setActionLoading(false);
    }
  };

  const openActionDialog = (request: ApprovalRequest, type: 'approve' | 'reject') => {
    setSelectedRequest(request);
    setActionType(type);
    setActionNote('');
  };

  const closeDialog = () => {
    setSelectedRequest(null);
    setActionType(null);
    setActionNote('');
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ko-KR').format(Math.round(amount));
  };

  const formatUsdt = (amount: number) => {
    return amount.toFixed(2);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return <Badge variant="outline">대기</Badge>;
      case 'partially_approved':
        return <Badge className="bg-yellow-100 text-yellow-700">부분 승인</Badge>;
      case 'approved':
        return <Badge className="bg-green-100 text-green-700">승인 완료</Badge>;
      case 'rejected':
        return <Badge variant="destructive">거부</Badge>;
      case 'expired':
        return <Badge variant="secondary">만료</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const getRemainingTime = (expiresAt: string) => {
    const now = new Date();
    const expires = new Date(expiresAt);
    const diffMs = expires.getTime() - now.getTime();

    if (diffMs <= 0) return '만료됨';

    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 60) return `${diffMins}분`;

    const diffHours = Math.floor(diffMins / 60);
    return `${diffHours}시간 ${diffMins % 60}분`;
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
          <h1 className="text-3xl font-bold tracking-tight">다중 승인 관리</h1>
          <p className="text-muted-foreground">고액 출금에 대한 다중 관리자 승인</p>
        </div>
        <div className="flex gap-2">
          <Link href="/crypto">
            <Button variant="outline">대시보드</Button>
          </Link>
          <Button variant="outline" onClick={fetchData}>
            <RefreshCwIcon className="w-4 h-4 mr-2" />
            새로고침
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">대기 중</CardTitle>
            <ClockIcon className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.pending_count || 0}건</div>
            <p className="text-xs text-muted-foreground">승인 대기 중인 요청</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">오늘 승인</CardTitle>
            <CheckCircleIcon className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.today_approved || 0}건</div>
            <p className="text-xs text-muted-foreground">오늘 승인 완료</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">오늘 거부</CardTitle>
            <XCircleIcon className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.today_rejected || 0}건</div>
            <p className="text-xs text-muted-foreground">오늘 거부됨</p>
          </CardContent>
        </Card>
      </div>

      {/* Pending Requests */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheckIcon className="w-5 h-5" />
            승인 대기 요청
          </CardTitle>
          <CardDescription>다중 승인이 필요한 고액 출금 요청</CardDescription>
        </CardHeader>
        <CardContent>
          {pendingRequests.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>사용자</TableHead>
                  <TableHead className="text-right">금액</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>승인 현황</TableHead>
                  <TableHead>남은 시간</TableHead>
                  <TableHead>주소</TableHead>
                  <TableHead className="text-center">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingRequests.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-mono text-sm">
                      {request.user_id.slice(0, 8)}...
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="font-bold">{formatUsdt(request.amount_usdt)} USDT</div>
                      <div className="text-xs text-muted-foreground">
                        {formatCurrency(request.amount_krw)} KRW
                      </div>
                    </TableCell>
                    <TableCell>{getStatusBadge(request.status)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <UsersIcon className="w-4 h-4 text-muted-foreground" />
                        <span className="font-medium">
                          {request.current_approvals}/{request.required_approvals}
                        </span>
                      </div>
                      {request.approval_records.length > 0 && (
                        <div className="text-xs text-muted-foreground mt-1">
                          {request.approval_records.map((r, i) => (
                            <span key={i}>
                              {r.admin_name}
                              {i < request.approval_records.length - 1 && ', '}
                            </span>
                          ))}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">{getRemainingTime(request.expires_at)}</span>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {request.to_address.slice(0, 15)}...
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-center gap-2">
                        <Button
                          size="sm"
                          onClick={() => openActionDialog(request, 'approve')}
                        >
                          승인
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => openActionDialog(request, 'reject')}
                        >
                          거부
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <ShieldCheckIcon className="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p>대기 중인 승인 요청이 없습니다</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Active Policies */}
      <Card>
        <CardHeader>
          <CardTitle>활성 승인 정책</CardTitle>
          <CardDescription>금액 범위에 따른 필요 승인 수</CardDescription>
        </CardHeader>
        <CardContent>
          {policies.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>정책명</TableHead>
                  <TableHead className="text-right">최소 금액</TableHead>
                  <TableHead className="text-right">최대 금액</TableHead>
                  <TableHead className="text-center">필요 승인</TableHead>
                  <TableHead className="text-center">만료 시간</TableHead>
                  <TableHead className="text-center">우선순위</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {policies.map((policy) => (
                  <TableRow key={policy.id}>
                    <TableCell className="font-medium">{policy.name}</TableCell>
                    <TableCell className="text-right">
                      {formatUsdt(policy.min_amount_usdt)} USDT
                    </TableCell>
                    <TableCell className="text-right">
                      {policy.max_amount_usdt
                        ? `${formatUsdt(policy.max_amount_usdt)} USDT`
                        : '무제한'}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline">{policy.required_approvals}명</Badge>
                    </TableCell>
                    <TableCell className="text-center">{policy.expiry_minutes}분</TableCell>
                    <TableCell className="text-center">{policy.priority}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-center py-4 text-muted-foreground">
              설정된 승인 정책이 없습니다
            </p>
          )}
        </CardContent>
      </Card>

      {/* Action Dialog */}
      <Dialog open={!!selectedRequest && !!actionType} onOpenChange={closeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {actionType === 'approve' ? '출금 승인' : '출금 거부'}
            </DialogTitle>
            <DialogDescription>
              {selectedRequest && (
                <>
                  <span className="font-bold">{formatUsdt(selectedRequest.amount_usdt)} USDT</span>
                  {' '}({formatCurrency(selectedRequest.amount_krw)} KRW) 출금 요청
                  {actionType === 'approve'
                    ? `을 승인합니다. (${selectedRequest.current_approvals + 1}/${selectedRequest.required_approvals})`
                    : '을 거부합니다.'}
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {selectedRequest && (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">사용자:</span>
                  <span className="font-mono">{selectedRequest.user_id.slice(0, 12)}...</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">주소:</span>
                  <span className="font-mono">{selectedRequest.to_address.slice(0, 20)}...</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">현재 승인:</span>
                  <span>
                    {selectedRequest.current_approvals}/{selectedRequest.required_approvals}명
                  </span>
                </div>
              </div>
            )}

            <div>
              <label className="text-sm font-medium">
                {actionType === 'approve' ? '메모 (선택)' : '거부 사유 (필수)'}
              </label>
              <Input
                placeholder={actionType === 'approve' ? '승인 메모 입력...' : '거부 사유 입력...'}
                value={actionNote}
                onChange={(e) => setActionNote(e.target.value)}
                className="mt-2"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              취소
            </Button>
            <Button
              onClick={actionType === 'approve' ? handleApprove : handleReject}
              disabled={actionLoading || (actionType === 'reject' && !actionNote)}
              variant={actionType === 'approve' ? 'default' : 'destructive'}
            >
              {actionLoading ? '처리 중...' : actionType === 'approve' ? '승인' : '거부'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
