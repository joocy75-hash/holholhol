'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { announcementsApi, ActiveAnnouncement, checkinApi, CheckinStatusResponse, referralApi, ReferralStatsResponse } from '@/lib/api';
import { useAnnouncementStore } from '@/stores/announcement';
import BottomNavigation from '@/components/lobby/BottomNavigation';

const TYPE_LABELS: Record<string, string> = {
  notice: '공지',
  event: '이벤트',
  maintenance: '점검',
  urgent: '긴급',
};

// 공지에 포함될 타입들
const NOTICE_TYPES = ['notice', 'maintenance', 'urgent'];

export default function EventsPage() {
  const router = useRouter();
  const [announcements, setAnnouncements] = useState<ActiveAnnouncement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAnnouncement, setSelectedAnnouncement] = useState<ActiveAnnouncement | null>(null);

  // 출석체크 상태
  const [checkinStatus, setCheckinStatus] = useState<CheckinStatusResponse | null>(null);
  const [checkinLoading, setCheckinLoading] = useState(false);
  const [checkinResult, setCheckinResult] = useState<{ success: boolean; reward: number; streak: number; bonus?: string } | null>(null);

  // 친구추천 상태
  const [referralStats, setReferralStats] = useState<ReferralStatsResponse | null>(null);
  const [codeCopied, setCodeCopied] = useState(false);

  const { markAsRead } = useAnnouncementStore();

  const fetchAnnouncements = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await announcementsApi.getActive(50);
      setAnnouncements(response.data.items || []);
    } catch (err) {
      console.error('Failed to fetch announcements:', err);
      setError('공지사항을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  // 출석체크 상태 조회
  const fetchCheckinStatus = useCallback(async () => {
    try {
      const response = await checkinApi.getStatus();
      setCheckinStatus(response.data);
    } catch (err) {
      console.error('Failed to fetch checkin status:', err);
    }
  }, []);

  // 출석체크 수행
  const handleCheckin = useCallback(async () => {
    if (checkinLoading || !checkinStatus?.can_checkin) return;

    setCheckinLoading(true);
    setCheckinResult(null);

    try {
      const response = await checkinApi.doCheckin();
      const data = response.data;

      setCheckinResult({
        success: true,
        reward: data.reward_amount,
        streak: data.streak_days,
        bonus: data.bonus_rewards.length > 0 ? data.bonus_rewards[0].type : undefined,
      });

      // 상태 갱신
      await fetchCheckinStatus();
    } catch (err: unknown) {
      const errorMessage = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '출석체크에 실패했습니다';
      setCheckinResult({
        success: false,
        reward: 0,
        streak: checkinStatus?.streak_days || 0,
      });
      console.error('Checkin failed:', errorMessage);
    } finally {
      setCheckinLoading(false);
    }
  }, [checkinLoading, checkinStatus, fetchCheckinStatus]);

  // 친구추천 통계 조회
  const fetchReferralStats = useCallback(async () => {
    try {
      const response = await referralApi.getStats();
      setReferralStats(response.data);
    } catch (err) {
      console.error('Failed to fetch referral stats:', err);
    }
  }, []);

  // 추천 코드 복사
  const copyReferralCode = useCallback(() => {
    if (referralStats?.referral_code) {
      navigator.clipboard.writeText(referralStats.referral_code);
      setCodeCopied(true);
      setTimeout(() => setCodeCopied(false), 2000);
    }
  }, [referralStats]);

  useEffect(() => {
    fetchAnnouncements();
    fetchCheckinStatus();
    fetchReferralStats();
  }, [fetchAnnouncements, fetchCheckinStatus, fetchReferralStats]);

  // 이벤트와 공지 분리
  const events = useMemo(() => {
    return announcements.filter((item) => item.announcement_type === 'event');
  }, [announcements]);

  const notices = useMemo(() => {
    return announcements.filter((item) => NOTICE_TYPES.includes(item.announcement_type));
  }, [announcements]);

  const handleSelect = (item: ActiveAnnouncement) => {
    setSelectedAnnouncement(item);
    markAsRead(item.id);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // 아이템 렌더링 컴포넌트
  const renderItem = (item: ActiveAnnouncement) => (
    <motion.div
      key={item.id}
      whileTap={{ scale: 0.99 }}
      onClick={() => handleSelect(item)}
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: '10px',
        padding: '14px 16px',
        cursor: 'pointer',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <span
          style={{
            fontSize: '11px',
            color: 'rgba(255,255,255,0.5)',
            background: 'rgba(255,255,255,0.06)',
            padding: '3px 8px',
            borderRadius: '4px',
            fontWeight: 500,
          }}
        >
          {TYPE_LABELS[item.announcement_type] || '공지'}
        </span>
        {item.priority === 'critical' && (
          <span
            style={{
              fontSize: '10px',
              color: '#f87171',
              fontWeight: 600,
            }}
          >
            긴급
          </span>
        )}
      </div>
      <h3
        style={{
          color: '#fff',
          fontSize: '14px',
          fontWeight: 500,
          margin: '0 0 4px 0',
          lineHeight: 1.4,
        }}
      >
        {item.title}
      </h3>
      <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: '12px', margin: 0 }}>
        {formatDate(item.created_at)}
      </p>
    </motion.div>
  );

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: '430px',
        minHeight: '100vh',
        margin: '0 auto',
        background: '#0f172a',
        paddingBottom: '100px',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px 20px',
          background: '#0f172a',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <button
          onClick={() => router.back()}
          style={{
            background: 'transparent',
            border: 'none',
            padding: '8px 12px',
            color: 'rgba(255,255,255,0.6)',
            cursor: 'pointer',
            fontSize: '14px',
          }}
        >
          ← 뒤로
        </button>
        <h1 style={{ color: '#fff', fontSize: '17px', fontWeight: 600, margin: 0 }}>
          이벤트/공지
        </h1>
      </div>

      {/* Content */}
      <div style={{ padding: '16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                border: '2px solid rgba(255,255,255,0.1)',
                borderTopColor: 'rgba(255,255,255,0.5)',
                borderRadius: '50%',
                margin: '0 auto 16px',
                animation: 'spin 1s linear infinite',
              }}
            />
            <style jsx>{`
              @keyframes spin {
                to { transform: rotate(360deg); }
              }
            `}</style>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '13px', margin: 0 }}>
              로딩 중...
            </p>
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '13px', margin: '0 0 16px 0' }}>
              {error}
            </p>
            <button
              onClick={fetchAnnouncements}
              style={{
                padding: '10px 20px',
                background: 'rgba(255, 255, 255, 0.08)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                color: 'rgba(255,255,255,0.7)',
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              다시 시도
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* 출석체크 섹션 */}
            <div
              style={{
                background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(147, 51, 234, 0.15) 100%)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                borderRadius: '16px',
                padding: '20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div>
                  <h2 style={{ color: '#fff', fontSize: '16px', fontWeight: 600, margin: '0 0 4px 0' }}>
                    출석체크
                  </h2>
                  <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px', margin: 0 }}>
                    매일 출석하고 보상 받기
                  </p>
                </div>
                {checkinStatus && (
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color: '#a78bfa', fontSize: '24px', fontWeight: 700 }}>
                      {checkinStatus.streak_days}일
                    </div>
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}>
                      연속 출석
                    </div>
                  </div>
                )}
              </div>

              {/* 이번 달 출석 캘린더 (간략 표시) */}
              {checkinStatus && checkinStatus.monthly_checkins.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {checkinStatus.monthly_checkins.slice(-7).map((c) => (
                      <div
                        key={c.date}
                        style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '8px',
                          background: c.reward_type !== 'daily' ? 'rgba(251, 191, 36, 0.3)' : 'rgba(74, 222, 128, 0.2)',
                          border: c.reward_type !== 'daily' ? '1px solid rgba(251, 191, 36, 0.5)' : '1px solid rgba(74, 222, 128, 0.3)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#fff',
                          fontSize: '11px',
                          fontWeight: 500,
                        }}
                        title={`${c.date}: ${c.reward.toLocaleString()} KRW`}
                      >
                        {new Date(c.date).getDate()}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 다음 보너스 안내 */}
              {checkinStatus?.next_bonus && (
                <div
                  style={{
                    background: 'rgba(0,0,0,0.2)',
                    borderRadius: '8px',
                    padding: '10px 12px',
                    marginBottom: '16px',
                    fontSize: '12px',
                  }}
                >
                  <span style={{ color: 'rgba(255,255,255,0.6)' }}>다음 보너스까지 </span>
                  <span style={{ color: '#fbbf24', fontWeight: 600 }}>{checkinStatus.next_bonus.days_remaining}일</span>
                  <span style={{ color: 'rgba(255,255,255,0.6)' }}> 남음 → </span>
                  <span style={{ color: '#4ade80', fontWeight: 600 }}>{checkinStatus.next_bonus.bonus.toLocaleString()} KRW</span>
                </div>
              )}

              {/* 출석체크 결과 표시 */}
              <AnimatePresence>
                {checkinResult && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    style={{
                      background: checkinResult.success ? 'rgba(74, 222, 128, 0.15)' : 'rgba(248, 113, 113, 0.15)',
                      border: `1px solid ${checkinResult.success ? 'rgba(74, 222, 128, 0.3)' : 'rgba(248, 113, 113, 0.3)'}`,
                      borderRadius: '8px',
                      padding: '12px',
                      marginBottom: '16px',
                      textAlign: 'center',
                    }}
                  >
                    {checkinResult.success ? (
                      <>
                        <div style={{ color: '#4ade80', fontSize: '14px', fontWeight: 600, marginBottom: '4px' }}>
                          출석체크 완료!
                        </div>
                        <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: '12px' }}>
                          +{checkinResult.reward.toLocaleString()} KRW 지급 ({checkinResult.streak}일 연속)
                          {checkinResult.bonus && <span style={{ color: '#fbbf24' }}> · {checkinResult.bonus} 달성!</span>}
                        </div>
                      </>
                    ) : (
                      <div style={{ color: '#f87171', fontSize: '13px' }}>출석체크에 실패했습니다</div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* 출석체크 버튼 */}
              <motion.button
                whileTap={{ scale: checkinStatus?.can_checkin ? 0.98 : 1 }}
                onClick={handleCheckin}
                disabled={!checkinStatus?.can_checkin || checkinLoading}
                style={{
                  width: '100%',
                  padding: '14px',
                  borderRadius: '10px',
                  border: 'none',
                  background: checkinStatus?.can_checkin
                    ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)'
                    : 'rgba(255,255,255,0.1)',
                  color: checkinStatus?.can_checkin ? '#fff' : 'rgba(255,255,255,0.4)',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: checkinStatus?.can_checkin ? 'pointer' : 'default',
                  transition: 'all 0.2s',
                }}
              >
                {checkinLoading
                  ? '처리 중...'
                  : checkinStatus?.can_checkin
                    ? `출석체크 (+${checkinStatus.daily_reward.toLocaleString()} KRW)`
                    : '오늘 출석 완료'}
              </motion.button>
            </div>

            {/* 친구추천 섹션 */}
            {referralStats && (
              <div
                style={{
                  background: 'linear-gradient(135deg, rgba(251, 191, 36, 0.12) 0%, rgba(245, 158, 11, 0.12) 100%)',
                  border: '1px solid rgba(251, 191, 36, 0.25)',
                  borderRadius: '16px',
                  padding: '20px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                  <div>
                    <h2 style={{ color: '#fff', fontSize: '16px', fontWeight: 600, margin: '0 0 4px 0' }}>
                      친구 초대
                    </h2>
                    <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px', margin: 0 }}>
                      친구를 초대하고 보상 받기
                    </p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ color: '#fbbf24', fontSize: '24px', fontWeight: 700 }}>
                      {referralStats.total_referrals}명
                    </div>
                    <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '11px' }}>
                      초대 성공
                    </div>
                  </div>
                </div>

                {/* 보상 안내 */}
                <div
                  style={{
                    display: 'flex',
                    gap: '10px',
                    marginBottom: '16px',
                  }}
                >
                  <div
                    style={{
                      flex: 1,
                      background: 'rgba(0,0,0,0.2)',
                      borderRadius: '8px',
                      padding: '10px',
                      textAlign: 'center',
                    }}
                  >
                    <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '11px', marginBottom: '4px' }}>
                      초대 시 내 보상
                    </div>
                    <div style={{ color: '#4ade80', fontSize: '14px', fontWeight: 600 }}>
                      +{referralStats.referrer_reward.toLocaleString()} KRW
                    </div>
                  </div>
                  <div
                    style={{
                      flex: 1,
                      background: 'rgba(0,0,0,0.2)',
                      borderRadius: '8px',
                      padding: '10px',
                      textAlign: 'center',
                    }}
                  >
                    <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '11px', marginBottom: '4px' }}>
                      친구 가입 보너스
                    </div>
                    <div style={{ color: '#60a5fa', fontSize: '14px', fontWeight: 600 }}>
                      +{referralStats.referee_reward.toLocaleString()} KRW
                    </div>
                  </div>
                </div>

                {/* 누적 보상 */}
                {referralStats.total_rewards > 0 && (
                  <div
                    style={{
                      background: 'rgba(74, 222, 128, 0.1)',
                      borderRadius: '8px',
                      padding: '10px 12px',
                      marginBottom: '16px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '12px' }}>누적 추천 보상</span>
                    <span style={{ color: '#4ade80', fontWeight: 600, fontSize: '14px' }}>
                      {referralStats.total_rewards.toLocaleString()} KRW
                    </span>
                  </div>
                )}

                {/* 추천 코드 */}
                <div
                  style={{
                    background: 'rgba(0,0,0,0.3)',
                    borderRadius: '10px',
                    padding: '14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '10px',
                  }}
                >
                  <div>
                    <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '11px', marginBottom: '4px' }}>
                      내 추천 코드
                    </div>
                    <div style={{ color: '#fff', fontSize: '18px', fontWeight: 700, letterSpacing: '2px' }}>
                      {referralStats.referral_code}
                    </div>
                  </div>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={copyReferralCode}
                    style={{
                      padding: '10px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      background: codeCopied ? 'rgba(74, 222, 128, 0.3)' : 'rgba(251, 191, 36, 0.2)',
                      color: codeCopied ? '#4ade80' : '#fbbf24',
                      fontSize: '13px',
                      fontWeight: 500,
                      cursor: 'pointer',
                    }}
                  >
                    {codeCopied ? '복사됨!' : '복사'}
                  </motion.button>
                </div>

                {/* 최근 초대 목록 */}
                {referralStats.recent_referrals.length > 0 && (
                  <div style={{ marginTop: '12px' }}>
                    <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '11px', marginBottom: '8px' }}>
                      최근 초대한 친구
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {referralStats.recent_referrals.slice(0, 5).map((r, i) => (
                        <span
                          key={i}
                          style={{
                            padding: '4px 10px',
                            background: 'rgba(255,255,255,0.08)',
                            borderRadius: '12px',
                            color: 'rgba(255,255,255,0.7)',
                            fontSize: '12px',
                          }}
                        >
                          {r.nickname}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 이벤트 섹션 */}
            <div>
              <h2
                style={{
                  color: 'rgba(255,255,255,0.7)',
                  fontSize: '13px',
                  fontWeight: 600,
                  margin: '0 0 12px 4px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}
              >
                이벤트 ({events.length})
              </h2>
              {events.length === 0 ? (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '32px 20px',
                    background: 'rgba(255,255,255,0.02)',
                    borderRadius: '10px',
                    border: '1px solid rgba(255,255,255,0.04)',
                  }}
                >
                  <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: '13px', margin: 0 }}>
                    진행 중인 이벤트가 없습니다.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {events.map(renderItem)}
                </div>
              )}
            </div>

            {/* 공지 섹션 */}
            <div>
              <h2
                style={{
                  color: 'rgba(255,255,255,0.7)',
                  fontSize: '13px',
                  fontWeight: 600,
                  margin: '0 0 12px 4px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}
              >
                공지 ({notices.length})
              </h2>
              {notices.length === 0 ? (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '32px 20px',
                    background: 'rgba(255,255,255,0.02)',
                    borderRadius: '10px',
                    border: '1px solid rgba(255,255,255,0.04)',
                  }}
                >
                  <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: '13px', margin: 0 }}>
                    공지사항이 없습니다.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {notices.map(renderItem)}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      <AnimatePresence>
        {selectedAnnouncement && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedAnnouncement(null)}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.7)',
              zIndex: 100,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ type: 'spring', damping: 30, stiffness: 400 }}
              onClick={(e) => e.stopPropagation()}
              style={{
                width: 'calc(100% - 32px)',
                maxWidth: '380px',
                maxHeight: '70vh',
                background: '#1e293b',
                borderRadius: '16px',
                padding: '24px 20px',
                overflowY: 'auto',
              }}
            >
              {/* Type Badge */}
              <div style={{ marginBottom: '12px' }}>
                <span
                  style={{
                    fontSize: '11px',
                    color: 'rgba(255,255,255,0.5)',
                    background: 'rgba(255,255,255,0.08)',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    fontWeight: 500,
                  }}
                >
                  {TYPE_LABELS[selectedAnnouncement.announcement_type] || '공지'}
                </span>
              </div>

              {/* Title */}
              <h2
                style={{
                  color: '#fff',
                  fontSize: '18px',
                  fontWeight: 600,
                  margin: '0 0 6px 0',
                  lineHeight: 1.4,
                }}
              >
                {selectedAnnouncement.title}
              </h2>

              {/* Date */}
              <p
                style={{
                  color: 'rgba(255,255,255,0.35)',
                  fontSize: '12px',
                  margin: '0 0 20px 0',
                }}
              >
                {formatDate(selectedAnnouncement.created_at)}
                {selectedAnnouncement.end_time && ` ~ ${formatDate(selectedAnnouncement.end_time)}`}
              </p>

              {/* Content */}
              <div
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: '10px',
                  padding: '16px',
                  marginBottom: '20px',
                }}
              >
                <p
                  style={{
                    color: 'rgba(255,255,255,0.75)',
                    fontSize: '14px',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.7,
                    margin: 0,
                  }}
                >
                  {selectedAnnouncement.content}
                </p>
              </div>

              {/* Close Button */}
              <button
                onClick={() => setSelectedAnnouncement(null)}
                style={{
                  width: '100%',
                  padding: '14px',
                  background: 'rgba(255,255,255,0.1)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '10px',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                닫기
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom Navigation */}
      <BottomNavigation />
    </div>
  );
}
