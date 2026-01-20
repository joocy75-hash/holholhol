"""관리자 알림 서비스.

부정 행위 탐지, 긴급 이벤트 등 관리자에게 실시간 알림을 전송합니다.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """알림 유형."""
    
    # 부정 행위 탐지
    FRAUD_CHIP_DUMPING = "fraud_chip_dumping"
    FRAUD_BOT_DETECTED = "fraud_bot_detected"
    FRAUD_COLLUSION = "fraud_collusion"
    
    # 사용자 관련
    USER_LARGE_WITHDRAWAL = "user_large_withdrawal"
    USER_SUSPICIOUS_ACTIVITY = "user_suspicious_activity"
    
    # 시스템
    SYSTEM_ERROR = "system_error"
    SYSTEM_HIGH_LOAD = "system_high_load"
    
    # 입출금
    DEPOSIT_PENDING = "deposit_pending"
    WITHDRAWAL_PENDING = "withdrawal_pending"

    # 지갑 관련 (Phase 9)
    WALLET_LOW_BALANCE = "wallet_low_balance"
    WALLET_CRITICAL_BALANCE = "wallet_critical_balance"
    WALLET_BALANCE_RESTORED = "wallet_balance_restored"


class NotificationPriority(str, Enum):
    """알림 우선순위."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AdminNotification:
    """관리자 알림."""
    
    id: str
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    data: dict[str, Any]
    created_at: datetime
    read: bool = False
    read_by: str | None = None
    read_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "createdAt": self.created_at.isoformat(),
            "read": self.read,
            "readBy": self.read_by,
            "readAt": self.read_at.isoformat() if self.read_at else None,
        }


class NotificationService:
    """알림 서비스."""

    NOTIFICATIONS_KEY = "admin:notifications"
    NOTIFICATIONS_CHANNEL = "admin:notifications:channel"
    MAX_NOTIFICATIONS = 100
    NOTIFICATION_TTL = 86400 * 7  # 7일

    def __init__(self, redis: Redis):
        self.redis = redis

    async def create_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: dict[str, Any] | None = None,
    ) -> AdminNotification:
        """알림 생성 및 발행.

        Args:
            notification_type: 알림 유형
            title: 알림 제목
            message: 알림 내용
            priority: 우선순위
            data: 추가 데이터

        Returns:
            생성된 알림
        """
        notification = AdminNotification(
            id=str(uuid4()),
            type=notification_type,
            priority=priority,
            title=title,
            message=message,
            data=data or {},
            created_at=datetime.now(timezone.utc),
        )

        # Redis에 저장
        await self._store_notification(notification)

        # Pub/Sub으로 발행
        await self._publish_notification(notification)

        logger.info(
            f"알림 생성: type={notification_type.value} "
            f"priority={priority.value} title={title}"
        )

        return notification

    async def get_notifications(
        self,
        limit: int = 50,
        include_read: bool = False,
    ) -> list[dict]:
        """알림 목록 조회.

        Args:
            limit: 최대 개수
            include_read: 읽은 알림 포함 여부

        Returns:
            알림 목록
        """
        # 모든 알림 가져오기 (최대 MAX_NOTIFICATIONS)
        notifications_raw = await self.redis.lrange(
            self.NOTIFICATIONS_KEY, 0, -1
        )

        notifications = []
        for raw in notifications_raw:
            try:
                data = json.loads(raw)
                if not include_read and data.get("read"):
                    continue
                notifications.append(data)
                # 필터링 후 limit 적용
                if len(notifications) >= limit:
                    break
            except json.JSONDecodeError:
                continue

        return notifications

    async def get_unread_count(self) -> int:
        """읽지 않은 알림 개수."""
        notifications = await self.get_notifications(limit=100, include_read=True)
        return sum(1 for n in notifications if not n.get("read"))

    async def get_total_count(self) -> int:
        """전체 알림 개수."""
        return await self.redis.llen(self.NOTIFICATIONS_KEY)

    async def mark_as_read(
        self,
        notification_id: str,
        admin_id: str,
    ) -> bool:
        """알림 읽음 처리.

        Args:
            notification_id: 알림 ID
            admin_id: 관리자 ID

        Returns:
            성공 여부
        """
        notifications_raw = await self.redis.lrange(
            self.NOTIFICATIONS_KEY, 0, -1
        )

        for i, raw in enumerate(notifications_raw):
            try:
                data = json.loads(raw)
                if data.get("id") == notification_id:
                    data["read"] = True
                    data["readBy"] = admin_id
                    data["readAt"] = datetime.now(timezone.utc).isoformat()
                    await self.redis.lset(
                        self.NOTIFICATIONS_KEY, i, json.dumps(data)
                    )
                    return True
            except (json.JSONDecodeError, IndexError):
                continue

        return False

    async def mark_all_as_read(self, admin_id: str) -> int:
        """모든 알림 읽음 처리.

        Args:
            admin_id: 관리자 ID

        Returns:
            읽음 처리된 개수
        """
        notifications_raw = await self.redis.lrange(
            self.NOTIFICATIONS_KEY, 0, -1
        )

        count = 0
        now = datetime.now(timezone.utc).isoformat()

        for i, raw in enumerate(notifications_raw):
            try:
                data = json.loads(raw)
                if not data.get("read"):
                    data["read"] = True
                    data["readBy"] = admin_id
                    data["readAt"] = now
                    await self.redis.lset(
                        self.NOTIFICATIONS_KEY, i, json.dumps(data)
                    )
                    count += 1
            except (json.JSONDecodeError, IndexError):
                continue

        return count

    async def delete_notification(self, notification_id: str) -> bool:
        """알림 삭제.

        Args:
            notification_id: 알림 ID

        Returns:
            성공 여부
        """
        notifications_raw = await self.redis.lrange(
            self.NOTIFICATIONS_KEY, 0, -1
        )

        for raw in notifications_raw:
            try:
                data = json.loads(raw)
                if data.get("id") == notification_id:
                    await self.redis.lrem(self.NOTIFICATIONS_KEY, 1, raw)
                    return True
            except json.JSONDecodeError:
                continue

        return False

    async def _store_notification(self, notification: AdminNotification) -> None:
        """알림 저장."""
        await self.redis.lpush(
            self.NOTIFICATIONS_KEY,
            json.dumps(notification.to_dict())
        )
        # 최대 개수 유지
        await self.redis.ltrim(self.NOTIFICATIONS_KEY, 0, self.MAX_NOTIFICATIONS - 1)
        # TTL 설정
        await self.redis.expire(self.NOTIFICATIONS_KEY, self.NOTIFICATION_TTL)

    async def _publish_notification(self, notification: AdminNotification) -> None:
        """알림 발행 (Pub/Sub)."""
        await self.redis.publish(
            self.NOTIFICATIONS_CHANNEL,
            json.dumps(notification.to_dict())
        )

    # =========================================================================
    # 편의 메서드 - 특정 상황별 알림 생성
    # =========================================================================

    async def notify_chip_dumping(
        self,
        user_id: str,
        target_user_id: str,
        amount: int,
        confidence: float,
    ) -> AdminNotification:
        """칩 밀어주기 탐지 알림."""
        return await self.create_notification(
            notification_type=NotificationType.FRAUD_CHIP_DUMPING,
            priority=NotificationPriority.HIGH,
            title="🚨 칩 밀어주기 의심",
            message=f"사용자 {user_id[:8]}...가 {target_user_id[:8]}...에게 "
                    f"{amount:,}칩을 의심스럽게 전달 (신뢰도: {confidence:.1%})",
            data={
                "userId": user_id,
                "targetUserId": target_user_id,
                "amount": amount,
                "confidence": confidence,
            },
        )

    async def notify_bot_detected(
        self,
        user_id: str,
        indicators: list[str],
        confidence: float,
    ) -> AdminNotification:
        """봇 탐지 알림."""
        return await self.create_notification(
            notification_type=NotificationType.FRAUD_BOT_DETECTED,
            priority=NotificationPriority.HIGH,
            title="🤖 봇 의심 사용자",
            message=f"사용자 {user_id[:8]}...에서 봇 패턴 감지 (신뢰도: {confidence:.1%})",
            data={
                "userId": user_id,
                "indicators": indicators,
                "confidence": confidence,
            },
        )

    async def notify_large_withdrawal(
        self,
        user_id: str,
        amount: int,
        withdrawal_id: str,
    ) -> AdminNotification:
        """대규모 출금 알림."""
        return await self.create_notification(
            notification_type=NotificationType.USER_LARGE_WITHDRAWAL,
            priority=NotificationPriority.MEDIUM,
            title="💰 대규모 출금 요청",
            message=f"사용자 {user_id[:8]}...가 {amount:,}원 출금 요청",
            data={
                "userId": user_id,
                "amount": amount,
                "withdrawalId": withdrawal_id,
            },
        )

    async def notify_pending_withdrawal(
        self,
        count: int,
        total_amount: int,
    ) -> AdminNotification:
        """대기 중 출금 알림."""
        return await self.create_notification(
            notification_type=NotificationType.WITHDRAWAL_PENDING,
            priority=NotificationPriority.MEDIUM,
            title="⏳ 출금 승인 대기",
            message=f"{count}건의 출금 요청이 승인 대기 중 (총 {total_amount:,}원)",
            data={
                "count": count,
                "totalAmount": total_amount,
            },
        )

    async def notify_system_error(
        self,
        error_type: str,
        message: str,
        details: dict | None = None,
    ) -> AdminNotification:
        """시스템 에러 알림."""
        return await self.create_notification(
            notification_type=NotificationType.SYSTEM_ERROR,
            priority=NotificationPriority.CRITICAL,
            title=f"⚠️ 시스템 오류: {error_type}",
            message=message,
            data=details or {},
        )

    async def notify_wallet_low_balance(
        self,
        available_usdt: float,
        threshold_usdt: float,
        deficit_usdt: float,
        balance_usdt: float,
        pending_usdt: float,
    ) -> AdminNotification:
        """지갑 잔액 부족 알림."""
        return await self.create_notification(
            notification_type=NotificationType.WALLET_LOW_BALANCE,
            priority=NotificationPriority.HIGH,
            title="💰 지갑 잔액 부족 경고",
            message=f"사용 가능 잔액: {available_usdt:,.2f} USDT (임계값: {threshold_usdt:,.2f} USDT, "
                    f"부족분: {deficit_usdt:,.2f} USDT)",
            data={
                "availableUsdt": available_usdt,
                "thresholdUsdt": threshold_usdt,
                "deficitUsdt": deficit_usdt,
                "balanceUsdt": balance_usdt,
                "pendingUsdt": pending_usdt,
            },
        )

    async def notify_wallet_critical_balance(
        self,
        available_usdt: float,
        threshold_usdt: float,
    ) -> AdminNotification:
        """지갑 잔액 위험 수준 알림 (출금 불가 임박)."""
        return await self.create_notification(
            notification_type=NotificationType.WALLET_CRITICAL_BALANCE,
            priority=NotificationPriority.CRITICAL,
            title="🚨 지갑 잔액 위험 - 출금 불가 임박",
            message=f"잔액이 매우 낮습니다: {available_usdt:,.2f} USDT "
                    f"(위험 임계값: {threshold_usdt:,.2f} USDT). 즉시 충전이 필요합니다!",
            data={
                "availableUsdt": available_usdt,
                "criticalThresholdUsdt": threshold_usdt,
            },
        )

    async def notify_wallet_balance_restored(
        self,
        previous_usdt: float,
        current_usdt: float,
        threshold_usdt: float,
    ) -> AdminNotification:
        """지갑 잔액 정상화 알림."""
        return await self.create_notification(
            notification_type=NotificationType.WALLET_BALANCE_RESTORED,
            priority=NotificationPriority.LOW,
            title="✅ 지갑 잔액 정상화",
            message=f"잔액이 정상 수준으로 복구되었습니다: {current_usdt:,.2f} USDT "
                    f"(이전: {previous_usdt:,.2f} USDT)",
            data={
                "previousUsdt": previous_usdt,
                "currentUsdt": current_usdt,
                "thresholdUsdt": threshold_usdt,
            },
        )
