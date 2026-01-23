'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { partnersApi, CommissionType } from '@/lib/partners-api';
import { usersApi, User } from '@/lib/users-api';
import { toast } from 'sonner';
import { Check, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CreatePartnerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

const commissionTypeOptions = [
  { value: CommissionType.RAKEBACK, label: '레이크백 (하위 유저 레이크의 X%)' },
  { value: CommissionType.REVSHARE, label: '레브쉐어 (하위 유저 순손실의 X%)' },
  { value: CommissionType.TURNOVER, label: '턴오버 (하위 유저 베팅량의 X%)' },
];

export function CreatePartnerDialog({ open, onOpenChange, onSuccess }: CreatePartnerDialogProps) {
  const [loading, setLoading] = useState(false);
  const [userSearchOpen, setUserSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [users, setUsers] = useState<User[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  const [formData, setFormData] = useState({
    partnerCode: '',
    name: '',
    contactInfo: '',
    notes: '',
    commissionType: CommissionType.RAKEBACK,
    commissionRate: 30,
  });

  // Debounced user search
  const searchUsers = useCallback(async (query: string) => {
    if (!query || query.length < 2) {
      setUsers([]);
      return;
    }

    setUsersLoading(true);
    try {
      const result = await usersApi.listUsers({
        search: query,
        pageSize: 10,
      });
      setUsers(result.items);
    } catch (error) {
      console.error('Failed to search users:', error);
    } finally {
      setUsersLoading(false);
    }
  }, []);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      searchUsers(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, searchUsers]);

  const resetForm = () => {
    setFormData({
      partnerCode: '',
      name: '',
      contactInfo: '',
      notes: '',
      commissionType: CommissionType.RAKEBACK,
      commissionRate: 30,
    });
    setSelectedUser(null);
    setSearchQuery('');
    setUsers([]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedUser) {
      toast.error('파트너로 등록할 유저를 선택해주세요.');
      return;
    }
    if (!formData.partnerCode.trim()) {
      toast.error('파트너 코드를 입력해주세요.');
      return;
    }
    if (!formData.name.trim()) {
      toast.error('파트너명을 입력해주세요.');
      return;
    }
    if (formData.commissionRate < 0 || formData.commissionRate > 100) {
      toast.error('수수료율은 0~100% 사이여야 합니다.');
      return;
    }

    setLoading(true);
    try {
      await partnersApi.createPartner({
        userId: selectedUser.id,
        partnerCode: formData.partnerCode.trim().toUpperCase(),
        name: formData.name.trim(),
        contactInfo: formData.contactInfo.trim() || undefined,
        notes: formData.notes.trim() || undefined,
        commissionType: formData.commissionType,
        commissionRate: formData.commissionRate / 100,
      });
      onSuccess();
      onOpenChange(false);
      resetForm();
    } catch (error) {
      console.error('Failed to create partner:', error);
      toast.error(error instanceof Error ? error.message : '파트너 등록에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // Auto-fill partner name with username when user is selected
  const handleUserSelect = (user: User) => {
    setSelectedUser(user);
    if (!formData.name) {
      setFormData(prev => ({ ...prev, name: user.username }));
    }
    setUserSearchOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>파트너 등록</DialogTitle>
          <DialogDescription>
            새로운 파트너(총판)를 등록합니다. 기존 사용자를 파트너로 등록할 수 있습니다.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {/* User Selection */}
            <div className="grid gap-2">
              <Label>유저 선택 *</Label>
              <Popover open={userSearchOpen} onOpenChange={setUserSearchOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={userSearchOpen}
                    className="w-full justify-between"
                  >
                    {selectedUser ? (
                      <span className="flex items-center gap-2">
                        <span className="font-medium">{selectedUser.username}</span>
                        <span className="text-gray-500 text-sm">({selectedUser.email})</span>
                      </span>
                    ) : (
                      <span className="text-gray-500">유저를 검색하여 선택하세요...</span>
                    )}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[450px] p-0" align="start">
                  <Command shouldFilter={false}>
                    <CommandInput
                      placeholder="닉네임 또는 이메일로 검색..."
                      value={searchQuery}
                      onValueChange={setSearchQuery}
                    />
                    <CommandList>
                      {usersLoading ? (
                        <div className="p-4 text-center text-sm text-gray-500">
                          검색 중...
                        </div>
                      ) : searchQuery.length < 2 ? (
                        <div className="p-4 text-center text-sm text-gray-500">
                          2자 이상 입력하세요
                        </div>
                      ) : users.length === 0 ? (
                        <CommandEmpty>검색 결과가 없습니다.</CommandEmpty>
                      ) : (
                        <CommandGroup>
                          {users.map((user) => (
                            <CommandItem
                              key={user.id}
                              value={user.id}
                              onSelect={() => handleUserSelect(user)}
                              className="cursor-pointer"
                            >
                              <Check
                                className={cn(
                                  "mr-2 h-4 w-4",
                                  selectedUser?.id === user.id ? "opacity-100" : "opacity-0"
                                )}
                              />
                              <div className="flex flex-col">
                                <span className="font-medium">{user.username}</span>
                                <span className="text-xs text-gray-500">{user.email}</span>
                              </div>
                              <span className="ml-auto text-xs text-gray-400 font-mono">
                                {user.id.slice(0, 8)}...
                              </span>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      )}
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
              {selectedUser && (
                <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                  <div>유저 ID: <span className="font-mono">{selectedUser.id}</span></div>
                  <div>잔액: {selectedUser.balance.toLocaleString()}원</div>
                </div>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="partnerCode">파트너 코드 *</Label>
              <Input
                id="partnerCode"
                placeholder="예: ABC, VIP01"
                value={formData.partnerCode}
                onChange={(e) => setFormData({ ...formData, partnerCode: e.target.value.toUpperCase() })}
                maxLength={20}
              />
              <p className="text-xs text-gray-500">
                회원 가입 시 입력하는 추천 코드입니다. 대문자로 자동 변환됩니다.
              </p>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="name">파트너명 *</Label>
              <Input
                id="name"
                placeholder="파트너 이름 (표시용)"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
              <p className="text-xs text-gray-500">
                관리자가 파트너를 구분하기 위한 이름입니다.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="contactInfo">연락처</Label>
              <Input
                id="contactInfo"
                placeholder="연락처 정보 (선택)"
                value={formData.contactInfo}
                onChange={(e) => setFormData({ ...formData, contactInfo: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="notes">비고</Label>
              <Textarea
                id="notes"
                placeholder="파트너에 대한 메모 (선택)"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows={3}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="commissionType">수수료 타입</Label>
              <Select
                value={formData.commissionType}
                onValueChange={(value) => setFormData({ ...formData, commissionType: value as CommissionType })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="수수료 타입 선택" />
                </SelectTrigger>
                <SelectContent>
                  {commissionTypeOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="commissionRate">수수료율 (%)</Label>
              <Input
                id="commissionRate"
                type="number"
                min={0}
                max={100}
                step={0.1}
                value={formData.commissionRate}
                onChange={(e) => setFormData({ ...formData, commissionRate: parseFloat(e.target.value) || 0 })}
              />
              <p className="text-xs text-gray-500">
                0~100% 사이의 값을 입력하세요. 예: 30 = 30%
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? '등록 중...' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
