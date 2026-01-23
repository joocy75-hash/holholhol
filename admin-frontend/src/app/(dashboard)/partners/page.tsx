'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
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
  PaginatedPartners,
  PartnerStatus,
  CommissionType,
} from '@/lib/partners-api';
import { toast } from 'sonner';
import { TableSkeleton } from '@/components/ui/table-skeleton';
import { CreatePartnerDialog } from '@/components/partners/CreatePartnerDialog';

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

export default function PartnersPage() {
  const router = useRouter();
  const [partners, setPartners] = useState<PaginatedPartners | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const fetchPartners = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        search: search || undefined,
        status: statusFilter === 'all' ? undefined : (statusFilter as PartnerStatus),
        page,
        pageSize: 20,
      };
      const data = await partnersApi.listPartners(params);
      setPartners(data);
    } catch (error) {
      console.error('Failed to fetch partners:', error);
      toast.error('파트너 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, page]);

  useEffect(() => {
    fetchPartners();
  }, [fetchPartners]);

  const handleSearch = () => {
    setPage(1);
    fetchPartners();
  };

  const totalPages = partners ? Math.ceil(partners.total / 20) : 0;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">파트너 관리</h1>
        <Button onClick={() => setCreateModalOpen(true)}>
          + 파트너 등록
        </Button>
      </div>

      {/* Search & Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <Input
              placeholder="파트너명, 코드, 이름 검색..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="max-w-sm"
            />
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="상태" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체</SelectItem>
                <SelectItem value={PartnerStatus.ACTIVE}>활성</SelectItem>
                <SelectItem value={PartnerStatus.SUSPENDED}>정지</SelectItem>
                <SelectItem value={PartnerStatus.TERMINATED}>해지</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleSearch}>검색</Button>
          </div>
        </CardContent>
      </Card>

      {/* Partners Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            파트너 목록 {partners && `(${partners.total}명)`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton
              columns={8}
              rows={10}
              headers={['코드', '파트너명', '수수료 타입', '수수료율', '추천 회원', '누적 수수료', '상태', '등록일']}
            />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>코드</TableHead>
                    <TableHead>파트너명</TableHead>
                    <TableHead>수수료 타입</TableHead>
                    <TableHead className="text-right">수수료율</TableHead>
                    <TableHead className="text-right">추천 회원</TableHead>
                    <TableHead className="text-right">누적 수수료</TableHead>
                    <TableHead>상태</TableHead>
                    <TableHead>등록일</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {partners?.items.map((partner) => (
                    <TableRow
                      key={partner.id}
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() => router.push(`/partners/${partner.id}`)}
                    >
                      <TableCell className="font-mono font-medium">
                        {partner.partnerCode}
                      </TableCell>
                      <TableCell className="font-medium">{partner.name}</TableCell>
                      <TableCell>
                        {commissionTypeLabels[partner.commissionType]}
                      </TableCell>
                      <TableCell className="text-right">
                        {(partner.commissionRate * 100).toFixed(1)}%
                      </TableCell>
                      <TableCell className="text-right">
                        {partner.totalReferrals.toLocaleString()}명
                      </TableCell>
                      <TableCell className="text-right">
                        {partner.totalCommissionEarned.toLocaleString()}원
                      </TableCell>
                      <TableCell>
                        <span className={`px-2 py-1 rounded text-xs ${statusLabels[partner.status].className}`}>
                          {statusLabels[partner.status].label}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {new Date(partner.createdAt).toLocaleDateString('ko-KR')}
                      </TableCell>
                    </TableRow>
                  ))}
                  {partners?.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8 text-gray-500">
                        {search ? '검색 결과가 없습니다.' : '등록된 파트너가 없습니다.'}
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

      {/* Create Partner Modal */}
      <CreatePartnerDialog
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
        onSuccess={() => {
          fetchPartners();
          toast.success('파트너가 등록되었습니다.');
        }}
      />
    </div>
  );
}
