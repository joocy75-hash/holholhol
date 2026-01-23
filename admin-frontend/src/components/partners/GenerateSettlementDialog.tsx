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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { partnersApi, SettlementPeriod } from '@/lib/partners-api';
import { toast } from 'sonner';

interface GenerateSettlementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

const periodTypeOptions = [
  { value: SettlementPeriod.DAILY, label: '일간' },
  { value: SettlementPeriod.WEEKLY, label: '주간' },
  { value: SettlementPeriod.MONTHLY, label: '월간' },
];

function getDefaultDates(periodType: SettlementPeriod) {
  const now = new Date();
  let start: Date;
  let end: Date;

  switch (periodType) {
    case SettlementPeriod.DAILY:
      // 어제
      start = new Date(now);
      start.setDate(start.getDate() - 1);
      start.setHours(0, 0, 0, 0);
      end = new Date(start);
      end.setHours(23, 59, 59, 999);
      break;
    case SettlementPeriod.WEEKLY:
      // 지난 주 (월~일)
      const dayOfWeek = now.getDay();
      const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
      start = new Date(now);
      start.setDate(start.getDate() - daysToMonday - 7);
      start.setHours(0, 0, 0, 0);
      end = new Date(start);
      end.setDate(end.getDate() + 6);
      end.setHours(23, 59, 59, 999);
      break;
    case SettlementPeriod.MONTHLY:
      // 지난 달
      start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      end = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59, 999);
      break;
  }

  return {
    periodStart: start.toISOString().split('T')[0],
    periodEnd: end.toISOString().split('T')[0],
  };
}

export function GenerateSettlementDialog({ open, onOpenChange, onSuccess }: GenerateSettlementDialogProps) {
  const [loading, setLoading] = useState(false);
  const [periodType, setPeriodType] = useState<SettlementPeriod>(SettlementPeriod.MONTHLY);
  const defaultDates = getDefaultDates(periodType);
  const [periodStart, setPeriodStart] = useState(defaultDates.periodStart);
  const [periodEnd, setPeriodEnd] = useState(defaultDates.periodEnd);

  const handlePeriodTypeChange = (value: SettlementPeriod) => {
    setPeriodType(value);
    const dates = getDefaultDates(value);
    setPeriodStart(dates.periodStart);
    setPeriodEnd(dates.periodEnd);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!periodStart || !periodEnd) {
      toast.error('정산 기간을 입력해주세요.');
      return;
    }

    const startDate = new Date(periodStart);
    const endDate = new Date(periodEnd);
    if (startDate > endDate) {
      toast.error('시작일이 종료일보다 늦을 수 없습니다.');
      return;
    }

    setLoading(true);
    try {
      const result = await partnersApi.generateSettlements({
        periodType,
        periodStart: new Date(periodStart).toISOString(),
        periodEnd: new Date(periodEnd + 'T23:59:59').toISOString(),
      });

      if (Array.isArray(result) && result.length > 0) {
        toast.success(`${result.length}건의 정산이 생성되었습니다.`);
      } else {
        toast.info('생성된 정산이 없습니다. (해당 기간에 활동한 파트너가 없거나 이미 정산이 완료되었습니다.)');
      }

      onSuccess();
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to generate settlements:', error);
      toast.error(error instanceof Error ? error.message : '정산 생성에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle>정산 생성</DialogTitle>
          <DialogDescription>
            선택한 기간에 대한 파트너 정산을 일괄 생성합니다.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>정산 주기</Label>
              <Select
                value={periodType}
                onValueChange={(value) => handlePeriodTypeChange(value as SettlementPeriod)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="정산 주기 선택" />
                </SelectTrigger>
                <SelectContent>
                  {periodTypeOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="periodStart">시작일</Label>
                <Input
                  id="periodStart"
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="periodEnd">종료일</Label>
                <Input
                  id="periodEnd"
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                />
              </div>
            </div>
            <p className="text-sm text-gray-500">
              활성 상태인 모든 파트너에 대해 정산이 생성됩니다.
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              취소
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? '생성 중...' : '정산 생성'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
