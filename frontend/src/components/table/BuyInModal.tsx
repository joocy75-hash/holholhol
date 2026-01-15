'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  slideUp,
  fadeIn,
  springTransition,
} from '@/lib/animations';

interface TableConfig {
  maxSeats: number;
  smallBlind: number;
  bigBlind: number;
  minBuyIn: number;
  maxBuyIn: number;
  turnTimeoutSeconds: number;
}

interface BuyInModalProps {
  config: TableConfig;
  userBalance: number;
  onConfirm: (buyIn: number) => void;
  onCancel: () => void;
  isLoading: boolean;
  tableName?: string;
}

export function BuyInModal({
  config,
  userBalance,
  onConfirm,
  onCancel,
  isLoading,
  tableName = '테이블',
}: BuyInModalProps) {
  const minBuyIn = config.minBuyIn || 400;
  const maxBuyIn = Math.min(config.maxBuyIn || 2000, userBalance);
  const [buyIn, setBuyIn] = useState(minBuyIn);

  const isValidBuyIn = buyIn >= minBuyIn && buyIn <= maxBuyIn;
  const insufficientBalance = userBalance < minBuyIn;

  console.log('🎰 BuyInModal rendered:', { minBuyIn, maxBuyIn, buyIn, isValidBuyIn, insufficientBalance, userBalance });

  // 슬라이더 퍼센트 계산
  const sliderPercent = maxBuyIn > minBuyIn
    ? ((buyIn - minBuyIn) / (maxBuyIn - minBuyIn)) * 100
    : 100;

  const handleMin = () => setBuyIn(minBuyIn);
  const handleMax = () => setBuyIn(maxBuyIn);

  return (
    <AnimatePresence>
      <motion.div 
        className="fixed inset-0 z-[100] flex items-end justify-center"
        initial="initial"
        animate="animate"
        exit="exit"
        data-testid="buyin-modal"
      >
        {/* 백드롭 - fadeIn + backdrop-blur */}
        <motion.div
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          variants={fadeIn}
          onClick={onCancel}
        />
        
        {/* 바텀시트 - slideUp + spring */}
        <motion.div
          className="relative w-full max-w-[500px]"
          variants={slideUp}
          transition={springTransition}
          onClick={(e) => e.stopPropagation()}
          style={{
            backgroundImage: "url('/assets/ui/buyin/bg-panel.png')",
            backgroundSize: '100% 100%',
            backgroundRepeat: 'no-repeat',
          }}
        >
        <div className="px-6 pt-8 pb-6">
          {/* 제목 */}
          <h2 className="text-center text-white text-xl font-bold mb-2">바이인</h2>

          {/* 테이블 정보 */}
          <p className="text-center text-[#4FC3F7] text-base mb-6 underline underline-offset-4">
            {tableName} {config.smallBlind.toLocaleString()}/{config.bigBlind.toLocaleString()}
          </p>

          {insufficientBalance ? (
            <div className="mb-6 p-4 rounded-lg bg-red-500/20 text-red-400 text-center" data-testid="buyin-error">
              잔액이 부족합니다. 최소 바이인: {minBuyIn.toLocaleString()}
            </div>
          ) : (
            <>
              {/* MIN/MAX 바 - 698x73 @2x → 349x36.5 @1x */}
              <div
                className="relative h-[37px] mb-6 flex items-center"
                style={{
                  backgroundImage: "url('/assets/ui/buyin/bar-minmax.png')",
                  backgroundSize: '100% 100%',
                }}
              >
                {/* MIN 버튼 - 144x70 @2x → 72x35 @1x */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('[BuyInModal] MIN clicked');
                    handleMin();
                  }}
                  className="absolute left-0 top-0 bottom-0 w-[72px] flex items-center justify-center text-white font-bold text-xs active:scale-95 transition-transform z-10"
                  style={{
                    backgroundImage: "url('/assets/ui/buyin/btn-min.png')",
                    backgroundSize: '100% 100%',
                  }}
                >
                  MIN
                </button>

                {/* 금액 표시 */}
                <span className="absolute left-1/2 -translate-x-1/2 text-[#FFD700] text-xl font-bold pointer-events-none">
                  {buyIn.toLocaleString()}
                </span>

                {/* MAX 버튼 - 144x70 @2x → 72x35 @1x */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('[BuyInModal] MAX clicked');
                    handleMax();
                  }}
                  className="absolute right-0 top-0 bottom-0 w-[72px] flex items-center justify-center text-white font-bold text-xs active:scale-95 transition-transform z-10"
                  style={{
                    backgroundImage: "url('/assets/ui/buyin/btn-max.png')",
                    backgroundSize: '100% 100%',
                  }}
                >
                  MAX
                </button>
              </div>

              {/* 최소/최대 표시 */}
              <div className="flex justify-between text-[#FFD700] text-sm mb-2 px-2">
                <span>{minBuyIn.toLocaleString()}</span>
                <span className="text-gray-500">- - - - - - - - - - - - - -</span>
                <span>{maxBuyIn.toLocaleString()}</span>
              </div>

              {/* 슬라이더 */}
              <div className="relative h-[52px] mb-6 mx-2">
                {/* 트랙 배경 */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 left-[24px] right-[24px] h-[26px]"
                  style={{
                    backgroundImage: "url('/assets/ui/buyin/slider-track.png')",
                    backgroundSize: '100% 100%',
                    opacity: 0.3,
                  }}
                />
                {/* 트랙 채워진 부분 */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 left-[24px] h-[26px]"
                  style={{
                    width: `calc((100% - 48px) * ${sliderPercent / 100})`,
                    backgroundImage: "url('/assets/ui/buyin/slider-track.png')",
                    backgroundSize: '100% 100%',
                  }}
                />
                {/* 슬라이더 input (투명) */}
                <input
                  type="range"
                  min={minBuyIn}
                  max={maxBuyIn}
                  value={buyIn}
                  onChange={(e) => setBuyIn(parseInt(e.target.value))}
                  className="absolute top-0 left-[24px] right-[24px] h-full opacity-0 cursor-pointer z-10"
                  style={{ width: 'calc(100% - 48px)' }}
                  data-testid="buyin-slider"
                />
                {/* 노브 */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-[48px] h-[48px] pointer-events-none"
                  style={{
                    left: `calc(${sliderPercent / 100} * (100% - 48px))`,
                    backgroundImage: "url('/assets/ui/buyin/slider-thumb.png')",
                    backgroundSize: 'contain',
                    backgroundPosition: 'center',
                    backgroundRepeat: 'no-repeat',
                  }}
                />
              </div>
            </>
          )}

          {/* 보유 골드 */}
          <div
            className="relative h-[42px] mb-6 flex items-center justify-between px-4"
            style={{
              backgroundImage: "url('/assets/ui/buyin/bar-balance.png')",
              backgroundSize: '100% 100%',
            }}
          >
            <span className="text-gray-400 text-sm">보유 골드</span>
            <div className="flex items-center gap-2">
              <img
                src="/assets/ui/buyin/icon-gold.png"
                alt="gold"
                className="w-6 h-6 object-contain"
              />
              <span className="text-[#FFD700] text-base font-bold">
                {userBalance.toLocaleString()}
              </span>
            </div>
          </div>

          {/* 버튼 영역 */}
          <div className="flex relative z-10">
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[BuyInModal] Cancel clicked');
                onCancel();
              }}
              disabled={isLoading}
              className="flex-[258] h-[73px] flex items-center justify-center text-gray-700 font-bold text-base active:scale-95 transition-transform"
              style={{
                backgroundImage: "url('/assets/ui/buyin/btn-cancel.png')",
                backgroundSize: '100% 100%',
              }}
              data-testid="buyin-cancel"
            >
              닫기
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[BuyInModal] Confirm clicked, buyIn:', buyIn);
                if (!isLoading && isValidBuyIn && !insufficientBalance) {
                  onConfirm(buyIn);
                }
              }}
              disabled={isLoading || !isValidBuyIn || insufficientBalance}
              className="flex-[431] h-[73px] flex items-center justify-center text-white font-bold text-base disabled:opacity-50 active:scale-95 transition-transform"
              style={{
                backgroundImage: "url('/assets/ui/buyin/btn-confirm.png')",
                backgroundSize: '100% 100%',
              }}
              data-testid="buyin-confirm"
            >
              {isLoading ? '참여 중...' : '확인'}
            </button>
          </div>
        </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export type { TableConfig, BuyInModalProps };
