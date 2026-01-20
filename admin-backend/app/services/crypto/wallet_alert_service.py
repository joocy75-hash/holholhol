"""지갑 잔액 알림 서비스.

Hot wallet 잔액을 모니터링하고 임계값 기반 알림을 전송합니다.
HotWalletBalanceTask와 연동하여 사용됩니다.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from redis.asyncio import Redis

from app.config import get_settings
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class AlertThresholds:
    """알림 임계값 설정."""

    # 경고 임계값 (HIGH 우선순위)
    warning_usdt: Decimal = Decimal("1000.0")

    # 위험 임계값 (CRITICAL 우선순위)
    critical_usdt: Decimal = Decimal("200.0")

    # 정상 복구 마진 (임계값 + 마진 이상이면 정상으로 간주)
    recovery_margin_usdt: Decimal = Decimal("500.0")

    # 알림 쿨다운 (초)
    cooldown_seconds: int = 3600  # 1시간


@dataclass
class WalletAlertState:
    """지갑 알림 상태."""

    # 현재 상태
    is_low_balance: bool = False
    is_critical_balance: bool = False

    # 마지막 알림 시간
    last_warning_alert: Optional[datetime] = None
    last_critical_alert: Optional[datetime] = None
    last_recovery_alert: Optional[datetime] = None

    # 마지막 알림 시 잔액
    last_alerted_balance: Optional[Decimal] = None


class WalletAlertService:
    """지갑 잔액 알림 서비스.

    잔액 임계값을 모니터링하고 상태 변화 시 알림을 전송합니다.

    사용법:
        ```python
        alert_service = WalletAlertService(redis_client)

        # HotWalletBalanceTask 콜백으로 연결
        task.set_low_balance_callback(alert_service.handle_balance_update)
        ```
    """

    def __init__(
        self,
        redis: Redis,
        thresholds: Optional[AlertThresholds] = None,
    ):
        """초기화.

        Args:
            redis: Redis 클라이언트
            thresholds: 알림 임계값 설정 (None이면 기본값 + config 사용)
        """
        self.redis = redis
        self.notification_service = NotificationService(redis)

        # 임계값 설정 (config 우선)
        if thresholds:
            self.thresholds = thresholds
        else:
            self.thresholds = AlertThresholds(
                warning_usdt=Decimal(str(settings.hot_wallet_min_balance)),
                critical_usdt=Decimal(str(settings.hot_wallet_min_balance)) / 5,
            )

        # 상태 (메모리 + Redis 백업)
        self._state = WalletAlertState()
        self._state_key = "wallet:alert:state"

    async def initialize(self) -> None:
        """상태 복구 (서버 재시작 시)."""
        try:
            state_data = await self.redis.hgetall(self._state_key)
            if state_data:
                self._state.is_low_balance = state_data.get(b"is_low") == b"1"
                self._state.is_critical_balance = state_data.get(b"is_critical") == b"1"

                last_warning = state_data.get(b"last_warning")
                if last_warning:
                    self._state.last_warning_alert = datetime.fromisoformat(
                        last_warning.decode()
                    )

                last_critical = state_data.get(b"last_critical")
                if last_critical:
                    self._state.last_critical_alert = datetime.fromisoformat(
                        last_critical.decode()
                    )

                logger.info(
                    f"Wallet alert state restored: "
                    f"low={self._state.is_low_balance}, "
                    f"critical={self._state.is_critical_balance}"
                )
        except Exception as e:
            logger.warning(f"Failed to restore wallet alert state: {e}")

    async def _save_state(self) -> None:
        """상태 저장."""
        try:
            state_data = {
                "is_low": "1" if self._state.is_low_balance else "0",
                "is_critical": "1" if self._state.is_critical_balance else "0",
            }

            if self._state.last_warning_alert:
                state_data["last_warning"] = self._state.last_warning_alert.isoformat()
            if self._state.last_critical_alert:
                state_data["last_critical"] = self._state.last_critical_alert.isoformat()
            if self._state.last_recovery_alert:
                state_data["last_recovery"] = self._state.last_recovery_alert.isoformat()

            await self.redis.hset(self._state_key, mapping=state_data)
            await self.redis.expire(self._state_key, 86400 * 7)  # 7일
        except Exception as e:
            logger.warning(f"Failed to save wallet alert state: {e}")

    def _can_send_alert(self, last_alert: Optional[datetime]) -> bool:
        """알림 쿨다운 확인."""
        if last_alert is None:
            return True

        now = datetime.now(timezone.utc)
        elapsed = (now - last_alert).total_seconds()
        return elapsed >= self.thresholds.cooldown_seconds

    async def handle_balance_update(self, balance_data: dict) -> None:
        """잔액 업데이트 처리 (HotWalletBalanceTask 콜백).

        Args:
            balance_data: 잔액 데이터
                - available_usdt: 사용 가능 잔액
                - threshold_usdt: 경고 임계값
                - deficit_usdt: 부족분
                - pending_usdt: 대기 중 출금
                - balance_usdt: 총 잔액
                - timestamp: 타임스탬프
        """
        available = Decimal(str(balance_data.get("available_usdt", 0)))
        balance = Decimal(str(balance_data.get("balance_usdt", 0)))
        pending = Decimal(str(balance_data.get("pending_usdt", 0)))

        now = datetime.now(timezone.utc)

        # 상태 판정
        is_critical = available < self.thresholds.critical_usdt
        is_warning = available < self.thresholds.warning_usdt
        recovery_threshold = self.thresholds.warning_usdt + self.thresholds.recovery_margin_usdt
        is_recovered = available >= recovery_threshold

        # 위험 상태 처리 (최우선)
        if is_critical:
            if self._can_send_alert(self._state.last_critical_alert):
                await self._send_critical_alert(available)
                self._state.last_critical_alert = now
                self._state.is_critical_balance = True
                self._state.is_low_balance = True
                self._state.last_alerted_balance = available
                await self._save_state()
                return

        # 경고 상태 처리
        elif is_warning and not is_recovered:
            if self._can_send_alert(self._state.last_warning_alert):
                deficit = self.thresholds.warning_usdt - available
                await self._send_warning_alert(
                    available=float(available),
                    threshold=float(self.thresholds.warning_usdt),
                    deficit=float(deficit),
                    balance=float(balance),
                    pending=float(pending),
                )
                self._state.last_warning_alert = now
                self._state.is_low_balance = True
                self._state.is_critical_balance = False
                self._state.last_alerted_balance = available
                await self._save_state()
                return

        # 정상 복구 처리
        if is_recovered and self._state.is_low_balance:
            if self._can_send_alert(self._state.last_recovery_alert):
                previous = float(self._state.last_alerted_balance or 0)
                await self._send_recovery_alert(
                    previous=previous,
                    current=float(available),
                    threshold=float(self.thresholds.warning_usdt),
                )
                self._state.last_recovery_alert = now
                self._state.is_low_balance = False
                self._state.is_critical_balance = False
                self._state.last_alerted_balance = available
                await self._save_state()

    async def _send_critical_alert(self, available: Decimal) -> None:
        """위험 알림 전송."""
        logger.critical(
            f"CRITICAL: Wallet balance critically low! "
            f"Available: {available:.2f} USDT "
            f"(threshold: {self.thresholds.critical_usdt:.2f} USDT)"
        )

        await self.notification_service.notify_wallet_critical_balance(
            available_usdt=float(available),
            threshold_usdt=float(self.thresholds.critical_usdt),
        )

    async def _send_warning_alert(
        self,
        available: float,
        threshold: float,
        deficit: float,
        balance: float,
        pending: float,
    ) -> None:
        """경고 알림 전송."""
        logger.warning(
            f"WARNING: Wallet balance low! "
            f"Available: {available:.2f} USDT "
            f"(threshold: {threshold:.2f} USDT, deficit: {deficit:.2f} USDT)"
        )

        await self.notification_service.notify_wallet_low_balance(
            available_usdt=available,
            threshold_usdt=threshold,
            deficit_usdt=deficit,
            balance_usdt=balance,
            pending_usdt=pending,
        )

    async def _send_recovery_alert(
        self,
        previous: float,
        current: float,
        threshold: float,
    ) -> None:
        """정상 복구 알림 전송."""
        logger.info(
            f"INFO: Wallet balance restored! "
            f"Previous: {previous:.2f} USDT → Current: {current:.2f} USDT"
        )

        await self.notification_service.notify_wallet_balance_restored(
            previous_usdt=previous,
            current_usdt=current,
            threshold_usdt=threshold,
        )

    async def get_current_status(self) -> dict:
        """현재 알림 상태 조회."""
        return {
            "is_low_balance": self._state.is_low_balance,
            "is_critical_balance": self._state.is_critical_balance,
            "thresholds": {
                "warning_usdt": float(self.thresholds.warning_usdt),
                "critical_usdt": float(self.thresholds.critical_usdt),
                "recovery_margin_usdt": float(self.thresholds.recovery_margin_usdt),
            },
            "last_alerts": {
                "warning": self._state.last_warning_alert.isoformat()
                    if self._state.last_warning_alert else None,
                "critical": self._state.last_critical_alert.isoformat()
                    if self._state.last_critical_alert else None,
                "recovery": self._state.last_recovery_alert.isoformat()
                    if self._state.last_recovery_alert else None,
            },
            "last_alerted_balance_usdt": float(self._state.last_alerted_balance)
                if self._state.last_alerted_balance else None,
        }

    async def update_thresholds(
        self,
        warning_usdt: Optional[float] = None,
        critical_usdt: Optional[float] = None,
        recovery_margin_usdt: Optional[float] = None,
        cooldown_seconds: Optional[int] = None,
    ) -> dict:
        """임계값 동적 업데이트.

        Args:
            warning_usdt: 경고 임계값
            critical_usdt: 위험 임계값
            recovery_margin_usdt: 복구 마진
            cooldown_seconds: 알림 쿨다운

        Returns:
            업데이트된 임계값
        """
        if warning_usdt is not None:
            self.thresholds.warning_usdt = Decimal(str(warning_usdt))
        if critical_usdt is not None:
            self.thresholds.critical_usdt = Decimal(str(critical_usdt))
        if recovery_margin_usdt is not None:
            self.thresholds.recovery_margin_usdt = Decimal(str(recovery_margin_usdt))
        if cooldown_seconds is not None:
            self.thresholds.cooldown_seconds = cooldown_seconds

        logger.info(
            f"Wallet alert thresholds updated: "
            f"warning={self.thresholds.warning_usdt}, "
            f"critical={self.thresholds.critical_usdt}"
        )

        return {
            "warning_usdt": float(self.thresholds.warning_usdt),
            "critical_usdt": float(self.thresholds.critical_usdt),
            "recovery_margin_usdt": float(self.thresholds.recovery_margin_usdt),
            "cooldown_seconds": self.thresholds.cooldown_seconds,
        }

    async def force_check(self, balance_usdt: float, pending_usdt: float = 0) -> dict:
        """수동 잔액 체크 및 알림.

        Args:
            balance_usdt: 현재 잔액
            pending_usdt: 대기 중 출금

        Returns:
            체크 결과
        """
        available = balance_usdt - pending_usdt

        await self.handle_balance_update({
            "available_usdt": available,
            "balance_usdt": balance_usdt,
            "pending_usdt": pending_usdt,
            "threshold_usdt": float(self.thresholds.warning_usdt),
            "deficit_usdt": max(0, float(self.thresholds.warning_usdt) - available),
        })

        return await self.get_current_status()
