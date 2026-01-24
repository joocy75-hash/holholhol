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
import { TableSkeleton } from '@/components/ui/table-skeleton';
import { toast } from 'sonner';

// TODO: 백엔드 API 구현 후 실제 데이터 타입으로 교체
interface SuspiciousUser {
  id: string;
  username: string;
  email: string;
  suspicionScore: number; // 0-100
  flags: string[]; // ['bot', 'collusion', 'multi_account', etc.]
  lastActivity: string;
  handsPlayed: number;
  winRate: number;
  vpip?: number; // Voluntarily Put money In Pot
  pfr?: number; // Pre-Flop Raise
}

export default function SuspiciousPage() {
  const router = useRouter();
  const [users, setUsers] = useState<SuspiciousUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [flagFilter, setFlagFilter] = useState<string>('all');
  const [page, setPage] = useState(1);

  const fetchSuspiciousUsers = useCallback(async () => {
    setLoading(true);
    try {
      // TODO: 실제 API 호출로 교체
      // const response = await fetch('/api/admin/suspicious');
      // const data = await response.json();

      // 임시 데이터 (개발용)
      await new Promise(resolve => setTimeout(resolve, 500));
      setUsers([]);

      toast.info('백엔드 API가 아직 구현되지 않았습니다.');
    } catch (error) {
      console.error('Failed to fetch suspicious users:', error);
      toast.error('의심 사용자 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [search, flagFilter, page]);

  useEffect(() => {
    fetchSuspiciousUsers();
  }, [fetchSuspiciousUsers]);

  const handleSearch = () => {
    setPage(1);
    fetchSuspiciousUsers();
  };

  const getSuspicionBadge = (score: number) => {
    if (score >= 80) {
      return <span className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-semibold">위험</span>;
    } else if (score >= 60) {
      return <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-semibold">경고</span>;
    } else if (score >= 40) {
      return <span className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs font-semibold">주의</span>;
    } else {
      return <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">낮음</span>;
    }
  };

  const getFlagBadge = (flag: string) => {
    const badges: Record<string, { label: string; className: string }> = {
      bot: { label: '봇 의심', className: 'bg-purple-100 text-purple-700' },
      collusion: { label: '담합', className: 'bg-red-100 text-red-700' },
      multi_account: { label: '다중계정', className: 'bg-orange-100 text-orange-700' },
      suspicious_pattern: { label: '이상패턴', className: 'bg-yellow-100 text-yellow-700' },
    };

    const badgeInfo = badges[flag] || { label: flag, className: 'bg-gray-100 text-gray-700' };

    return (
      <span className={`px-2 py-1 rounded text-xs ${badgeInfo.className}`}>
        {badgeInfo.label}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">의심 사용자 모니터링</h1>
        <Button onClick={fetchSuspiciousUsers} variant="outline">
          새로고침
        </Button>
      </div>

      {/* 요약 통계 */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              총 의심 사용자
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{users.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              위험 등급
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {users.filter(u => u.suspicionScore >= 80).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              경고 등급
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {users.filter(u => u.suspicionScore >= 60 && u.suspicionScore < 80).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">
              주의 등급
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {users.filter(u => u.suspicionScore >= 40 && u.suspicionScore < 60).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search & Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <Input
              placeholder="사용자명, 이메일, ID 검색..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="max-w-sm"
            />
            <Select value={flagFilter} onValueChange={setFlagFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="필터" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체</SelectItem>
                <SelectItem value="bot">봇 의심</SelectItem>
                <SelectItem value="collusion">담합</SelectItem>
                <SelectItem value="multi_account">다중계정</SelectItem>
                <SelectItem value="suspicious_pattern">이상패턴</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleSearch}>검색</Button>
          </div>
        </CardContent>
      </Card>

      {/* Suspicious Users Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            의심 사용자 목록 {users.length > 0 && `(${users.length}명)`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton
              columns={8}
              rows={10}
              headers={['ID', '사용자명', '의심 점수', '플래그', '핸드 수', '승률', '통계', '최근 활동']}
            />
          ) : (
            <>
              {users.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-gray-400 mb-4">
                    <svg
                      className="mx-auto h-12 w-12"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    의심 사용자가 없습니다
                  </h3>
                  <p className="text-gray-500 mb-6">
                    현재 시스템에서 감지된 의심스러운 활동이 없습니다.
                    <br />
                    백엔드 API 구현 후 실시간으로 모니터링됩니다.
                  </p>
                  <Button onClick={fetchSuspiciousUsers} variant="outline">
                    다시 확인
                  </Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>사용자명</TableHead>
                      <TableHead>의심 점수</TableHead>
                      <TableHead>플래그</TableHead>
                      <TableHead className="text-right">핸드 수</TableHead>
                      <TableHead className="text-right">승률</TableHead>
                      <TableHead>통계 (VPIP/PFR)</TableHead>
                      <TableHead>최근 활동</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow
                        key={user.id}
                        className="cursor-pointer hover:bg-gray-50"
                        onClick={() => router.push(`/users/${user.id}`)}
                      >
                        <TableCell className="font-mono text-xs">
                          {user.id.slice(0, 8)}...
                        </TableCell>
                        <TableCell className="font-medium">{user.username}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getSuspicionBadge(user.suspicionScore)}
                            <span className="text-sm text-gray-600">{user.suspicionScore}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1 flex-wrap">
                            {user.flags.map((flag) => (
                              <div key={flag}>{getFlagBadge(flag)}</div>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          {user.handsPlayed.toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right">
                          {user.winRate.toFixed(1)}%
                        </TableCell>
                        <TableCell>
                          {user.vpip !== undefined && user.pfr !== undefined
                            ? `${user.vpip.toFixed(0)}/${user.pfr.toFixed(0)}`
                            : '-'}
                        </TableCell>
                        <TableCell className="text-sm text-gray-500">
                          {user.lastActivity
                            ? new Date(user.lastActivity).toLocaleString('ko-KR')
                            : '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* 안내 메시지 */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <div className="text-blue-600">
              <svg
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <div className="flex-1">
              <h4 className="font-semibold text-blue-900 mb-1">구현 예정 기능</h4>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• 봇 탐지: VPIP/PFR 패턴 분석, 액션 타이밍, 일정한 베팅 패턴</li>
                <li>• 담합 탐지: 동일 IP, 동시 폴드 패턴, 상호 이익 행동</li>
                <li>• 다중 계정: 디바이스 핑거프린트, 행동 패턴 유사도</li>
                <li>• 이상 패턴: 비정상적인 승률, 극단적 플레이 스타일</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
