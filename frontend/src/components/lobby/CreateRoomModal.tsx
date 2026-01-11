import { useState } from 'react';
import { Modal } from '@/components/common/Modal';
import { Button } from '@/components/common/Button';
import { useUIStore } from '@/stores/uiStore';

interface CreateRoomFormData {
  name: string;
  smallBlind: number;
  bigBlind: number;
  maxSeats: 2 | 6 | 9;
  minBuyIn: number;
  maxBuyIn: number;
}

interface CreateRoomModalProps {
  onSubmit: (data: CreateRoomFormData) => Promise<void>;
  isLoading?: boolean;
}

const BLIND_PRESETS = [
  { small: 10, big: 20 },
  { small: 25, big: 50 },
  { small: 50, big: 100 },
  { small: 100, big: 200 },
];

const SEAT_OPTIONS: Array<2 | 6 | 9> = [2, 6, 9];

export function CreateRoomModal({ onSubmit, isLoading = false }: CreateRoomModalProps) {
  const { activeModal, closeModal } = useUIStore();
  const isOpen = activeModal === 'create-room';

  const [formData, setFormData] = useState<CreateRoomFormData>({
    name: '',
    smallBlind: 10,
    bigBlind: 20,
    maxSeats: 6,
    minBuyIn: 400,
    maxBuyIn: 2000,
  });

  const [errors, setErrors] = useState<Partial<Record<keyof CreateRoomFormData, string>>>({});

  const validateForm = (): boolean => {
    const newErrors: typeof errors = {};

    if (!formData.name.trim()) {
      newErrors.name = '방 이름을 입력해주세요';
    } else if (formData.name.length < 2 || formData.name.length > 20) {
      newErrors.name = '방 이름은 2-20자여야 합니다';
    }

    const minBB = formData.bigBlind * 20;
    const maxBB = formData.bigBlind * 200;

    if (formData.minBuyIn < minBB) {
      newErrors.minBuyIn = `최소 바이인은 ${minBB} (20 BB) 이상이어야 합니다`;
    }

    if (formData.maxBuyIn > maxBB) {
      newErrors.maxBuyIn = `최대 바이인은 ${maxBB} (200 BB) 이하여야 합니다`;
    }

    if (formData.minBuyIn > formData.maxBuyIn) {
      newErrors.minBuyIn = '최소 바이인이 최대보다 클 수 없습니다';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;

    try {
      await onSubmit(formData);
      closeModal();
      setFormData({
        name: '',
        smallBlind: 10,
        bigBlind: 20,
        maxSeats: 6,
        minBuyIn: 400,
        maxBuyIn: 2000,
      });
    } catch {
      // Error handling is done in parent
    }
  };

  const handleBlindSelect = (small: number, big: number) => {
    setFormData((prev) => ({
      ...prev,
      smallBlind: small,
      bigBlind: big,
      minBuyIn: big * 20,
      maxBuyIn: big * 100,
    }));
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={closeModal}
      title="방 만들기"
      footer={
        <>
          <Button variant="ghost" onClick={closeModal}>
            취소
          </Button>
          <Button onClick={handleSubmit} loading={isLoading}>
            방 만들기
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Room Name */}
        <div>
          <label className="block text-sm font-medium text-text mb-1">방 이름</label>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
            placeholder="초보자 테이블"
            className="input"
            maxLength={20}
          />
          {errors.name && <p className="mt-1 text-sm text-danger">{errors.name}</p>}
        </div>

        {/* Blinds */}
        <div>
          <label className="block text-sm font-medium text-text mb-2">블라인드</label>
          <div className="flex gap-2">
            {BLIND_PRESETS.map((preset) => (
              <button
                key={`${preset.small}/${preset.big}`}
                type="button"
                onClick={() => handleBlindSelect(preset.small, preset.big)}
                className={`flex-1 py-2 text-sm rounded transition-colors ${
                  formData.smallBlind === preset.small
                    ? 'bg-primary text-white'
                    : 'bg-surface text-text hover:bg-surface-light'
                }`}
              >
                {preset.small}/{preset.big}
              </button>
            ))}
          </div>
        </div>

        {/* Max Seats */}
        <div>
          <label className="block text-sm font-medium text-text mb-2">최대 인원</label>
          <div className="flex gap-2">
            {SEAT_OPTIONS.map((seats) => (
              <button
                key={seats}
                type="button"
                onClick={() => setFormData((prev) => ({ ...prev, maxSeats: seats }))}
                className={`flex-1 py-2 text-sm rounded transition-colors ${
                  formData.maxSeats === seats
                    ? 'bg-primary text-white'
                    : 'bg-surface text-text hover:bg-surface-light'
                }`}
              >
                {seats}인
              </button>
            ))}
          </div>
        </div>

        {/* Buy-in Range */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-text mb-1">최소 바이인</label>
            <input
              type="number"
              value={formData.minBuyIn}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, minBuyIn: parseInt(e.target.value) || 0 }))
              }
              className="input"
              min={formData.bigBlind * 20}
            />
            {errors.minBuyIn && <p className="mt-1 text-sm text-danger">{errors.minBuyIn}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-text mb-1">최대 바이인</label>
            <input
              type="number"
              value={formData.maxBuyIn}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, maxBuyIn: parseInt(e.target.value) || 0 }))
              }
              className="input"
              max={formData.bigBlind * 200}
            />
            {errors.maxBuyIn && <p className="mt-1 text-sm text-danger">{errors.maxBuyIn}</p>}
          </div>
        </div>

        <p className="text-xs text-text-muted">
          바이인 범위: {formData.bigBlind * 20} ~ {formData.bigBlind * 200} (20-200 BB)
        </p>
      </form>
    </Modal>
  );
}
