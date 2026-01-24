'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
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
import { usersApi, PaginatedUsers, CreateUserData } from '@/lib/users-api';
import { toast } from 'sonner';
import { TableSkeleton } from '@/components/ui/table-skeleton';
import { UsersEmptyState, SearchEmptyState } from '@/components/ui/empty-state';

export default function UsersPage() {
  const router = useRouter();
  const [users, setUsers] = useState<PaginatedUsers | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [banFilter, setBanFilter] = useState<string>('all');
  const [page, setPage] = useState(1);

  // Create user modal state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm, setCreateForm] = useState<CreateUserData>({
    nickname: '',
    email: '',
    password: '',
    balance: 10000,
  });

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        search: search || undefined,
        isBanned: banFilter === 'all' ? undefined : banFilter === 'banned',
        page,
        pageSize: 20,
      };
      const data = await usersApi.listUsers(params);
      setUsers(data);
    } catch (error) {
      console.error('Failed to fetch users:', error);
      toast.error('사용자 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [search, banFilter, page]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleSearch = () => {
    setPage(1);
    fetchUsers();
  };

  const handleCreateUser = async () => {
    if (!createForm.nickname || !createForm.email || !createForm.password) {
      toast.error('모든 필수 항목을 입력해주세요');
      return;
    }

    setCreateLoading(true);
    try {
      await usersApi.createUser(createForm);
      toast.success('사용자가 생성되었습니다');
      setCreateModalOpen(false);
      setCreateForm({ nickname: '', email: '', password: '', balance: 10000 });
      fetchUsers();
    } catch (error) {
      console.error('Failed to create user:', error);
      toast.error(error instanceof Error ? error.message : '사용자 생성에 실패했습니다');
    } finally {
      setCreateLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">사용자 관리</h1>
        <Button onClick={() => setCreateModalOpen(true)}>
          + 사용자 추가
        </Button>
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
            <Select value={banFilter} onValueChange={setBanFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="상태" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체</SelectItem>
                <SelectItem value="active">활성</SelectItem>
                <SelectItem value="banned">제재됨</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={handleSearch}>검색</Button>
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            사용자 목록 {users && `(${users.total}명)`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton
              columns={6}
              rows={10}
              headers={['아이디', '닉네임', '이메일', '잔액', '상태', '가입일']}
            />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>아이디</TableHead>
                    <TableHead>닉네임</TableHead>
                    <TableHead>이메일</TableHead>
                    <TableHead className="text-right">잔액</TableHead>
                    <TableHead>상태</TableHead>
                    <TableHead>가입일</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users?.items.map((user) => (
                    <TableRow
                      key={user.id}
                      className="cursor-pointer hover:bg-gray-50"
                      onClick={() => router.push(`/users/${user.id}`)}
                    >
                      <TableCell className="font-medium text-blue-600">
                        {user.username}
                      </TableCell>
                      <TableCell>{user.nickname || user.username}</TableCell>
                      <TableCell className="text-gray-500">{user.email}</TableCell>
                      <TableCell className="text-right">
                        {user.balance.toLocaleString()} 원
                      </TableCell>
                      <TableCell>
                        {user.isBanned ? (
                          <span className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs">
                            제재됨
                          </span>
                        ) : (
                          <span className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs">
                            활성
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {user.createdAt ? new Date(user.createdAt).toLocaleDateString('ko-KR') : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {users?.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="p-0">
                        {search ? (
                          <SearchEmptyState
                            query={search}
                            onClear={() => {
                              setSearch('');
                              setBanFilter('all');
                              setPage(1);
                            }}
                          />
                        ) : (
                          <UsersEmptyState onRefresh={fetchUsers} />
                        )}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {/* Pagination */}
              {users && users.totalPages > 1 && (
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
                    {page} / {users.totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === users.totalPages}
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

      {/* Create User Modal */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>사용자 추가</DialogTitle>
            <DialogDescription>
              새로운 사용자를 생성합니다.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="nickname">닉네임 *</Label>
              <Input
                id="nickname"
                placeholder="닉네임을 입력하세요"
                value={createForm.nickname}
                onChange={(e) => setCreateForm({ ...createForm, nickname: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="email">이메일 *</Label>
              <Input
                id="email"
                type="email"
                placeholder="이메일을 입력하세요"
                value={createForm.email}
                onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">비밀번호 *</Label>
              <Input
                id="password"
                type="password"
                placeholder="비밀번호를 입력하세요 (최소 8자)"
                value={createForm.password}
                onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="balance">초기 잔액</Label>
              <Input
                id="balance"
                type="number"
                placeholder="초기 잔액"
                value={createForm.balance}
                onChange={(e) => setCreateForm({ ...createForm, balance: Number(e.target.value) })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateModalOpen(false)}>
              취소
            </Button>
            <Button onClick={handleCreateUser} disabled={createLoading}>
              {createLoading ? '생성 중...' : '생성'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
