'use client';

import { useState, useEffect } from 'react';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { partnersApi, Partner, CommissionType, PartnerStatus } from '@/lib/partners-api';
import { toast } from 'sonner';

interface UpdatePartnerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  partner: Partner;
  onSuccess: () => void;
}

const commissionTypeOptions = [
  { value: CommissionType.RAKEBACK, label: '레이크백' },
  { value: CommissionType.REVSHARE, label: '레브쉐어' },
  { value: CommissionType.TURNOVER, label: '턴오버' },
];

const statusOptions = [
  { value: PartnerStatus.ACTIVE, label: '활성' },
  { value: PartnerStatus.SUSPENDED, label: '정지' },
];

export function UpdatePartnerDialog({ open, onOpenChange, partner, onSuccess }: UpdatePartnerDialogProps) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    contactInfo: '',
    commissionType: CommissionType.RAKEBACK,
    commissionRate: 30,
    status: PartnerStatus.ACTIVE,
  });

  useEffect(() => {
    if (partner) {
      setFormData({
        name: partner.name,
        contactInfo: partner.contactInfo || '',
        commissionType: partner.commissionType,
        commissionRate: partner.commissionRate * 100,
        status: partner.status,
      });
    }
  }, [partner]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

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
      await partnersApi.updatePartner(partner.id, {
        name: formData.name.trim(),
        contactInfo: formData.contactInfo.trim() || undefined,
        commissionType: formData.commissionType,
        commissionRate: formData.commissionRate / 100,
        status: formData.status,
      });
      onSuccess();
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to update partner:', error);
      toast.error(error instanceof Error ? error.message : '파트너 수정에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>파트너 수정</DialogTitle>
          <DialogDescription>
            파트너 정보를 수정합니다.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">파트너명 *</Label>
              <Input
                id="name"
                placeholder="파트너 이름"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="contactInfo">연락처</Label>
              <Input
                id="contactInfo"
                placeholder="연락처 정보"
                value={formData.contactInfo}
                onChange={(e) => setFormData({ ...formData, contactInfo: e.target.value })}
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
            </div>
            <div className="grid gap-2">
              <Label htmlFor="status">상태</Label>
              <Select
                value={formData.status}
                onValueChange={(value) => setFormData({ ...formData, status: value as PartnerStatus })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="상태 선택" />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? '저장 중...' : '저장'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
