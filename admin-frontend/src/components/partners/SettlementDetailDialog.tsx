'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  partnersApi,
  Settlement,
  SettlementStatus,
  CommissionType,
  SettlementPeriod,
} from '@/lib/partners-api';
import { toast } from 'sonner';

interface SettlementDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  settlement: Settlement;
  onSuccess: () => void;
}

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

export function SettlementDetailDialog({
  open,
  onOpenChange,
  settlement,
  onSuccess,
}: SettlementDetailDialogProps) {
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<'approve' | 'reject' | 'pay' | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');

  const handleApprove = async () => {
    setLoading(true);
    try {
      await partnersApi.updateSettlement(settlement.id, {
        status: SettlementStatus.APPROVED,
      });
      toast.success('정산이 승인되었습니다.');
      onSuccess();
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to approve settlement:', error);
      toast.error('정산 승인에 실패했습니다.');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      toast.error('거부 사유를 입력해주세요.');
      return;
    }

    setLoading(true);
    try {
      await partnersApi.updateSettlement(settlement.id, {
        status: SettlementStatus.REJECTED,
        rejectionReason: rejectionReason.trim(),
      });
      toast.success('정산이 거부되었습니다.');
      onSuccess();
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to reject settlement:', error);
      toast.error('정산 거부에 실패했습니다.');
    } finally {
      setLoading(false);
      setAction(null);
      setRejectionReason('');
    }
  };

  const handlePay = async () => {
    setLoading(true);
    try {
      await partnersApi.paySettlement(settlement.id);
      toast.success('정산이 지급되었습니다.');
      onSuccess();
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to pay settlement:', error);
      toast.error('정산 지급에 실패했습니다.');
    } finally {
      setLoading(false);
      setAction(null);
    }
  };

  const canApprove = settlement.status === SettlementStatus.PENDING;
  const canReject = settlement.status === SettlementStatus.PENDING;
  const canPay = settlement.status === SettlementStatus.APPROVED;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>정산 상세</DialogTitle>
          <DialogDescription>
            정산 정보를 확인하고 승인/거부/지급 처리를 할 수 있습니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* 기본 정보 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">파트너</p>
              <p className="font-medium">{settlement.partnerName || '-'}</p>
              <p className="text-xs text-gray-400 font-mono">{settlement.partnerCode || settlement.partnerId}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">상태</p>
              <span className={`inline-block px-2 py-1 rounded text-xs ${settlementStatusLabels[settlement.status].className}`}>
                {settlementStatusLabels[settlement.status].label}
              </span>
            </div>
            <div>
              <p className="text-sm text-gray-500">정산 기간</p>
              <p className="font-medium">
                {new Date(settlement.periodStart).toLocaleDateString('ko-KR')} ~{' '}
                {new Date(settlement.periodEnd).toLocaleDateString('ko-KR')}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500">정산 주기</p>
              <p className="font-medium">{periodTypeLabels[settlement.periodType]}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">수수료 타입</p>
              <p className="font-medium">{commissionTypeLabels[settlement.commissionType]}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">수수료율</p>
              <p className="font-medium">{(settlement.commissionRate * 100).toFixed(1)}%</p>
            </div>
          </div>

          <Separator />

          {/* 금액 정보 */}
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">기준 금액</p>
                <p className="text-xl font-bold">{settlement.baseAmount.toLocaleString()}원</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">수수료</p>
                <p className="text-xl font-bold text-green-600">{settlement.commissionAmount.toLocaleString()}원</p>
              </div>
            </div>
          </div>

          {/* 상세 내역 (유저별) */}
          {settlement.detail && settlement.detail.length > 0 && (
            <>
              <Separator />
              <div>
                <p className="text-sm font-medium mb-2">하위 유저별 내역</p>
                <div className="max-h-48 overflow-y-auto border rounded">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>닉네임</TableHead>
                        <TableHead className="text-right">기준 금액</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {settlement.detail.map((item) => (
                        <TableRow key={item.userId}>
                          <TableCell>{item.nickname}</TableCell>
                          <TableCell className="text-right">{item.amount.toLocaleString()}원</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </>
          )}

          {/* 처리 정보 */}
          {(settlement.approvedAt || settlement.paidAt || settlement.rejectionReason) && (
            <>
              <Separator />
              <div className="space-y-2">
                {settlement.approvedAt && (
                  <p className="text-sm text-gray-500">
                    승인일: {new Date(settlement.approvedAt).toLocaleString('ko-KR')}
                  </p>
                )}
                {settlement.paidAt && (
                  <p className="text-sm text-gray-500">
                    지급일: {new Date(settlement.paidAt).toLocaleString('ko-KR')}
                  </p>
                )}
                {settlement.rejectionReason && (
                  <div>
                    <p className="text-sm text-gray-500">거부 사유:</p>
                    <p className="text-sm text-red-600">{settlement.rejectionReason}</p>
                  </div>
                )}
              </div>
            </>
          )}

          {/* 거부 사유 입력 */}
          {action === 'reject' && (
            <div className="space-y-2">
              <Label htmlFor="rejectionReason">거부 사유 *</Label>
              <Textarea
                id="rejectionReason"
                placeholder="거부 사유를 입력하세요"
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                rows={3}
              />
            </div>
          )}
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          {action === null ? (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                닫기
              </Button>
              {canReject && (
                <Button variant="outline" onClick={() => setAction('reject')}>
                  거부
                </Button>
              )}
              {canApprove && (
                <Button onClick={() => setAction('approve')}>
                  승인
                </Button>
              )}
              {canPay && (
                <Button onClick={() => setAction('pay')} className="bg-green-600 hover:bg-green-700">
                  지급
                </Button>
              )}
            </>
          ) : action === 'approve' ? (
            <>
              <Button variant="outline" onClick={() => setAction(null)} disabled={loading}>
                취소
              </Button>
              <Button onClick={handleApprove} disabled={loading}>
                {loading ? '처리 중...' : '승인 확인'}
              </Button>
            </>
          ) : action === 'reject' ? (
            <>
              <Button variant="outline" onClick={() => setAction(null)} disabled={loading}>
                취소
              </Button>
              <Button variant="destructive" onClick={handleReject} disabled={loading}>
                {loading ? '처리 중...' : '거부 확인'}
              </Button>
            </>
          ) : action === 'pay' ? (
            <>
              <Button variant="outline" onClick={() => setAction(null)} disabled={loading}>
                취소
              </Button>
              <Button onClick={handlePay} disabled={loading} className="bg-green-600 hover:bg-green-700">
                {loading ? '처리 중...' : '지급 확인'}
              </Button>
            </>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
