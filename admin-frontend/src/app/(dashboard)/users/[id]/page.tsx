'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { usersApi, UserDetail, Transaction, LoginHistory, HandHistory } from '@/lib/users-api';

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.id as string;

  const [user, setUser] = useState<UserDetail | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loginHistory, setLoginHistory] = useState<LoginHistory[]>([]);
  const [hands, setHands] = useState<HandHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('info');

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const data = await usersApi.getUser(userId);
        setUser(data);
      } catch (error) {
        console.error('Failed to fetch user:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, [userId]);

  useEffect(() => {
    const fetchTabData = async () => {
      if (activeTab === 'transactions') {
        const data = await usersApi.getUserTransactions(userId);
        setTransactions(data.items);
      } else if (activeTab === 'logins') {
        const data = await usersApi.getUserLoginHistory(userId);
        setLoginHistory(data.items);
      } else if (activeTab === 'hands') {
        const data = await usersApi.getUserHands(userId);
        setHands(data.items);
      }
    };
    if (userId) fetchTabData();
  }, [userId, activeTab]);

  if (loading) {
    return <div className="text-center py-8">로딩 중...</div>;
  }

  if (!user) {
    return <div className="text-center py-8">사용자를 찾을 수 없습니다</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => router.back()}>← 뒤로</Button>
          <h1 className="text-2xl font-bold">{user.username}</h1>
          {user.isBanned && (
            <span className="px-2 py-1 bg-red-100 text-red-700 rounded text-sm">
              제재됨
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {user.isBanned ? (
            <Button variant="outline">제재 해제</Button>
          ) : (
            <Button variant="destructive">제재하기</Button>
          )}
        </div>
      </div>

      {/* User Info Card */}
      <Card>
        <CardHeader>
          <CardTitle>기본 정보</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-500">ID</p>
              <p className="font-mono text-sm">{user.id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">이메일</p>
              <p>{user.email}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">잔액</p>
              <p className="text-xl font-bold">{user.balance.toLocaleString()} USDT</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">가입일</p>
              <p>{user.createdAt ? new Date(user.createdAt).toLocaleDateString('ko-KR') : '-'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">최근 로그인</p>
              <p>{user.lastLogin ? new Date(user.lastLogin).toLocaleString('ko-KR') : '-'}</p>
            </div>
            {user.isBanned && user.banReason && (
              <div className="col-span-2">
                <p className="text-sm text-gray-500">제재 사유</p>
                <p className="text-red-600">{user.banReason}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="info">정보</TabsTrigger>
          <TabsTrigger value="transactions">거래 내역</TabsTrigger>
          <TabsTrigger value="logins">로그인 기록</TabsTrigger>
          <TabsTrigger value="hands">핸드 기록</TabsTrigger>
        </TabsList>

        <TabsContent value="info">
          <Card>
            <CardContent className="pt-6">
              <p className="text-gray-500">추가 정보가 여기에 표시됩니다.</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="transactions">
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>유형</TableHead>
                    <TableHead className="text-right">금액</TableHead>
                    <TableHead className="text-right">이전 잔액</TableHead>
                    <TableHead className="text-right">이후 잔액</TableHead>
                    <TableHead>설명</TableHead>
                    <TableHead>일시</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transactions.map((tx) => (
                    <TableRow key={tx.id}>
                      <TableCell>{tx.type}</TableCell>
                      <TableCell className={`text-right ${tx.amount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {tx.amount >= 0 ? '+' : ''}{tx.amount.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">{tx.balanceBefore.toLocaleString()}</TableCell>
                      <TableCell className="text-right">{tx.balanceAfter.toLocaleString()}</TableCell>
                      <TableCell>{tx.description || '-'}</TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {tx.createdAt ? new Date(tx.createdAt).toLocaleString('ko-KR') : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {transactions.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-gray-500">
                        거래 내역이 없습니다
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="logins">
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>IP 주소</TableHead>
                    <TableHead>User Agent</TableHead>
                    <TableHead>결과</TableHead>
                    <TableHead>일시</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loginHistory.map((login) => (
                    <TableRow key={login.id}>
                      <TableCell className="font-mono">{login.ipAddress || '-'}</TableCell>
                      <TableCell className="text-sm max-w-xs truncate">{login.userAgent || '-'}</TableCell>
                      <TableCell>
                        {login.success ? (
                          <span className="text-green-600">성공</span>
                        ) : (
                          <span className="text-red-600">실패</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {login.createdAt ? new Date(login.createdAt).toLocaleString('ko-KR') : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {loginHistory.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-8 text-gray-500">
                        로그인 기록이 없습니다
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="hands">
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>핸드 ID</TableHead>
                    <TableHead>포지션</TableHead>
                    <TableHead>카드</TableHead>
                    <TableHead className="text-right">베팅</TableHead>
                    <TableHead className="text-right">획득</TableHead>
                    <TableHead className="text-right">팟</TableHead>
                    <TableHead>일시</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {hands.map((hand) => (
                    <TableRow key={hand.id}>
                      <TableCell className="font-mono text-xs">{hand.handId.slice(0, 8)}...</TableCell>
                      <TableCell>{hand.position ?? '-'}</TableCell>
                      <TableCell className="font-mono">{hand.cards || '-'}</TableCell>
                      <TableCell className="text-right">{hand.betAmount.toLocaleString()}</TableCell>
                      <TableCell className={`text-right ${hand.wonAmount > 0 ? 'text-green-600' : ''}`}>
                        {hand.wonAmount.toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">{hand.potSize.toLocaleString()}</TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {hand.createdAt ? new Date(hand.createdAt).toLocaleString('ko-KR') : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {hands.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                        핸드 기록이 없습니다
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
