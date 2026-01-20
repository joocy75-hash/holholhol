"""Telegram 알림 서비스.

관리자에게 중요한 이벤트를 Telegram으로 알립니다.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from enum import Enum

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AlertLevel(str, Enum):
    """알림 수준."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TelegramAlertService:
    """Telegram 알림 서비스.

    중요한 이벤트를 Telegram Bot API를 통해 관리자에게 전송합니다.

    사용법:
        ```python
        service = TelegramAlertService()

        # 단순 알림
        await service.send_alert(
            title="출금 승인 필요",
            message="100 USDT 출금 요청이 접수되었습니다.",
            level=AlertLevel.WARNING,
        )

        # 구조화된 알림
        await service.notify_large_withdrawal(
            user_id="user123",
            amount_usdt=1000.0,
            to_address="EQ...",
        )
        ```

    환경 변수:
        - TELEGRAM_BOT_TOKEN: Telegram Bot API 토큰
        - TELEGRAM_ADMIN_CHAT_ID: 알림을 받을 채팅 ID
    """

    TELEGRAM_API_BASE = "https://api.telegram.org/bot"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        """초기화.

        Args:
            bot_token: Telegram Bot 토큰 (None이면 환경변수)
            chat_id: 알림 채팅 ID (None이면 환경변수)
        """
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_admin_chat_id
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Telegram 설정 여부."""
        return bool(self.bot_token and self.chat_id)

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 가져오기."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """리소스 정리."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _format_message(
        self,
        title: str,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        data: Optional[dict] = None,
    ) -> str:
        """메시지 포맷팅.

        Args:
            title: 제목
            message: 본문
            level: 알림 수준
            data: 추가 데이터

        Returns:
            포맷된 메시지 (Markdown)
        """
        # 이모지 선택
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨",
        }
        emoji = emoji_map.get(level, "📢")

        # 메시지 구성
        lines = [
            f"{emoji} *{self._escape_markdown(title)}*",
            "",
            self._escape_markdown(message),
        ]

        # 추가 데이터
        if data:
            lines.append("")
            lines.append("```")
            for key, value in data.items():
                lines.append(f"{key}: {value}")
            lines.append("```")

        # 타임스탬프
        now = datetime.now(timezone.utc)
        lines.append("")
        lines.append(f"_{now.strftime('%Y-%m-%d %H:%M:%S')} UTC_")

        return "\n".join(lines)

    def _escape_markdown(self, text: str) -> str:
        """Markdown 특수문자 이스케이프."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text

    async def send_alert(
        self,
        title: str,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        data: Optional[dict] = None,
    ) -> bool:
        """알림 전송.

        Args:
            title: 제목
            message: 본문
            level: 알림 수준
            data: 추가 데이터

        Returns:
            전송 성공 여부
        """
        if not self.is_configured:
            logger.debug("Telegram not configured, skipping alert")
            return False

        formatted = self._format_message(title, message, level, data)

        try:
            client = await self._get_client()
            url = f"{self.TELEGRAM_API_BASE}{self.bot_token}/sendMessage"

            response = await client.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": formatted,
                    "parse_mode": "MarkdownV2",
                    "disable_web_page_preview": True,
                },
            )

            if response.status_code == 200:
                logger.info(f"Telegram alert sent: {title}")
                return True
            else:
                logger.error(
                    f"Failed to send Telegram alert: {response.status_code} "
                    f"{response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            return False

    # =========================================================================
    # 편의 메서드 - 특정 이벤트 알림
    # =========================================================================

    async def notify_large_withdrawal(
        self,
        user_id: str,
        amount_usdt: float,
        amount_krw: int,
        to_address: str,
        withdrawal_id: str,
    ) -> bool:
        """대규모 출금 알림."""
        return await self.send_alert(
            title="대규모 출금 요청",
            message=f"사용자 {user_id[:8]}...가 {amount_usdt:,.2f} USDT ({amount_krw:,} KRW) 출금을 요청했습니다.",
            level=AlertLevel.WARNING,
            data={
                "출금 ID": withdrawal_id[:8] + "...",
                "금액 USDT": f"{amount_usdt:,.2f}",
                "금액 KRW": f"{amount_krw:,}",
                "주소": to_address[:20] + "...",
            },
        )

    async def notify_multi_approval_required(
        self,
        withdrawal_id: str,
        amount_usdt: float,
        required_approvals: int,
        expires_at: datetime,
    ) -> bool:
        """다중 승인 필요 알림."""
        return await self.send_alert(
            title="다중 승인 필요",
            message=f"고액 출금({amount_usdt:,.2f} USDT)에 대해 {required_approvals}명의 승인이 필요합니다.",
            level=AlertLevel.WARNING,
            data={
                "출금 ID": withdrawal_id[:8] + "...",
                "필요 승인": f"{required_approvals}명",
                "만료": expires_at.strftime("%Y-%m-%d %H:%M UTC"),
            },
        )

    async def notify_wallet_low_balance(
        self,
        balance_usdt: float,
        threshold_usdt: float,
        pending_usdt: float,
    ) -> bool:
        """지갑 잔액 부족 알림."""
        available = balance_usdt - pending_usdt
        return await self.send_alert(
            title="지갑 잔액 부족 경고",
            message=f"Hot Wallet 잔액이 임계값 이하입니다. 충전이 필요합니다.",
            level=AlertLevel.CRITICAL,
            data={
                "총 잔액": f"{balance_usdt:,.2f} USDT",
                "대기 출금": f"{pending_usdt:,.2f} USDT",
                "사용 가능": f"{available:,.2f} USDT",
                "임계값": f"{threshold_usdt:,.2f} USDT",
            },
        )

    async def notify_withdrawal_completed(
        self,
        withdrawal_id: str,
        amount_usdt: float,
        tx_hash: str,
    ) -> bool:
        """출금 완료 알림."""
        return await self.send_alert(
            title="출금 완료",
            message=f"출금 {amount_usdt:,.2f} USDT가 블록체인에서 확인되었습니다.",
            level=AlertLevel.INFO,
            data={
                "출금 ID": withdrawal_id[:8] + "...",
                "TX Hash": tx_hash[:20] + "...",
            },
        )

    async def notify_withdrawal_failed(
        self,
        withdrawal_id: str,
        amount_usdt: float,
        error: str,
    ) -> bool:
        """출금 실패 알림."""
        return await self.send_alert(
            title="출금 실패",
            message=f"출금 {amount_usdt:,.2f} USDT 처리 중 오류가 발생했습니다.",
            level=AlertLevel.CRITICAL,
            data={
                "출금 ID": withdrawal_id[:8] + "...",
                "오류": error[:100],
            },
        )

    async def notify_system_error(
        self,
        error_type: str,
        message: str,
        details: Optional[str] = None,
    ) -> bool:
        """시스템 오류 알림."""
        data = {"오류 유형": error_type}
        if details:
            data["상세"] = details[:200]

        return await self.send_alert(
            title=f"시스템 오류: {error_type}",
            message=message,
            level=AlertLevel.CRITICAL,
            data=data,
        )

    async def notify_suspicious_activity(
        self,
        user_id: str,
        activity_type: str,
        details: str,
    ) -> bool:
        """의심 활동 알림."""
        return await self.send_alert(
            title="의심 활동 감지",
            message=f"사용자 {user_id[:8]}...에서 의심 활동이 감지되었습니다.",
            level=AlertLevel.WARNING,
            data={
                "사용자": user_id[:8] + "...",
                "유형": activity_type,
                "상세": details[:100],
            },
        )


# 싱글톤 인스턴스
_telegram_service: Optional[TelegramAlertService] = None


def get_telegram_service() -> TelegramAlertService:
    """Telegram 서비스 싱글톤 인스턴스."""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramAlertService()
    return _telegram_service
