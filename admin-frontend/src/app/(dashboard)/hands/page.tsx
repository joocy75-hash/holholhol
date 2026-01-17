'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { handsApi, PaginatedHands } from '@/lib/hands-api';

export default function HandsPage() {
  const router = useRouter();
  const [hands, setHands] = useState<PaginatedHands | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  // Search filters
  const [handIdFilter, setHandIdFilter] = useState('');
  const [userIdFilter, setUserIdFilter] = useState('');
  const [tableIdFilter, setTableIdFilter] = useState('');

  const fetchHands = useCallback(async () => {
    setLoading(true);
    try {
      const data = await handsApi.searchHands({
        handId: handIdFilter || undefined,
        userId: userIdFilter || undefined,
        tableId: tableIdFilter || undefined,
        page,
        pageSize: 20,
      });
      setHands(data);
    } catch (error) {
      console.error('Failed to fetch hands:', error);
    } finally {
      setLoading(false);
    }
  }, [handIdFilter, userIdFilter, tableIdFilter, page]);

  useEffect(() => {
    fetchHands();
  }, [fetchHands]);

  const handleSearch = () => {
    setPage(1);
    fetchHands();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const formatDuration = (start: string | null, end: string | null) => {
    if (!start || !end) return '-';
    const startDate = new Date(start);
    const endDate = new Date(end);
    const diffMs = endDate.getTime() - startDate.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const min = Math.floor(diffSec / 60);
    const sec = diffSec % 60;
    return `${min}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">핸드 히스토리</h1>
      </div>

      {/* Search Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <Input
                placeholder="핸드 ID"
                value={handIdFilter}
                onChange={(e) => setHandIdFilter(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
            <div>
              <Input
                placeholder="유저 ID"
                value={userIdFilter}
                onChange={(e) => setUserIdFilter(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
            <div>
              <Input
                placeholder="테이블 ID"
                value={tableIdFilter}
                onChange={(e) => setTableIdFilter(e.target.value)}
                onKeyDown={handleKeyDown}
              />
            </div>
            <div>
              <Button onClick={handleSearch} className="w-full">
                검색
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Hands Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            핸드 목록 {hands && `(${hands.total}건)`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-gray-500">로딩 중...</div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>핸드 #</TableHead>
                    <TableHead>테이블</TableHead>
                    <TableHead className="text-right">팟</TableHead>
                    <TableHead className="text-center">플레이어</TableHead>
                    <TableHead>시작 시간</TableHead>
                    <TableHead>진행 시간</TableHead>
                    <TableHead>작업</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {hands?.items.map((hand) => (
                    <TableRow key={hand.id} className="cursor-pointer hover:bg-gray-50">
                      <TableCell>
                        <div>
                          <p className="font-medium">#{hand.handNumber}</p>
                          <p className="text-xs text-gray-500 font-mono">
                            {hand.id.slice(0, 8)}...
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <p>{hand.tableName || '알 수 없음'}</p>
                          <p className="text-xs text-gray-500 font-mono">
                            {hand.tableId.slice(0, 8)}...
                          </p>
                        </div>
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {hand.potSize.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-center">
                        {hand.playerCount}명
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {hand.startedAt
                          ? new Date(hand.startedAt).toLocaleString('ko-KR')
                          : '-'}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDuration(hand.startedAt, hand.endedAt)}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => router.push(`/hands/${hand.id}`)}
                        >
                          리플레이
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {hands?.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                        핸드 기록이 없습니다
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {/* Pagination */}
              {hands && hands.totalPages > 1 && (
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
                    {page} / {hands.totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === hands.totalPages}
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
    </div>
  );
}
