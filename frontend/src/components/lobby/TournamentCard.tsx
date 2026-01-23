"use client";

import { motion } from "framer-motion";

const springTransition = { type: "spring" as const, stiffness: 300, damping: 25 };
const quickSpring = { type: "spring" as const, stiffness: 400, damping: 20 };

interface TournamentCardProps {
  roomId?: string;
  name?: string;
  buyIn?: number;
  onJoin?: (roomId: string) => void;
}

export default function TournamentCard({
  roomId,
  name = "프리롤 하이퍼터보 1000 만 GTD",
  buyIn = 100000,
  onJoin
}: TournamentCardProps) {
  const imgTn1 = "/assets/lobby/tournament-thumb.png";
  const imgTrophyIcon = "/assets/icons/trophy.svg";
  const imgArrowIcon = "/assets/icons/arrow-right.svg";

  return (
    <motion.div
      whileHover={{
        boxShadow: '0 8px 25px rgba(0, 0, 0, 0.3), 0 0 20px rgba(72, 152, 255, 0.2)',
        borderColor: 'rgba(72, 152, 255, 0.5)',
        filter: 'brightness(1.08)',
      }}
      transition={springTransition}
      style={{
        position: 'relative',
        width: '370px',
        height: '126px',
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

      {/* 좌측 블루 그라디언트 영역 */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: '126px',
          height: '126px',
          background: 'var(--figma-gradient-tournament-left)',
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

        {/* 썸네일 이미지 */}
        <img
          src={imgTn1}
          alt="tournament"
          style={{
            position: 'absolute',
            left: '3px',
            top: '5px',
            width: '121px',
            height: '113px',
            objectFit: 'cover',
          }}
        />
      </div>

      {/* 제목 */}
      <p
        style={{
          position: 'absolute',
          left: '140px',
          top: '17px',
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

      {/* 상금 라벨 */}
      <p
        style={{
          position: 'absolute',
          left: '140px',
          top: '44px',
          margin: 0,
          fontFamily: 'Paperlogy, sans-serif',
          fontWeight: 400,
          fontSize: '17px',
          lineHeight: 'normal',
          color: 'white',
          textShadow: 'var(--figma-text-shadow-double)',
        }}
      >
        상금
      </p>

      {/* 트로피 아이콘 */}
      <img
        src={imgTrophyIcon}
        alt="trophy"
        style={{
          position: 'absolute',
          left: '177px',
          top: '45px',
          width: '18px',
          height: '18px',
        }}
      />

      {/* 상금 금액 (블루 그라디언트 텍스트) */}
      <p
        style={{
          position: 'absolute',
          left: '197px',
          top: '42px',
          margin: 0,
          fontFamily: 'Paperlogy, sans-serif',
          fontWeight: 900,
          fontSize: '20px',
          lineHeight: 'normal',
          background: 'var(--figma-gradient-tournament-prize)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          letterSpacing: '1px',
        }}
      >
        1000만
      </p>

      {/* 바이인 박스 */}
      <div
        style={{
          position: 'absolute',
          left: '137px',
          top: '80px',
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
            boxShadow: '0 0 18px rgba(0, 212, 255, 0.5), var(--figma-shadow-btn-blue-inset)',
          } : undefined}
          whileTap={roomId && onJoin ? { filter: 'brightness(0.9)' } : undefined}
          transition={quickSpring}
          style={{
            position: 'absolute',
            left: '114px',
            top: '3px',
            width: '104px',
            height: '28px',
            background: 'var(--figma-gradient-tournament-btn)',
            border: '1px solid var(--figma-btn-border-blue)',
            borderRadius: '15px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            cursor: roomId && onJoin ? 'pointer' : 'default',
          }}
        >
          {/* 버튼 inset glow */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              pointerEvents: 'none',
              borderRadius: 'inherit',
              boxShadow: 'var(--figma-shadow-btn-blue-inset)',
            }}
          />

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
