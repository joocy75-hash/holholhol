"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuthStore } from "@/stores/auth";
import { usersApi } from "@/lib/api";
import { Avatar } from "@/components/common";
import { VIPBadge } from "@/components/common/VIPBadge";

const quickSpring = { type: "spring" as const, stiffness: 400, damping: 20 };

export default function LobbyHeader() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [vipLevel, setVipLevel] = useState<string | null>(null);

  // VIP 상태 조회
  useEffect(() => {
    const fetchVipStatus = async () => {
      try {
        const response = await usersApi.getVIPStatus();
        setVipLevel(response.data.level);
      } catch {
        // VIP 상태 조회 실패 시 무시
      }
    };

    if (isAuthenticated) {
      fetchVipStatus();
    }
  }, [isAuthenticated]);

  const imgUsdtIcon = "/assets/icons/usdt.svg";

  return (
    <div
      style={{
        position: 'relative',
        width: '390px',
        height: '90px',
        background: 'var(--figma-gradient-header)',
      }}
    >
      {/* 헤더 inset shadow */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          boxShadow: 'var(--figma-shadow-header-inset)',
        }}
      />

      {/* 프로필 박스 배경 */}
      <motion.div
        whileHover={{
          boxShadow: '0 0 15px rgba(147, 51, 234, 0.25)',
        }}
        transition={quickSpring}
        style={{
          position: 'absolute',
          left: '17px',
          top: '15px',
          width: '219px',
          height: '60px',
          background: 'var(--figma-profile-box-bg)',
          borderRadius: '500px 15px 15px 500px',
          cursor: 'pointer',
        }}
      />

      {/* 프로필 이미지 */}
      <div
        style={{
          position: 'absolute',
          left: '19px',
          top: '17px',
        }}
      >
        <Avatar
          avatarId={user?.avatarUrl ?? null}
          size="lg"
          nickname={user?.nickname}
          showVIPBadge={false}
        />
      </div>

      {/* 유저네임 + VIP 배지 */}
      <div
        style={{
          position: 'absolute',
          left: '85px',
          top: '26px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}
      >
        <p
          style={{
            margin: 0,
            fontFamily: 'Paperlogy, sans-serif',
            fontWeight: 400,
            fontSize: '12px',
            lineHeight: 'normal',
            color: 'var(--figma-username-color)',
          }}
        >
          {user?.nickname || '유저네임'}
        </p>
        {vipLevel && <VIPBadge level={vipLevel} size="sm" showLabel />}
      </div>

      {/* 잔액 */}
      <p
        style={{
          position: 'absolute',
          left: '85px',
          top: '45px',
          margin: 0,
          fontFamily: 'Paperlogy, sans-serif',
          fontWeight: 600,
          fontSize: '14px',
          lineHeight: 'normal',
          color: 'var(--figma-balance-color)',
          letterSpacing: '0.7px',
        }}
      >
        {(user?.balance || 0).toLocaleString()}
      </p>

      {/* 충전/환전 버튼 */}
      <motion.div
        onClick={() => router.push('/wallet')}
        whileHover={{
          boxShadow: '0 0 20px rgba(0, 255, 200, 0.35), var(--figma-shadow-charge-inset)',
          filter: 'brightness(1.15)',
        }}
        whileTap={{ filter: 'brightness(0.9)' }}
        transition={quickSpring}
        style={{
          position: 'absolute',
          left: '244px',
          top: '14px',
          width: '64px',
          height: '61px',
          background: 'var(--figma-charge-btn-bg)',
          borderRadius: '10px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '4px',
          cursor: 'pointer',
        }}
      >
        {/* inset glow */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            borderRadius: 'inherit',
            boxShadow: 'var(--figma-shadow-charge-inset)',
          }}
        />

        {/* USDT 아이콘 */}
        <img
          src={imgUsdtIcon}
          alt="USDT"
          style={{
            width: '22px',
            height: '22px',
            display: 'block',
          }}
        />

        {/* 지갑 라벨 */}
        <p
          style={{
            margin: 0,
            fontFamily: 'Paperlogy, sans-serif',
            fontWeight: 500,
            fontSize: '10px',
            lineHeight: 'normal',
            color: '#ddd',
            textAlign: 'center',
          }}
        >
          지갑
        </p>
      </motion.div>

      {/* 이벤트/공지 버튼 */}
      <motion.div
        onClick={() => router.push('/events')}
        whileHover={{
          boxShadow: '0 0 20px rgba(255, 200, 0, 0.35)',
          filter: 'brightness(1.15)',
        }}
        whileTap={{ filter: 'brightness(0.9)' }}
        transition={quickSpring}
        style={{
          position: 'absolute',
          left: '316px',
          top: '14px',
          width: '64px',
          height: '61px',
          background: 'var(--figma-profile-box-bg)',
          borderRadius: '10px',
          cursor: 'pointer',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '4px',
        }}
      >
        {/* 이벤트 아이콘 */}
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#FFD700"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {/* 이벤트/공지 라벨 */}
        <p
          style={{
            margin: 0,
            fontFamily: 'Paperlogy, sans-serif',
            fontWeight: 500,
            fontSize: '9px',
            lineHeight: 'normal',
            color: '#ddd',
            textAlign: 'center',
          }}
        >
          이벤트/공지
        </p>
      </motion.div>
    </div>
  );
}
