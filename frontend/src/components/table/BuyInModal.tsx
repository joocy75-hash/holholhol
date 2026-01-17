'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  slideUp,
  fadeIn,
  springTransition,
} from '@/lib/animations';

/**
 * Figma 정밀 좌표 (BG-frame 621x548 기준, 절대 좌표에서 계산)
 *
 * BG-frame 원점: (111, -326)
 *
 * | 요소 | left | top | width | height |
 * |-----|------|-----|-------|--------|
 * | 바이인 (제목) | center | 33 | 64 | 28 |
 * | ROOMNAME | center | 69 | 146 | 26 |
 * | balance-container | 46 | 126 | 530 | 61 |
 * | min-btn | 50 | 130 | 100 | 53 |
 * | max-btn | 472 | 130 | 100 | 53 |
 * | 400 텍스트 | 78 | 207 | 41 | 24 |
 * | 2,000 텍스트 | right=69 | 207 | 60 | 24 |
 * | Line 1 (점선) | 177 | 219 | 268 | - |
 * | 슬라이더 | 80 | 251 | 444 | 39 |
 * | 트랙 | 97 | 264 | 427 | 12 |
 * | 노브 | 80 | 251 | 47 | 47 (viewBox) |
 * | 보유머니 | 28 | 316 | 567 | 56 |
 * | 취소 | 28 | 405 | 175 | 88 |
 * | 바이인 버튼 | 217 | 405 | 378 | 88 |
 */

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
  tableName = 'ROOMNAME',
}: BuyInModalProps) {
  const minBuyIn = config.minBuyIn || 400;
  const maxBuyIn = Math.min(config.maxBuyIn || 2000, userBalance);
  const [buyIn, setBuyIn] = useState(minBuyIn);

  const isValidBuyIn = buyIn >= minBuyIn && buyIn <= maxBuyIn;
  const insufficientBalance = userBalance < minBuyIn;

  // 슬라이더 퍼센트 계산
  const sliderPercent = maxBuyIn > minBuyIn
    ? ((buyIn - minBuyIn) / (maxBuyIn - minBuyIn)) * 100
    : 0;

  const handleMin = () => setBuyIn(minBuyIn);
  const handleMax = () => setBuyIn(maxBuyIn);

  // 트랙 너비: 427px, 노브 실제 크기: 39px (viewBox 47px)
  // 노브 이동 범위: 427 - 39 = 388px
  // 트랙 시작점 (슬라이더 영역 내): 97 - 80 = 17px
  const thumbLeft = 17 + (388 * sliderPercent / 100);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[100] flex items-end justify-center"
        initial="initial"
        animate="animate"
        exit="exit"
        data-testid="buyin-modal"
      >
        {/* 백드롭 */}
        <motion.div
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          variants={fadeIn}
          onClick={onCancel}
        />

        {/* 바텀시트 - Figma: 621x548px */}
        <motion.div
          className="relative flex-shrink-0"
          initial={{ opacity: 0, y: '100%', scale: 0.7 }}
          animate={{ opacity: 1, y: 0, scale: 0.7 }}
          exit={{ opacity: 0, y: '100%', scale: 0.7 }}
          transition={springTransition}
          onClick={(e) => e.stopPropagation()}
          style={{
            width: '621px',
            height: '548px',
            background: 'linear-gradient(180deg, rgba(62, 64, 68, 1) 0%, rgba(48, 50, 55, 1) 10.096%, rgba(40, 42, 47, 1) 39.904%, rgba(34, 36, 41, 1) 77.885%)',
            border: '1px solid #25272c',
            borderRadius: '25px 25px 0 0',
            boxShadow: 'inset 0px 3px 7.2px 0px rgba(182,182,182,0.5)',
            transformOrigin: 'bottom center',
          }}
        >
          {/* 제목 "바이인" - Figma: top=33, center, Paperlogy Bold 24px */}
          <h2
            className="absolute w-full text-center text-white"
            style={{
              top: '33px',
              fontWeight: 700,
              fontSize: '24px',
              lineHeight: '28px',
            }}
          >
            바이인
          </h2>

          {/* ROOMNAME - Figma: top=69, center, Paperlogy Medium 22px, #00ace0 */}
          <p
            className="absolute w-full text-center"
            style={{
              top: '69px',
              fontWeight: 500,
              fontSize: '22px',
              lineHeight: '26px',
              color: '#00ace0',
              textShadow: '0px 4px 4px rgba(0,0,0,0.25)',
            }}
          >
            {tableName}
          </p>

          {insufficientBalance ? (
            <div
              className="absolute p-4 rounded-lg bg-red-500/20 text-red-400 text-center"
              style={{ left: '28px', top: '126px', width: '565px' }}
              data-testid="buyin-error"
            >
              잔액이 부족합니다. 최소 바이인: {minBuyIn.toLocaleString()}
            </div>
          ) : (
            <>
              {/* balance-container (minmax 바) - Figma: left=46, top=126, 530x61 */}
              <div
                className="absolute"
                style={{ left: '46px', top: '126px', width: '530px', height: '61px' }}
              >
                {/* minmax 바 배경 */}
                <img
                  src="/assets/ui/buyin/minmax-bar-final.svg"
                  alt=""
                  className="absolute inset-0 w-full h-full"
                />

                {/* MIN 버튼 - Figma: left=4, top=4 (바 기준), 100x53 */}
                <motion.button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleMin();
                  }}
                  className="absolute flex items-center justify-center z-10"
                  style={{ left: '4px', top: '4px', width: '100px', height: '53px' }}
                  whileHover={{ scale: 1.02, filter: 'brightness(1.1)' }}
                  whileTap={{ scale: 0.98 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                >
                  <img
                    src="/assets/ui/buyin/btn-min-final.svg"
                    alt=""
                    className="absolute inset-0 w-full h-full"
                  />
                  <span
                    className="relative text-white z-10"
                    style={{ fontWeight: 700, fontSize: '18px' }}
                  >
                    MIN
                  </span>
                </motion.button>

                {/* 금액 표시 - Figma: center, 27px, #ffcc00 */}
                <span
                  className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 pointer-events-none"
                  style={{
                    fontWeight: 700,
                    fontSize: '27px',
                    color: '#ffcc00',
                    letterSpacing: '0.27px',
                  }}
                >
                  {buyIn.toLocaleString()}
                </span>

                {/* MAX 버튼 - Figma: right=4, top=4 (바 기준), 100x53 */}
                <motion.button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleMax();
                  }}
                  className="absolute flex items-center justify-center z-10"
                  style={{ right: '4px', top: '4px', width: '100px', height: '53px' }}
                  whileHover={{ scale: 1.02, filter: 'brightness(1.1)' }}
                  whileTap={{ scale: 0.98 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                >
                  <img
                    src="/assets/ui/buyin/btn-max-final.svg"
                    alt=""
                    className="absolute inset-0 w-full h-full"
                  />
                  <span
                    className="relative text-white z-10"
                    style={{ fontWeight: 700, fontSize: '18px' }}
                  >
                    MAX
                  </span>
                </motion.button>
              </div>

              {/* 400 텍스트 - Figma: left=78, top=207 */}
              <span
                className="absolute"
                style={{
                  left: '78px',
                  top: '207px',
                  fontWeight: 600,
                  fontSize: '20px',
                  color: '#a0a0a0',
                  textShadow: '0px 4px 4px rgba(0,0,0,0.25)',
                  letterSpacing: '0.2px',
                }}
              >
                {minBuyIn.toLocaleString()}
              </span>

              {/* 2,000 텍스트 - Figma: right=69, top=207 */}
              <span
                className="absolute text-right"
                style={{
                  right: '69px',
                  top: '207px',
                  fontWeight: 600,
                  fontSize: '20px',
                  color: '#a0a0a0',
                  textShadow: '0px 4px 4px rgba(0,0,0,0.25)',
                  letterSpacing: '0.2px',
                }}
              >
                {maxBuyIn.toLocaleString()}
              </span>

              {/* 점선 - Figma: left=177, top=219, width=268 */}
              <div
                className="absolute"
                style={{
                  left: '177px',
                  top: '219px',
                  width: '268px',
                  borderTop: '1px dashed #666',
                }}
              />

              {/* 슬라이더 영역 - Figma: left=80, top=251, 444x39 */}
              <div
                className="absolute"
                style={{ left: '80px', top: '251px', width: '444px', height: '39px' }}
              >
                {/* 트랙 배경 (비활성) - Figma: left=17 (97-80), 427x12 */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 opacity-30"
                  style={{ left: '17px', width: '427px', height: '12px' }}
                >
                  <img
                    src="/assets/ui/buyin/slider-track-final.svg"
                    alt=""
                    className="w-full h-full"
                    style={{ objectFit: 'fill' }}
                  />
                </div>

                {/* 트랙 채워진 부분 */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 overflow-hidden"
                  style={{
                    left: '17px',
                    width: `${(427 * sliderPercent / 100)}px`,
                    height: '12px'
                  }}
                >
                  <img
                    src="/assets/ui/buyin/slider-track-final.svg"
                    alt=""
                    style={{ width: '427px', height: '12px', objectFit: 'fill' }}
                  />
                </div>

                {/* 슬라이더 input (투명) */}
                <input
                  type="range"
                  min={minBuyIn}
                  max={maxBuyIn}
                  value={buyIn}
                  onChange={(e) => setBuyIn(parseInt(e.target.value))}
                  className="absolute top-0 h-full opacity-0 cursor-pointer z-20"
                  style={{ left: '17px', width: '427px' }}
                  data-testid="buyin-slider"
                />

                {/* 노브 - Figma: viewBox 47x47, 실제 39x39 */}
                <div
                  className="absolute pointer-events-none z-10"
                  style={{
                    left: `${thumbLeft - 4}px`,
                    top: '-4px',
                    width: '47px',
                    height: '47px',
                  }}
                >
                  <img
                    src="/assets/ui/buyin/slider-thumb-final.svg"
                    alt=""
                    className="w-full h-full"
                  />
                </div>
              </div>
            </>
          )}

          {/* 보유 머니 바 - Figma: left=28, top=316, 567x56 */}
          <div
            className="absolute flex items-center"
            style={{
              left: '28px',
              top: '316px',
              width: '567px',
              height: '56px',
            }}
          >
            {/* 배경 */}
            <img
              src="/assets/ui/buyin/balance-bar-final.svg"
              alt=""
              className="absolute inset-0 w-full h-full"
            />

            {/* 보유 머니 라벨 - Figma: Paperlogy Medium 18px, #9d9d9d */}
            <span
              className="relative z-10"
              style={{
                marginLeft: '20px',
                fontWeight: 500,
                fontSize: '18px',
                color: '#9d9d9d'
              }}
            >
              보유 머니
            </span>

            {/* 금액 + 아이콘 - Figma: 20px, #ffcc00 */}
            <div className="relative z-10 flex items-center gap-[8px] ml-auto mr-[17px]">
              <span
                style={{
                  fontWeight: 700,
                  fontSize: '20px',
                  color: '#ffcc00',
                  letterSpacing: '0.2px',
                }}
              >
                {(userBalance - buyIn).toLocaleString()}
              </span>
              <img
                src="/assets/ui/buyin/chip-icon-final.svg"
                alt="chip"
                style={{ width: '26px', height: '26px' }}
              />
            </div>
          </div>

          {/* 취소 버튼 - Figma: left=28, top=405, 175x88 */}
          <motion.button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onCancel();
            }}
            disabled={isLoading}
            className="absolute flex items-center justify-center overflow-hidden"
            style={{
              left: '28px',
              top: '405px',
              width: '175px',
              height: '88px',
              background: 'linear-gradient(90deg, #8d9192 0%, #ddd 51.38%, #cccfd0 100%)',
              border: '1px solid white',
              borderRadius: '15px',
              boxShadow: '0px 5px 10px 0px rgba(0,0,0,0.25)',
            }}
            whileHover={{
              scale: 1.02,
              boxShadow: '0 0 12px rgba(255, 255, 255, 0.3), 0px 5px 10px 0px rgba(0,0,0,0.25)',
            }}
            whileTap={{ scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            data-testid="buyin-cancel"
          >
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                borderRadius: 'inherit',
                boxShadow: 'inset 0px 0px 9.3px 0px white',
              }}
            />
            <span
              className="relative z-10"
              style={{ fontWeight: 700, fontSize: '25px', color: '#303030' }}
            >
              취소
            </span>
          </motion.button>

          {/* 바이인 버튼 - Figma: left=217, top=405, 378x88 */}
          <motion.button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (!isLoading && isValidBuyIn && !insufficientBalance) {
                onConfirm(buyIn);
              }
            }}
            disabled={isLoading || !isValidBuyIn || insufficientBalance}
            className="absolute flex items-center justify-center disabled:opacity-50 overflow-hidden"
            style={{
              left: '217px',
              top: '405px',
              width: '378px',
              height: '88px',
              background: 'linear-gradient(118.13deg, #008cf8 19.74%, #004cc5 43.96%, #003892 68.83%)',
              border: '1px solid #51dfff',
              borderRadius: '15px',
              boxShadow: '0px 3px 5px 0px rgba(0,0,0,0.25)',
            }}
            whileHover={{
              scale: 1.02,
              boxShadow: '0 0 15px rgba(0, 212, 255, 0.4), 0px 3px 5px 0px rgba(0,0,0,0.25)',
            }}
            whileTap={{ scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
            data-testid="buyin-confirm"
          >
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                borderRadius: 'inherit',
                boxShadow: 'inset 0px 0px 9.3px 0px #00d4ff',
              }}
            />
            <span
              className="relative z-10 text-white"
              style={{ fontWeight: 700, fontSize: '25px' }}
            >
              {isLoading ? '참여 중...' : '바이인'}
            </span>
          </motion.button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export type { TableConfig, BuyInModalProps };
