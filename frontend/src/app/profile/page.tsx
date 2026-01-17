'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { useAuthStore } from '@/stores/auth';
import { usersApi, UserProfile, UserStats } from '@/lib/api';
import ProfileHeader from '@/components/profile/ProfileHeader';
import StatsCard from '@/components/profile/StatsCard';
import MenuList from '@/components/profile/MenuList';
import EditProfileModal from '@/components/profile/EditProfileModal';
import ChangePasswordModal from '@/components/profile/ChangePasswordModal';
import BottomNavigation from '@/components/lobby/BottomNavigation';

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, fetchUser, logout } = useAuthStore();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [isLoadingAction, setIsLoadingAction] = useState(false);

  // 모달 상태
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);

  // 인증 체크
  useEffect(() => {
    if (!isAuthenticated) {
      fetchUser().catch(() => router.push('/login'));
    }
  }, [isAuthenticated, fetchUser, router]);

  // 프로필 조회
  useEffect(() => {
    const loadProfile = async () => {
      try {
        const response = await usersApi.getProfile();
        setProfile(response.data);
      } catch (error) {
        console.error('프로필 조회 실패:', error);
      }
    };

    if (isAuthenticated) {
      loadProfile();
    }
  }, [isAuthenticated]);

  // 통계 조회
  useEffect(() => {
    const loadStats = async () => {
      setIsLoadingStats(true);
      try {
        const response = await usersApi.getStats();
        setStats(response.data);
      } catch (error) {
        console.error('통계 조회 실패:', error);
        // 에러 시 기본값 설정
        setStats({
          total_hands: 0,
          hands_won: 0,
          vpip: 0,
          pfr: 0,
          biggest_pot: 0,
          win_rate: 0,
        });
      } finally {
        setIsLoadingStats(false);
      }
    };

    if (isAuthenticated) {
      loadStats();
    }
  }, [isAuthenticated]);

  // 프로필 수정
  const handleUpdateProfile = async (data: { nickname: string; avatar_url: string }) => {
    setIsLoadingAction(true);
    try {
      const response = await usersApi.updateProfile(data);
      setProfile(response.data);
      // auth store도 업데이트
      await fetchUser();
    } finally {
      setIsLoadingAction(false);
    }
  };

  // 비밀번호 변경
  const handleChangePassword = async (data: { current_password: string; new_password: string }) => {
    setIsLoadingAction(true);
    try {
      await usersApi.changePassword(data);
    } finally {
      setIsLoadingAction(false);
    }
  };

  // 로그아웃
  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '390px',
        minHeight: '858px',
        margin: '0 auto',
        background: 'var(--figma-bg-main)',
      }}
    >
      {/* 헤더 */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: '390px',
          height: '60px',
          background: 'var(--figma-gradient-header)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <h1
          style={{
            fontFamily: 'Paperlogy, sans-serif',
            fontWeight: 600,
            fontSize: '18px',
            color: 'white',
            textShadow: '0 2px 4px rgba(0,0,0,0.3)',
            margin: 0,
          }}
        >
          마이페이지
        </h1>
      </div>

      {/* 컨텐츠 */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        style={{ paddingTop: '60px', paddingBottom: '120px' }}
      >
        {/* 프로필 헤더 */}
        <ProfileHeader
          user={profile || (user ? {
            id: user.id,
            email: user.email,
            nickname: user.nickname,
            avatar_url: user.avatarUrl || null,
            balance: user.balance,
            total_hands: user.totalHands || 0,
            total_winnings: user.totalWinnings || 0,
            created_at: '',
          } : null)}
          onEditClick={() => setIsEditModalOpen(true)}
        />

        {/* 통계 카드 */}
        <StatsCard stats={stats} isLoading={isLoadingStats} />

        {/* 메뉴 리스트 */}
        <MenuList
          onEditProfile={() => setIsEditModalOpen(true)}
          onChangePassword={() => setIsPasswordModalOpen(true)}
          onLogout={handleLogout}
        />
      </motion.div>

      {/* 하단 네비게이션 */}
      <BottomNavigation />

      {/* 프로필 수정 모달 */}
      <EditProfileModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSave={handleUpdateProfile}
        user={profile}
        isLoading={isLoadingAction}
      />

      {/* 비밀번호 변경 모달 */}
      <ChangePasswordModal
        isOpen={isPasswordModalOpen}
        onClose={() => setIsPasswordModalOpen(false)}
        onSubmit={handleChangePassword}
        isLoading={isLoadingAction}
      />
    </div>
  );
}
