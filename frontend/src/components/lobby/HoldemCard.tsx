"use client";

import { motion } from "framer-motion";

const springTransition = { type: "spring" as const, stiffness: 300, damping: 25 };
const quickSpring = { type: "spring" as const, stiffness: 400, damping: 20 };

interface HoldemCardProps {
  roomId?: string;
  name?: string;
  maxSeats?: number;
  buyIn?: number;
  onJoin?: (roomId: string) => void;
}

export default function HoldemCard({
  roomId,
  name = "텍사스 홀덤",
  maxSeats = 6,
  buyIn = 100000,
  onJoin
}: HoldemCardProps) {
  const imgHoldemLogo = "/assets/lobby/holdem-logo.svg";
  const imgUsersIcon = "/assets/icons/users.svg";
  const imgArrowIcon = "/assets/icons/arrow-right.svg";

  return (
    <motion.div
      whileHover={{
        boxShadow: '0 8px 25px rgba(0, 0, 0, 0.3), 0 0 20px rgba(152, 118, 255, 0.25)',
        borderColor: 'rgba(152, 118, 255, 0.5)',
        filter: 'brightness(1.08)',
      }}
      transition={springTransition}
      style={{
        position: 'relative',
        width: '370px',
        height: '93px',
        background: 'var(--figma-card-bg)',
        border: '1px solid var(--figma-card-border)',
        borderRadius: '15px',
        boxShadow: 'var(--figma-shadow-card)',
        cursor: 'pointer',
      }}
    >
      {/* 카드 inset shadow */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          borderRadius: 'inherit',
          boxShadow: 'var(--figma-shadow-card-inset)',
        }}
      />

      {/* 좌측 다크 그레이 그라디언트 영역 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: '126px',
          height: '93px',
          background: 'var(--figma-gradient-holdem-left)',
          borderRadius: '15px 0 0 15px',
        }}
      >
        {/* 좌측 영역 inset shadow */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            borderRadius: 'inherit',
            boxShadow: 'var(--figma-shadow-left-area-inset)',
          }}
        />

        {/* 홀덤 로고 */}
        <img
          src={imgHoldemLogo}
          alt="holdem"
          style={{
            position: 'absolute',
            left: '28px',
            top: '34px',
            width: '70px',
            height: '23px',
          }}
        />
      </div>

      {/* 유저 아이콘 */}
      <img
        src={imgUsersIcon}
        alt="users"
        style={{
          position: 'absolute',
          left: '132px',
          top: '16px',
          width: '16px',
          height: '16px',
        }}
      />

      {/* 6인 텍스트 (퍼플 그라디언트) */}
      <p
        style={{
          position: 'absolute',
          left: '154px',
          top: '16px',
          margin: 0,
          fontFamily: 'Paperlogy, sans-serif',
          fontWeight: 600,
          fontSize: '15px',
          lineHeight: 'normal',
          background: 'var(--figma-gradient-holdem-seats)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        }}
      >
        {maxSeats}인
      </p>

      {/* 테이블 이름 */}
      <p
        style={{
          position: 'absolute',
          left: '198px',
          top: '18px',
          margin: 0,
          fontFamily: 'Paperlogy, sans-serif',
          fontWeight: 600,
          fontSize: '13px',
          lineHeight: 'normal',
          color: 'white',
          textShadow: 'var(--figma-text-shadow-basic)',
        }}
      >
        {name}
      </p>

      {/* 바이인 박스 */}
      <div
        style={{
          position: 'absolute',
          left: '137px',
          top: '46px',
          width: '221px',
          height: '34px',
          background: 'var(--figma-buyin-box-bg)',
          borderRadius: '100px',
        }}
      >
        {/* 바이인 박스 inset shadow */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            borderRadius: 'inherit',
            boxShadow: 'var(--figma-shadow-buyin-inset)',
          }}
        />

        {/* 바이인 라벨 */}
        <p
          style={{
            position: 'absolute',
            left: '13px',
            top: '11px',
            margin: 0,
            fontFamily: 'Paperlogy, sans-serif',
            fontWeight: 600,
            fontSize: '10px',
            lineHeight: 'normal',
            color: '#ccc',
          }}
        >
          바이인
        </p>

        {/* 바이인 금액 */}
        <p
          style={{
            position: 'absolute',
            left: '44px',
            top: '10px',
            margin: 0,
            fontFamily: 'Paperlogy, sans-serif',
            fontWeight: 600,
            fontSize: '12px',
            lineHeight: 'normal',
            color: 'var(--figma-buyin-amount-color)',
          }}
        >
          {buyIn.toLocaleString()}
        </p>

        {/* 참여하기 버튼 */}
        <motion.div
          onClick={() => roomId && onJoin && onJoin(roomId)}
          whileHover={roomId && onJoin ? {
            filter: 'brightness(1.2)',
            boxShadow: '0 0 18px rgba(152, 118, 255, 0.5), var(--figma-shadow-tab-purple-inset)',
          } : undefined}
          whileTap={roomId && onJoin ? { filter: 'brightness(0.9)' } : undefined}
          transition={quickSpring}
          style={{
            position: 'absolute',
            left: '114px',
            top: '3px',
            width: '104px',
            height: '28px',
            background: 'var(--figma-gradient-holdem-btn)',
            border: '1px solid var(--figma-tab-border-purple)',
            borderRadius: '15px',
            boxShadow: 'var(--figma-shadow-card), var(--figma-shadow-tab-purple-inset)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            cursor: roomId && onJoin ? 'pointer' : 'default',
          }}
        >
          {/* 참여하기 텍스트 */}
          <p
            style={{
              margin: 0,
              fontFamily: 'Paperlogy, sans-serif',
              fontWeight: 600,
              fontSize: '13px',
              lineHeight: 'normal',
              color: 'white',
            }}
          >
            참여하기
          </p>

          {/* 화살표 아이콘 */}
          <motion.img
            src={imgArrowIcon}
            alt="arrow"
            whileHover={{ x: 3 }}
            transition={{ duration: 0.2 }}
            style={{
              width: '12px',
              height: '12px',
            }}
          />
        </motion.div>
      </div>
    </motion.div>
  );
}
