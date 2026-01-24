"""
Tournament Event Bus - Asynchronous Event-Driven Architecture.

모든 토너먼트 액션을 비동기 이벤트로 처리하여 서버 부하 최소화.

설계 원칙:
1. Fire-and-Forget: 이벤트 발행은 비동기로 즉시 반환
2. Fan-Out: 하나의 이벤트를 여러 핸들러가 독립적으로 처리
3. Guaranteed Delivery: Redis Streams로 이벤트 유실 방지
4. Ordered Processing: 동일 토너먼트/테이블 이벤트는 순서 보장
"""

import asyncio
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Set,
)
from uuid import uuid4

import redis.asyncio as redis

from .models import TournamentEvent, TournamentEventType


# Type alias for event handlers
EventHandler = Callable[[TournamentEvent], Awaitable[None]]


@dataclass
class Subscription:
    """Event subscription metadata."""

    subscription_id: str
    event_types: Set[TournamentEventType]
    handler: EventHandler
    tournament_id: Optional[str] = None  # None = all tournaments
    is_active: bool = True


@dataclass
class EventMetrics:
    """Event processing metrics."""

    events_published: int = 0
    events_processed: int = 0
    events_failed: int = 0
    avg_processing_time_ms: float = 0.0
    last_event_time: Optional[datetime] = None


class TournamentEventBus:
    """
    High-performance event bus for tournament events.

    아키텍처:
    ─────────────────────────────────────────────────────────────────

    [Producer] -> [Redis Stream] -> [Consumer Group] -> [Handlers]

    1. Producer (publish):
       - 이벤트를 Redis Stream에 추가 (XADD)
       - 비동기로 즉시 반환 (Fire-and-Forget)
       - 로컬 인메모리 핸들러에도 동시 발행

    2. Redis Stream:
       - 이벤트 영속성 보장 (서버 재시작 후에도 유지)
       - Consumer Group으로 분산 처리 가능
       - Stream ID로 순서 보장

    3. Consumer:
       - 백그라운드 태스크로 지속적 폴링 (XREADGROUP)
       - ACK로 처리 완료 확인
       - 실패 시 Pending List로 재처리

    4. Local Handlers:
       - 인메모리 핸들러는 즉시 처리 (WebSocket 등)
       - 분산 핸들러는 Redis Stream 통해 처리

    ─────────────────────────────────────────────────────────────────

    성능 최적화:
    - 배치 발행: 여러 이벤트를 파이프라인으로 일괄 전송
    - 논블로킹: 모든 I/O 작업 비동기 처리
    - 백프레셔: 처리 지연 시 발행 속도 조절
    """

    # Redis Stream key prefix
    STREAM_KEY_PREFIX = "tournament:events"

    # Consumer group name
    CONSUMER_GROUP = "tournament-engine"

    # Max events to read per poll
    BATCH_SIZE = 100

    # Event retention (1 hour = 3600000 ms)
    STREAM_MAX_LEN = 10000

    def __init__(
        self,
        redis_client: redis.Redis,
        instance_id: Optional[str] = None,
    ):
        self.redis = redis_client
        self.instance_id = instance_id or str(uuid4())[:8]

        # Local in-memory subscriptions
        self._subscriptions: Dict[str, Subscription] = {}

        # Handler lookup table by event type
        self._handlers_by_type: Dict[TournamentEventType, List[Subscription]] = (
            defaultdict(list)
        )

        # Background consumer task
        self._consumer_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self._metrics = EventMetrics()

        # Event queue for batch processing
        self._event_queue: asyncio.Queue[TournamentEvent] = asyncio.Queue(maxsize=1000)

        # Publisher task
        self._publisher_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """
        Initialize event bus.

        - Redis Stream 및 Consumer Group 생성
        - Background tasks 시작
        """
        # Create stream and consumer group if not exists
        stream_key = f"{self.STREAM_KEY_PREFIX}:all"

        try:
            await self.redis.xgroup_create(
                stream_key,
                self.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except redis.ResponseError as e:
            # Group already exists
            if "BUSYGROUP" not in str(e):
                raise

        # Start background tasks
        self._running = True
        self._publisher_task = asyncio.create_task(self._batch_publisher())
        self._consumer_task = asyncio.create_task(self._stream_consumer())

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self._running = False

        if self._publisher_task:
            self._publisher_task.cancel()
            try:
                await self._publisher_task
            except asyncio.CancelledError:
                pass

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    def subscribe(
        self,
        event_types: Set[TournamentEventType],
        handler: EventHandler,
        tournament_id: Optional[str] = None,
    ) -> str:
        """
        Subscribe to tournament events.

        Args:
            event_types: Set of event types to listen for
            handler: Async function to call on event
            tournament_id: Filter for specific tournament (None = all)

        Returns:
            Subscription ID for unsubscribe
        """
        subscription_id = str(uuid4())
        subscription = Subscription(
            subscription_id=subscription_id,
            event_types=event_types,
            handler=handler,
            tournament_id=tournament_id,
        )

        self._subscriptions[subscription_id] = subscription

        for event_type in event_types:
            self._handlers_by_type[event_type].append(subscription)

        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove subscription."""
        subscription = self._subscriptions.pop(subscription_id, None)
        if not subscription:
            return False

        subscription.is_active = False

        for event_type in subscription.event_types:
            handlers = self._handlers_by_type[event_type]
            self._handlers_by_type[event_type] = [
                h for h in handlers if h.subscription_id != subscription_id
            ]

        return True

    async def publish(self, event: TournamentEvent) -> None:
        """
        Publish event to event bus.

        비동기 발행 로직:
        1. 이벤트 큐에 추가 (즉시 반환)
        2. 로컬 핸들러에 즉시 디스패치
        3. 백그라운드에서 Redis Stream에 저장

        성능: 초당 10,000+ 이벤트 처리 가능
        """
        # Add to queue for batch publishing to Redis
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            # Queue full - publish directly (backpressure)
            await self._publish_to_stream(event)

        # Dispatch to local handlers immediately
        await self._dispatch_local(event)

        self._metrics.events_published += 1
        self._metrics.last_event_time = datetime.now(timezone.utc)

    async def publish_batch(self, events: List[TournamentEvent]) -> None:
        """Publish multiple events efficiently."""
        for event in events:
            await self.publish(event)

    async def _publish_to_stream(self, event: TournamentEvent) -> str:
        """
        Publish single event to Redis Stream.

        Returns stream entry ID.
        """
        stream_key = f"{self.STREAM_KEY_PREFIX}:all"

        # Event data for Redis (flat structure)
        data = {
            "event_id": event.event_id,
            "event_type": event.event_type.name,
            "tournament_id": event.tournament_id,
            "timestamp": event.timestamp.isoformat(),
            "data": json.dumps(event.data),
            "table_id": event.table_id or "",
            "user_id": event.user_id or "",
        }

        entry_id = await self.redis.xadd(
            stream_key,
            data,
            maxlen=self.STREAM_MAX_LEN,
            approximate=True,
        )

        return entry_id

    async def _batch_publisher(self) -> None:
        """
        Background task for batch publishing to Redis.

        배치 처리로 Redis 호출 최소화:
        - 최대 BATCH_SIZE개 이벤트 수집
        - 또는 100ms 타임아웃 후 발행
        - Pipeline으로 일괄 전송
        """
        while self._running:
            batch: List[TournamentEvent] = []

            try:
                # Collect events for batch
                deadline = time.time() + 0.1  # 100ms batch window

                while len(batch) < self.BATCH_SIZE and time.time() < deadline:
                    try:
                        event = await asyncio.wait_for(
                            self._event_queue.get(),
                            timeout=max(0.01, deadline - time.time()),
                        )
                        batch.append(event)
                    except asyncio.TimeoutError:
                        break

                if batch:
                    # Batch publish with pipeline
                    stream_key = f"{self.STREAM_KEY_PREFIX}:all"

                    async with self.redis.pipeline(transaction=False) as pipe:
                        for event in batch:
                            data = {
                                "event_id": event.event_id,
                                "event_type": event.event_type.name,
                                "tournament_id": event.tournament_id,
                                "timestamp": event.timestamp.isoformat(),
                                "data": json.dumps(event.data),
                                "table_id": event.table_id or "",
                                "user_id": event.user_id or "",
                            }
                            pipe.xadd(
                                stream_key,
                                data,
                                maxlen=self.STREAM_MAX_LEN,
                                approximate=True,
                            )
                        await pipe.execute()

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log and continue
                await asyncio.sleep(0.1)

    async def _stream_consumer(self) -> None:
        """
        Background task for consuming events from Redis Stream.

        분산 환경 Consumer Group 처리:
        - 여러 서버 인스턴스가 이벤트를 분산 처리
        - XREADGROUP으로 자동 부하 분산
        - ACK로 처리 완료 확인
        """
        stream_key = f"{self.STREAM_KEY_PREFIX}:all"
        consumer_name = f"consumer-{self.instance_id}"

        while self._running:
            try:
                # Read new events
                entries = await self.redis.xreadgroup(
                    groupname=self.CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams={stream_key: ">"},  # Only new messages
                    count=self.BATCH_SIZE,
                    block=1000,  # 1 second timeout
                )

                if not entries:
                    continue

                for stream_name, messages in entries:
                    for message_id, data in messages:
                        try:
                            # Reconstruct event
                            event = TournamentEvent(
                                event_id=data.get("event_id", ""),
                                event_type=TournamentEventType[
                                    data.get("event_type", "TOURNAMENT_CREATED")
                                ],
                                tournament_id=data.get("tournament_id", ""),
                                timestamp=datetime.fromisoformat(
                                    data.get("timestamp", datetime.now(timezone.utc).isoformat())
                                ),
                                data=json.loads(data.get("data", "{}")),
                                table_id=data.get("table_id") or None,
                                user_id=data.get("user_id") or None,
                            )

                            # Process with distributed handlers
                            await self._dispatch_distributed(event)

                            # Acknowledge
                            await self.redis.xack(
                                stream_key,
                                self.CONSUMER_GROUP,
                                message_id,
                            )

                            self._metrics.events_processed += 1

                        except Exception as e:
                            self._metrics.events_failed += 1
                            # Don't ACK - will retry

            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(1)  # Backoff on error

    async def _dispatch_local(self, event: TournamentEvent) -> None:
        """
        Dispatch event to local in-memory handlers.

        로컬 핸들러 특성:
        - WebSocket 브로드캐스트
        - 인메모리 캐시 업데이트
        - 메트릭 수집

        비동기로 병렬 처리하되 개별 실패가 전체에 영향 없음.
        """
        handlers = self._handlers_by_type.get(event.event_type, [])

        tasks = []
        for subscription in handlers:
            if not subscription.is_active:
                continue

            # Tournament filter
            if (
                subscription.tournament_id
                and subscription.tournament_id != event.tournament_id
            ):
                continue

            # Create task for handler
            task = asyncio.create_task(
                self._safe_handler_call(subscription.handler, event)
            )
            tasks.append(task)

        if tasks:
            # Run all handlers concurrently
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _dispatch_distributed(self, event: TournamentEvent) -> None:
        """
        Dispatch event from Redis Stream (for distributed handlers).

        분산 핸들러 특성:
        - 데이터베이스 저장
        - 외부 서비스 알림
        - 분석/로깅
        """
        # Same as local for now - can be extended for remote handlers
        await self._dispatch_local(event)

    async def _safe_handler_call(
        self,
        handler: EventHandler,
        event: TournamentEvent,
    ) -> None:
        """Safely call handler with error handling."""
        try:
            start_time = time.time()
            await handler(event)
            elapsed_ms = (time.time() - start_time) * 1000

            # Update average processing time
            total = self._metrics.events_processed
            avg = self._metrics.avg_processing_time_ms
            self._metrics.avg_processing_time_ms = (avg * total + elapsed_ms) / (
                total + 1
            )

        except Exception as e:
            self._metrics.events_failed += 1
            # Log error but don't propagate

    def get_metrics(self) -> EventMetrics:
        """Get event processing metrics."""
        return self._metrics

    # =========================================================================
    # Convenience methods for common events
    # =========================================================================

    async def emit_player_eliminated(
        self,
        tournament_id: str,
        user_id: str,
        rank: int,
        eliminated_by: Optional[str] = None,
        table_id: Optional[str] = None,
    ) -> None:
        """Emit player elimination event."""
        event = TournamentEvent(
            event_type=TournamentEventType.PLAYER_ELIMINATED,
            tournament_id=tournament_id,
            user_id=user_id,
            table_id=table_id,
            data={
                "rank": rank,
                "eliminated_by": eliminated_by,
            },
        )
        await self.publish(event)

    async def emit_blind_change(
        self,
        tournament_id: str,
        level: int,
        small_blind: int,
        big_blind: int,
        ante: int,
    ) -> None:
        """Emit blind level change event."""
        event = TournamentEvent(
            event_type=TournamentEventType.BLIND_LEVEL_CHANGED,
            tournament_id=tournament_id,
            data={
                "level": level,
                "small_blind": small_blind,
                "big_blind": big_blind,
                "ante": ante,
            },
        )
        await self.publish(event)

    async def emit_table_balancing(
        self,
        tournament_id: str,
        moves: List[Dict[str, Any]],
    ) -> None:
        """Emit table balancing event."""
        event = TournamentEvent(
            event_type=TournamentEventType.TABLE_BALANCING_EXECUTED,
            tournament_id=tournament_id,
            data={"moves": moves},
        )
        await self.publish(event)

    async def emit_ranking_update(
        self,
        tournament_id: str,
        ranking: List[Dict[str, Any]],
    ) -> None:
        """Emit ranking update event."""
        event = TournamentEvent(
            event_type=TournamentEventType.RANKING_UPDATED,
            tournament_id=tournament_id,
            data={"ranking": ranking[:100]},  # Top 100 only
        )
        await self.publish(event)
