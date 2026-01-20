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
import { Switch } from '@/components/ui/switch';
import { roomsApi, CreateRoomData, RoomType } from '@/lib/rooms-api';
import { toast } from 'sonner';

interface CreateRoomDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function CreateRoomDialog({ open, onOpenChange, onSuccess }: CreateRoomDialogProps) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<CreateRoomData>({
    name: '',
    description: '',
    roomType: 'cash',
    maxSeats: 9,
    smallBlind: 10,
    bigBlind: 20,
    buyInMin: 400,
    buyInMax: 2000,
    turnTimeout: 30,
    isPrivate: false,
    password: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      toast.error('방 이름을 입력해주세요.');
      return;
    }

    // 값 검증 (초기값이 있으므로 non-null assertion 사용)
    if (formData.smallBlind! >= formData.bigBlind!) {
      toast.error('스몰 블라인드는 빅 블라인드보다 작아야 합니다.');
      return;
    }

    if (formData.buyInMin! >= formData.buyInMax!) {
      toast.error('최소 바이인은 최대 바이인보다 작아야 합니다.');
      return;
    }

    if (formData.isPrivate && !formData.password) {
      toast.error('비공개 방은 비밀번호가 필요합니다.');
      return;
    }

    setLoading(true);
    try {
      const data: CreateRoomData = {
        ...formData,
        password: formData.isPrivate ? formData.password : undefined,
      };
      await roomsApi.createRoom(data);
      onSuccess();
      resetForm();
    } catch (error) {
      console.error('Failed to create room:', error);
      toast.error('방 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      roomType: 'cash',
      maxSeats: 9,
      smallBlind: 10,
      bigBlind: 20,
      buyInMin: 400,
      buyInMax: 2000,
      turnTimeout: 30,
      isPrivate: false,
      password: '',
    });
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      resetForm();
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>방 생성</DialogTitle>
          <DialogDescription>
            새로운 게임 방을 생성합니다. 시스템 소유 방으로 생성됩니다.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            {/* 방 이름 */}
            <div className="grid gap-2">
              <Label htmlFor="name">방 이름 *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="방 이름을 입력하세요"
                maxLength={100}
              />
            </div>

            {/* 설명 */}
            <div className="grid gap-2">
              <Label htmlFor="description">설명</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="방 설명 (선택)"
                rows={2}
              />
            </div>

            {/* 타입 & 좌석 수 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>게임 타입</Label>
                <Select
                  value={formData.roomType}
                  onValueChange={(value: RoomType) => setFormData({ ...formData, roomType: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cash">캐시 게임</SelectItem>
                    <SelectItem value="tournament">토너먼트</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>좌석 수</Label>
                <Select
                  value={String(formData.maxSeats)}
                  onValueChange={(value) => setFormData({ ...formData, maxSeats: parseInt(value) as 6 | 9 })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="6">6인석</SelectItem>
                    <SelectItem value="9">9인석</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* 블라인드 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="smallBlind">스몰 블라인드</Label>
                <Input
                  id="smallBlind"
                  type="number"
                  value={formData.smallBlind}
                  onChange={(e) => setFormData({ ...formData, smallBlind: parseInt(e.target.value) || 0 })}
                  min={1}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="bigBlind">빅 블라인드</Label>
                <Input
                  id="bigBlind"
                  type="number"
                  value={formData.bigBlind}
                  onChange={(e) => setFormData({ ...formData, bigBlind: parseInt(e.target.value) || 0 })}
                  min={2}
                />
              </div>
            </div>

            {/* 바이인 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="buyInMin">최소 바이인</Label>
                <Input
                  id="buyInMin"
                  type="number"
                  value={formData.buyInMin}
                  onChange={(e) => setFormData({ ...formData, buyInMin: parseInt(e.target.value) || 0 })}
                  min={1}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="buyInMax">최대 바이인</Label>
                <Input
                  id="buyInMax"
                  type="number"
                  value={formData.buyInMax}
                  onChange={(e) => setFormData({ ...formData, buyInMax: parseInt(e.target.value) || 0 })}
                  min={1}
                />
              </div>
            </div>

            {/* 턴 타임아웃 */}
            <div className="grid gap-2">
              <Label htmlFor="turnTimeout">턴 타임아웃 (초)</Label>
              <Input
                id="turnTimeout"
                type="number"
                value={formData.turnTimeout}
                onChange={(e) => setFormData({ ...formData, turnTimeout: parseInt(e.target.value) || 30 })}
                min={10}
                max={120}
              />
            </div>

            {/* 비공개 설정 */}
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label>비공개 방</Label>
                <p className="text-sm text-muted-foreground">
                  비밀번호를 입력해야 입장할 수 있습니다
                </p>
              </div>
              <Switch
                checked={formData.isPrivate}
                onCheckedChange={(checked) => setFormData({ ...formData, isPrivate: checked })}
              />
            </div>

            {/* 비밀번호 */}
            {formData.isPrivate && (
              <div className="grid gap-2">
                <Label htmlFor="password">비밀번호 *</Label>
                <Input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="비밀번호 입력"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => handleOpenChange(false)}>
              취소
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? '생성 중...' : '생성'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
