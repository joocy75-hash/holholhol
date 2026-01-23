'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  partnersApi,
  Partner,
  PaginatedReferrals,
  PaginatedSettlements,
  PartnerStatus,
  CommissionType,
  SettlementStatus,
} from '@/lib/partners-api';
import { toast } from 'sonner';
import { Skeleton } from '@/components/ui/skeleton';
import { UpdatePartnerDialog } from '@/components/partners/UpdatePartnerDialog';

const statusLabels: Record<PartnerStatus, { label: string; className: string }> = {
  [PartnerStatus.ACTIVE]: { label: '활성', className: 'bg-green-100 text-green-700' },
  [PartnerStatus.SUSPENDED]: { label: '정지', className: 'bg-yellow-100 text-yellow-700' },
  [PartnerStatus.TERMINATED]: { label: '해지', className: 'bg-red-100 text-red-700' },
};

const commissionTypeLabels: Record<CommissionType, string> = {
  [CommissionType.RAKEBACK]: '레이크백',
  [CommissionType.REVSHARE]: '레브쉐어',
  [CommissionType.TURNOVER]: '턴오버',
};

const settlementStatusLabels: Record<SettlementStatus, { label: string; className: string }> = {
  [SettlementStatus.PENDING]: { label: '대기', className: 'bg-yellow-100 text-yellow-700' },
  [SettlementStatus.APPROVED]: { label: '승인', className: 'bg-blue-100 text-blue-700' },
  [SettlementStatus.REJECTED]: { label: '거부', className: 'bg-red-100 text-red-700' },
  [SettlementStatus.PAID]: { label: '지급완료', className: 'bg-green-100 text-green-700' },
};

export default function PartnerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const partnerId = params.id as string;

  const [partner, setPartner] = useState<Partner | null>(null);
  const [referrals, setReferrals] = useState<PaginatedReferrals | null>(null);
  const [settlements, setSettlements] = useState<PaginatedSettlements | null>(null);
  const [loading, setLoading] = useState(true);
  const [referralsPage, setReferralsPage] = useState(1);
  const [settlementsPage, setSettlementsPage] = useState(1);

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [regenerateDialogOpen, setRegenerateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchPartner = useCallback(async () => {
    try {
      const data = await partnersApi.getPartner(partnerId);
      setPartner(data);
    } catch (error) {
      console.error('Failed to fetch partner:', error);
      toast.error('파트너 정보를 불러오는데 실패했습니다.');
    }
  }, [partnerId]);

  const fetchReferrals = useCallback(async () => {
    try {
      const data = await partnersApi.getPartnerReferrals(partnerId, referralsPage, 10);
      setReferrals(data);
    } catch (error) {
      console.error('Failed to fetch referrals:', error);
    }
  }, [partnerId, referralsPage]);

  const fetchSettlements = useCallback(async () => {
    try {
      const data = await partnersApi.getPartnerSettlements(partnerId, { page: settlementsPage, pageSize: 10 });
      setSettlements(data);
    } catch (error) {
      console.error('Failed to fetch settlements:', error);
    }
  }, [partnerId, settlementsPage]);

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([fetchPartner(), fetchReferrals(), fetchSettlements()]);
      setLoading(false);
    };
    loadAll();
  }, [fetchPartner, fetchReferrals, fetchSettlements]);

  const handleRegenerateCode = async () => {
    setActionLoading(true);
    try {
      const result = await partnersApi.regenerateCode(partnerId);
      toast.success(`새 코드가 생성되었습니다: ${result.partnerCode}`);
      fetchPartner();
    } catch (error) {
      console.error('Failed to regenerate code:', error);
      toast.error('코드 재생성에 실패했습니다.');
    } finally {
      setActionLoading(false);
      setRegenerateDialogOpen(false);
    }
  };

  const handleDelete = async () => {
    setActionLoading(true);
    try {
      await partnersApi.deletePartner(partnerId);
      toast.success('파트너가 해지되었습니다.');
      router.push('/partners');
    } catch (error) {
      console.error('Failed to delete partner:', error);
      toast.error('파트너 해지에 실패했습니다.');
    } finally {
      setActionLoading(false);
      setDeleteDialogOpen(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!partner) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">파트너를 찾을 수 없습니다.</p>
        <Button className="mt-4" onClick={() => router.push('/partners')}>
          목록으로 돌아가기
        </Button>
      </div>
    );
  }

  const referralsTotalPages = referrals ? Math.ceil(referrals.total / 10) : 0;
  const settlementsTotalPages = settlements ? Math.ceil(settlements.total / 10) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <Button variant="ghost" onClick={() => router.push('/partners')} className="mb-2">
            &larr; 목록으로
          </Button>
          <h1 className="text-2xl font-bold">{partner.name}</h1>
          <p className="text-gray-500 font-mono">{partner.partnerCode}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditModalOpen(true)}>
            수정
          </Button>
          <Button variant="outline" onClick={() => setRegenerateDialogOpen(true)}>
            코드 재생성
          </Button>
          {partner.status !== PartnerStatus.TERMINATED && (
            <Button variant="destructive" onClick={() => setDeleteDialogOpen(true)}>
              해지
            </Button>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>상태</CardDescription>
          </CardHeader>
          <CardContent>
            <span className={`px-3 py-1 rounded text-sm ${statusLabels[partner.status].className}`}>
              {statusLabels[partner.status].label}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>추천 회원</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{partner.totalReferrals.toLocaleString()}명</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>누적 수수료</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{partner.totalCommissionEarned.toLocaleString()}원</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>이번 달 수수료</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{partner.currentMonthCommission.toLocaleString()}원</p>
          </CardContent>
        </Card>
      </div>

      {/* Partner Info */}
      <Card>
        <CardHeader>
          <CardTitle>파트너 정보</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-gray-500">유저 ID</dt>
              <dd className="font-mono text-sm">{partner.userId}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">연락처</dt>
              <dd>{partner.contactInfo || '-'}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">수수료 타입</dt>
              <dd>{commissionTypeLabels[partner.commissionType]}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">수수료율</dt>
              <dd>{(partner.commissionRate * 100).toFixed(1)}%</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">등록일</dt>
              <dd>{new Date(partner.createdAt).toLocaleString('ko-KR')}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">최근 수정일</dt>
              <dd>{new Date(partner.updatedAt).toLocaleString('ko-KR')}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Tabs: Referrals & Settlements */}
      <Tabs defaultValue="referrals">
        <TabsList>
          <TabsTrigger value="referrals">추천 회원 ({referrals?.total || 0})</TabsTrigger>
          <TabsTrigger value="settlements">정산 내역 ({settlements?.total || 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="referrals" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>닉네임</TableHead>
                    <TableHead>이메일</TableHead>
                    <TableHead className="text-right">총 레이크</TableHead>
                    <TableHead className="text-right">총 베팅량</TableHead>
                    <TableHead className="text-right">순손익</TableHead>
                    <TableHead>가입일</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {referrals?.items.map((referral) => (
                    <TableRow key={referral.id}>
                      <TableCell className="font-medium">{referral.nickname}</TableCell>
                      <TableCell>{referral.email}</TableCell>
                      <TableCell className="text-right">{referral.totalRakePaidKrw.toLocaleString()}원</TableCell>
                      <TableCell className="text-right">{referral.totalBetAmountKrw.toLocaleString()}원</TableCell>
                      <TableCell className="text-right">
                        <span className={referral.totalNetProfitKrw >= 0 ? 'text-green-600' : 'text-red-600'}>
                          {referral.totalNetProfitKrw >= 0 ? '+' : ''}{referral.totalNetProfitKrw.toLocaleString()}원
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {new Date(referral.createdAt).toLocaleDateString('ko-KR')}
                      </TableCell>
                    </TableRow>
                  ))}
                  {referrals?.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-gray-500">
                        추천 회원이 없습니다.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {referralsTotalPages > 1 && (
                <div className="flex justify-center gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={referralsPage === 1}
                    onClick={() => setReferralsPage(referralsPage - 1)}
                  >
                    이전
                  </Button>
                  <span className="px-4 py-2 text-sm">
                    {referralsPage} / {referralsTotalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={referralsPage === referralsTotalPages}
                    onClick={() => setReferralsPage(referralsPage + 1)}
                  >
                    다음
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settlements" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>정산 기간</TableHead>
                    <TableHead>수수료 타입</TableHead>
                    <TableHead className="text-right">기준 금액</TableHead>
                    <TableHead className="text-right">수수료</TableHead>
                    <TableHead>상태</TableHead>
                    <TableHead>생성일</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {settlements?.items.map((settlement) => (
                    <TableRow key={settlement.id}>
                      <TableCell>
                        {new Date(settlement.periodStart).toLocaleDateString('ko-KR')} ~{' '}
                        {new Date(settlement.periodEnd).toLocaleDateString('ko-KR')}
                      </TableCell>
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
                      <TableCell colSpan={6} className="text-center py-8 text-gray-500">
                        정산 내역이 없습니다.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {settlementsTotalPages > 1 && (
                <div className="flex justify-center gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={settlementsPage === 1}
                    onClick={() => setSettlementsPage(settlementsPage - 1)}
                  >
                    이전
                  </Button>
                  <span className="px-4 py-2 text-sm">
                    {settlementsPage} / {settlementsTotalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={settlementsPage === settlementsTotalPages}
                    onClick={() => setSettlementsPage(settlementsPage + 1)}
                  >
                    다음
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Partner Dialog */}
      <UpdatePartnerDialog
        open={editModalOpen}
        onOpenChange={setEditModalOpen}
        partner={partner}
        onSuccess={() => {
          fetchPartner();
          toast.success('파트너 정보가 수정되었습니다.');
        }}
      />

      {/* Regenerate Code Dialog */}
      <AlertDialog open={regenerateDialogOpen} onOpenChange={setRegenerateDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>파트너 코드 재생성</AlertDialogTitle>
            <AlertDialogDescription>
              새로운 파트너 코드를 생성하시겠습니까?<br />
              기존 코드({partner.partnerCode})는 더 이상 사용할 수 없게 됩니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction onClick={handleRegenerateCode} disabled={actionLoading}>
              {actionLoading ? '처리 중...' : '재생성'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>파트너 해지</AlertDialogTitle>
            <AlertDialogDescription>
              정말로 이 파트너를 해지하시겠습니까?<br />
              해지된 파트너는 더 이상 추천 활동을 할 수 없습니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={actionLoading}
              className="bg-red-600 hover:bg-red-700"
            >
              {actionLoading ? '처리 중...' : '해지'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
