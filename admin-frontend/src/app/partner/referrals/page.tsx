'use client';

import { useEffect, useState, useCallback } from 'react';
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
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { partnerPortalApi } from '@/lib/partner-portal-api';
import type { PartnerReferral } from '@/types';
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

export default function PartnerReferralsPage() {
  const [referrals, setReferrals] = useState<PartnerReferral[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const fetchReferrals = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;

    setIsLoading(true);
    try {
      const response = await partnerPortalApi.getReferrals(token, {
        page,
        pageSize,
        search: search || undefined,
      });
      setReferrals(response.items);
      setTotal(response.total);
    } catch (error) {
      console.error('Failed to fetch referrals:', error);
      toast.error('추천 회원 목록을 불러오는데 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, search]);

  useEffect(() => {
    fetchReferrals();
  }, [fetchReferrals]);

  const handleSearch = () => {
    setPage(1);
    setSearch(searchInput);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-gray-800">추천 회원</h1>
        <Badge variant="secondary" className="text-sm">
          총 {total}명
        </Badge>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="p-4">
          <div className="flex gap-2">
            <Input
              placeholder="닉네임 또는 이메일로 검색..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="max-w-sm"
            />
            <Button onClick={handleSearch} variant="secondary">
              검색
            </Button>
            {search && (
              <Button
                onClick={() => {
                  setSearchInput('');
                  setSearch('');
                  setPage(1);
                }}
                variant="ghost"
              >
                초기화
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Referrals Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">회원 목록</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : referrals.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>닉네임</TableHead>
                    <TableHead>가입일</TableHead>
                    <TableHead>마지막 접속</TableHead>
                    <TableHead className="text-right">총 레이크</TableHead>
                    <TableHead className="text-right">총 베팅액</TableHead>
                    <TableHead className="text-right">순손실</TableHead>
                    <TableHead className="text-center">상태</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {referrals.map((referral) => (
                    <TableRow key={referral.userId}>
                      <TableCell className="font-medium">
                        {referral.nickname}
                      </TableCell>
                      <TableCell className="text-gray-500">
                        {formatDate(referral.joinedAt)}
                      </TableCell>
                      <TableCell className="text-gray-500">
                        {referral.lastActiveAt
                          ? formatDate(referral.lastActiveAt)
                          : '-'}
                      </TableCell>
                      <TableCell className="text-right text-amber-600 font-medium">
                        {formatKRW(referral.totalRake)}원
                      </TableCell>
                      <TableCell className="text-right">
                        {formatKRW(referral.totalBetAmount)}원
                      </TableCell>
                      <TableCell className={`text-right font-medium ${
                        referral.netLoss > 0 ? 'text-red-600' : 'text-green-600'
                      }`}>
                        {referral.netLoss > 0 ? '-' : '+'}{formatKRW(Math.abs(referral.netLoss))}원
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge
                          variant={referral.isActive ? 'default' : 'secondary'}
                          className={referral.isActive ? 'bg-green-500' : ''}
                        >
                          {referral.isActive ? '활성' : '비활성'}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
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
              {search ? '검색 결과가 없습니다.' : '추천 회원이 없습니다.'}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary Stats */}
      {referrals.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-gray-500">활성 회원</p>
              <p className="text-xl font-bold text-green-600">
                {referrals.filter(r => r.isActive).length}명
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-gray-500">페이지 내 총 레이크</p>
              <p className="text-xl font-bold text-amber-600">
                {formatKRW(referrals.reduce((sum, r) => sum + r.totalRake, 0))}원
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-sm text-gray-500">페이지 내 총 베팅</p>
              <p className="text-xl font-bold text-gray-800">
                {formatKRW(referrals.reduce((sum, r) => sum + r.totalBetAmount, 0))}원
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
