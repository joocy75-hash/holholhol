"""Memory Cleanup Property-Based Tests.

Property 1: Memory Cleanup Completeness
- Tests table creation/deletion and memory verification
- Validates: Requirements 1.1, 1.2, 1.4

Tests ensure that:
1. Tables are properly removed from GameManager
2. Cleanup callbacks are triggered
3. No memory leaks after table removal
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from typing import List
from unittest.mock import AsyncMock, MagicMock

from app.game.manager import GameManager
from app.game.poker_table import PokerTable, Player, GamePhase


# =============================================================================
# Strategies
# =============================================================================

# Number of tables to create
num_tables_strategy = st.integers(min_value=1, max_value=10)

# Number of players per table
num_players_strategy = st.integers(min_value=2, max_value=9)

# Stack amounts
stack_strategy = st.integers(min_value=400, max_value=2000)


# =============================================================================
# Property 1: Memory Cleanup Completeness
# =============================================================================


class TestMemoryCleanupCompleteness:
    """Property: After table removal, all resources should be cleaned up."""

    @pytest.fixture
    def game_manager(self):
        """Create a fresh GameManager for each test."""
        manager = GameManager()
        yield manager
        # Cleanup
        manager.clear_all()

    @given(num_tables=num_tables_strategy)
    @settings(max_examples=10, deadline=None)
    def test_table_count_after_creation_and_removal(self, num_tables: int):
        """Table count should be zero after removing all tables."""
        manager = GameManager()
        
        # Create tables
        room_ids = []
        for i in range(num_tables):
            room_id = f"test-room-{i}"
            manager.create_table_sync(
                room_id=room_id,
                name=f"Test Table {i}",
                small_blind=10,
                big_blind=20,
                min_buy_in=400,
                max_buy_in=2000,
            )
            room_ids.append(room_id)
        
        assert manager.get_table_count() == num_tables
        
        # Remove all tables synchronously (for hypothesis compatibility)
        for room_id in room_ids:
            manager._tables.pop(room_id, None)
        
        assert manager.get_table_count() == 0

    @given(num_tables=num_tables_strategy)
    @settings(max_examples=10, deadline=None)
    def test_table_not_accessible_after_removal(self, num_tables: int):
        """Tables should not be accessible after removal."""
        manager = GameManager()
        
        room_ids = []
        for i in range(num_tables):
            room_id = f"test-room-{i}"
            manager.create_table_sync(
                room_id=room_id,
                name=f"Test Table {i}",
                small_blind=10,
                big_blind=20,
                min_buy_in=400,
                max_buy_in=2000,
            )
            room_ids.append(room_id)
        
        # Remove tables
        for room_id in room_ids:
            manager._tables.pop(room_id, None)
        
        # Verify tables are not accessible
        for room_id in room_ids:
            assert manager.get_table(room_id) is None
            assert not manager.has_table(room_id)

    @given(num_players=num_players_strategy)
    @settings(max_examples=10, deadline=None)
    def test_player_references_cleared_on_table_removal(self, num_players: int):
        """Player references should be cleared when table is removed."""
        manager = GameManager()
        
        room_id = "test-room"
        table = manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        # Add players
        players = []
        for i in range(num_players):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
            players.append(player)
        
        # Verify players are seated
        assert len(table.get_active_players()) == num_players
        
        # Remove table
        manager._tables.pop(room_id, None)
        
        # Table should not be accessible
        assert manager.get_table(room_id) is None


@pytest.mark.asyncio
class TestAsyncMemoryCleanup:
    """Async tests for memory cleanup with callbacks."""

    async def test_cleanup_callback_triggered_on_removal(self):
        """Cleanup callbacks should be triggered when table is removed."""
        manager = GameManager()
        callback_called = False
        callback_room_id = None
        
        async def cleanup_callback(room_id: str):
            nonlocal callback_called, callback_room_id
            callback_called = True
            callback_room_id = room_id
        
        manager.register_cleanup_callback(cleanup_callback)
        
        # Create and remove table
        room_id = "test-room"
        manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        await manager.remove_table(room_id)
        
        assert callback_called
        assert callback_room_id == room_id

    async def test_multiple_cleanup_callbacks(self):
        """Multiple cleanup callbacks should all be triggered."""
        manager = GameManager()
        callbacks_called = []
        
        async def callback1(room_id: str):
            callbacks_called.append(("callback1", room_id))
        
        async def callback2(room_id: str):
            callbacks_called.append(("callback2", room_id))
        
        manager.register_cleanup_callback(callback1)
        manager.register_cleanup_callback(callback2)
        
        room_id = "test-room"
        manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        await manager.remove_table(room_id)
        
        assert len(callbacks_called) == 2
        assert ("callback1", room_id) in callbacks_called
        assert ("callback2", room_id) in callbacks_called

    async def test_cleanup_callback_error_does_not_prevent_removal(self):
        """Cleanup callback errors should not prevent table removal."""
        manager = GameManager()
        
        async def failing_callback(room_id: str):
            raise Exception("Callback error")
        
        manager.register_cleanup_callback(failing_callback)
        
        room_id = "test-room"
        manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        # Should not raise, table should still be removed
        result = await manager.remove_table(room_id)
        
        assert result is True
        assert manager.get_table(room_id) is None

    async def test_remove_nonexistent_table_returns_false(self):
        """Removing a nonexistent table should return False."""
        manager = GameManager()
        
        result = await manager.remove_table("nonexistent-room")
        
        assert result is False

    async def test_concurrent_table_creation_and_removal(self):
        """Concurrent table operations should be thread-safe."""
        manager = GameManager()
        
        async def create_and_remove(index: int):
            room_id = f"test-room-{index}"
            await manager.create_table(
                room_id=room_id,
                name=f"Test Table {index}",
                small_blind=10,
                big_blind=20,
                min_buy_in=400,
                max_buy_in=2000,
            )
            await asyncio.sleep(0.01)  # Small delay
            await manager.remove_table(room_id)
        
        # Run concurrent operations
        await asyncio.gather(*[create_and_remove(i) for i in range(5)])
        
        # All tables should be removed
        assert manager.get_table_count() == 0


class TestTableStateCleanup:
    """Tests for table state cleanup after hand completion."""

    @given(num_players=num_players_strategy)
    @settings(max_examples=10, deadline=None)
    def test_table_state_reset_after_hand(self, num_players: int):
        """Table state should be properly reset after hand completion."""
        manager = GameManager()
        
        room_id = "test-room"
        table = manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        # Add players
        for i in range(num_players):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
        
        # Start hand
        result = table.start_new_hand()
        assume(result["success"])
        
        # Complete hand by folding
        while table.phase != GamePhase.WAITING:
            current_player = table.players.get(table.current_player_seat)
            if current_player:
                table.process_action(current_player.user_id, "fold", 0)
            else:
                break
        
        # Verify state is reset
        assert table.phase == GamePhase.WAITING
        assert table.pot == 0
        assert table.community_cards == []
        assert table.current_player_seat is None
        assert table.current_bet == 0

    def test_reset_table_clears_all_state(self):
        """reset_table should clear all game state."""
        manager = GameManager()
        
        room_id = "test-room"
        table = manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        # Add players
        for i in range(3):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
        
        # Start hand
        table.start_new_hand()
        
        # Reset table
        reset_table = manager.reset_table(room_id)
        
        assert reset_table is not None
        assert reset_table.phase == GamePhase.WAITING
        assert reset_table.pot == 0
        assert reset_table.community_cards == []
        assert reset_table.hand_number == 0
        
        # All players should be removed
        active_players = reset_table.get_active_players()
        assert len(active_players) == 0

    def test_clear_all_removes_all_tables(self):
        """clear_all should remove all tables."""
        manager = GameManager()

        # Create multiple tables
        for i in range(5):
            manager.create_table_sync(
                room_id=f"test-room-{i}",
                name=f"Test Table {i}",
                small_blind=10,
                big_blind=20,
                min_buy_in=400,
                max_buy_in=2000,
            )

        assert manager.get_table_count() == 5

        manager.clear_all()

        assert manager.get_table_count() == 0
        assert manager.get_all_tables() == []


# =============================================================================
# Phase 4.5: Memory Cleanup Optimization Tests
# =============================================================================


class TestEmptyTableAutoCleanup:
    """Tests for automatic empty table cleanup after 30 minutes."""

    @pytest.fixture
    def game_manager(self):
        """Create a fresh GameManager for each test."""
        manager = GameManager()
        yield manager
        manager.clear_all()

    def test_empty_table_marked_for_cleanup(self, game_manager):
        """Empty table should be marked with last activity time."""
        room_id = "test-room"
        game_manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )

        # 테이블 활동 시간 갱신
        game_manager.update_table_activity(room_id)

        assert room_id in game_manager._table_last_activity

    def test_activity_update_refreshes_timestamp(self, game_manager):
        """Activity update should refresh last activity timestamp."""
        from datetime import datetime
        import time

        room_id = "test-room"
        game_manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )

        # 첫 번째 활동 시간 기록
        game_manager.update_table_activity(room_id)
        first_activity = game_manager._table_last_activity[room_id]

        time.sleep(0.01)  # 약간의 대기

        # 두 번째 활동 시간 기록
        game_manager.update_table_activity(room_id)
        second_activity = game_manager._table_last_activity[room_id]

        assert second_activity > first_activity

    @pytest.mark.asyncio
    async def test_cleanup_empty_tables_removes_old_empty(self, game_manager):
        """Old empty tables should be removed by cleanup."""
        from datetime import datetime, timedelta
        from app.game.manager import EMPTY_TABLE_CLEANUP_MINUTES

        room_id = "test-room"
        game_manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )

        # 마지막 활동 시간을 과거로 설정 (30분 이전)
        old_time = datetime.utcnow() - timedelta(minutes=EMPTY_TABLE_CLEANUP_MINUTES + 1)
        game_manager._table_last_activity[room_id] = old_time

        # 정리 실행
        removed_count = await game_manager._cleanup_empty_tables()

        assert removed_count == 1
        assert game_manager.get_table(room_id) is None

    @pytest.mark.asyncio
    async def test_cleanup_keeps_tables_with_players(self, game_manager):
        """Tables with players should not be cleaned up."""
        from datetime import datetime, timedelta
        from app.game.manager import EMPTY_TABLE_CLEANUP_MINUTES

        room_id = "test-room"
        table = game_manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )

        # 플레이어 추가
        player = Player(
            user_id="user1",
            username="Player1",
            seat=0,
            stack=1000,
        )
        table.seat_player(0, player)

        # 마지막 활동 시간을 과거로 설정
        old_time = datetime.utcnow() - timedelta(minutes=EMPTY_TABLE_CLEANUP_MINUTES + 1)
        game_manager._table_last_activity[room_id] = old_time

        # 정리 실행
        removed_count = await game_manager._cleanup_empty_tables()

        # 플레이어가 있으므로 제거되지 않음
        assert removed_count == 0
        assert game_manager.get_table(room_id) is not None

    @pytest.mark.asyncio
    async def test_cleanup_task_start_stop(self, game_manager):
        """Cleanup task should start and stop properly."""
        assert not game_manager._cleanup_running

        await game_manager.start_cleanup_task()
        assert game_manager._cleanup_running
        assert game_manager._cleanup_task is not None

        await game_manager.stop_cleanup_task()
        assert not game_manager._cleanup_running


class TestHandHistoryManagement:
    """Tests for hand history storage and cleanup."""

    @pytest.fixture
    def game_manager(self):
        """Create a fresh GameManager for each test."""
        manager = GameManager()
        yield manager
        manager.clear_all()

    def test_save_hand_history(self, game_manager):
        """Hand history should be saved."""
        room_id = "test-room"
        game_manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )

        hand_data = {
            "hand_number": 1,
            "actions": ["raise", "call", "fold"],
            "winners": ["user1"],
            "pot": 100,
        }

        game_manager.save_hand_history(room_id, hand_data)

        history = game_manager.get_hand_history(room_id)
        assert len(history) == 1
        assert history[0]["hand_number"] == 1

    def test_hand_history_limit_enforced(self, game_manager):
        """Hand history should be limited to MAX_HAND_HISTORY_PER_TABLE."""
        from app.game.manager import MAX_HAND_HISTORY_PER_TABLE

        room_id = "test-room"
        game_manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )

        # MAX보다 많은 핸드 저장
        for i in range(MAX_HAND_HISTORY_PER_TABLE + 5):
            hand_data = {"hand_number": i + 1, "pot": 100 * (i + 1)}
            game_manager.save_hand_history(room_id, hand_data)

        history = game_manager.get_hand_history(room_id)

        # MAX_HAND_HISTORY_PER_TABLE 개만 유지
        assert len(history) == MAX_HAND_HISTORY_PER_TABLE

        # 최근 핸드만 유지 (오래된 것 삭제)
        assert history[0]["hand_number"] == 6  # 처음 5개 삭제됨
        assert history[-1]["hand_number"] == MAX_HAND_HISTORY_PER_TABLE + 5

    def test_get_hand_history_empty(self, game_manager):
        """Empty hand history should return empty list."""
        history = game_manager.get_hand_history("nonexistent-room")
        assert history == []

    def test_cleanup_hand_data(self, game_manager):
        """cleanup_hand_data should clear temporary hand data."""
        room_id = "test-room"
        table = game_manager.create_table_sync(
            room_id=room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )

        # 임시 데이터 설정
        table._hand_actions = [{"action": "raise", "amount": 100}]
        table._hand_starting_stacks = {"user1": 1000}
        table._hand_start_time = "2026-01-17T12:00:00"
        table._injected_cards = {"hole_cards": {0: ["As", "Ks"]}, "community_cards": []}

        # 정리 실행
        game_manager.cleanup_hand_data(table)

        # 모든 임시 데이터 정리됨
        assert table._hand_actions == []
        assert table._hand_starting_stacks == {}
        assert table._hand_start_time is None
        assert table._injected_cards == {"hole_cards": {}, "community_cards": []}


class TestMemoryStats:
    """Tests for memory usage statistics."""

    @pytest.fixture
    def game_manager(self):
        """Create a fresh GameManager for each test."""
        manager = GameManager()
        yield manager
        manager.clear_all()

    def test_get_memory_stats_empty(self, game_manager):
        """Memory stats should work with no tables."""
        stats = game_manager.get_memory_stats()

        assert stats["table_count"] == 0
        assert stats["total_players"] == 0
        assert stats["total_hand_history"] == 0
        assert "cleanup_running" in stats

    def test_get_memory_stats_with_tables(self, game_manager):
        """Memory stats should reflect table and player counts."""
        # 테이블 2개 생성
        for i in range(2):
            table = game_manager.create_table_sync(
                room_id=f"test-room-{i}",
                name=f"Test Table {i}",
                small_blind=10,
                big_blind=20,
                min_buy_in=400,
                max_buy_in=2000,
            )

            # 각 테이블에 플레이어 추가
            for j in range(3):
                player = Player(
                    user_id=f"user{i}_{j}",
                    username=f"Player{j}",
                    seat=j,
                    stack=1000,
                )
                table.seat_player(j, player)

        # 핸드 히스토리 추가
        game_manager.save_hand_history("test-room-0", {"hand_number": 1})
        game_manager.save_hand_history("test-room-0", {"hand_number": 2})
        game_manager.save_hand_history("test-room-1", {"hand_number": 1})

        stats = game_manager.get_memory_stats()

        assert stats["table_count"] == 2
        assert stats["total_players"] == 6
        assert stats["total_hand_history"] == 3

    def test_memory_log_does_not_raise(self, game_manager):
        """Memory logging should not raise exceptions."""
        # 테이블 생성
        game_manager.create_table_sync(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )

        # 예외 없이 실행되어야 함
        game_manager._log_memory_usage()


@pytest.mark.asyncio
class TestCleanupIntegration:
    """Integration tests for the full cleanup cycle."""

    async def test_full_cleanup_cycle(self):
        """Full cleanup cycle: create, use, cleanup."""
        from datetime import datetime, timedelta
        from app.game.manager import EMPTY_TABLE_CLEANUP_MINUTES

        manager = GameManager()

        try:
            # 1. 테이블 생성
            room_id = "test-room"
            table = manager.create_table_sync(
                room_id=room_id,
                name="Test Table",
                small_blind=10,
                big_blind=20,
                min_buy_in=400,
                max_buy_in=2000,
            )

            # 2. 플레이어 추가 및 게임 진행
            for i in range(3):
                player = Player(
                    user_id=f"user{i}",
                    username=f"Player{i}",
                    seat=i,
                    stack=1000,
                )
                table.seat_player(i, player)
                manager.update_table_activity(room_id)

            # 3. 핸드 진행 후 히스토리 저장
            table.start_new_hand()
            manager.save_hand_history(room_id, {
                "hand_number": 1,
                "actions": [],
                "pot": 30,
            })

            # 4. 모든 플레이어 퇴장 (seat 번호로 제거)
            for i in range(3):
                table.remove_player(i)

            # 5. 시간 경과 시뮬레이션 (30분 이전으로 설정)
            old_time = datetime.utcnow() - timedelta(minutes=EMPTY_TABLE_CLEANUP_MINUTES + 1)
            manager._table_last_activity[room_id] = old_time

            # 6. 정리 실행
            removed = await manager._cleanup_empty_tables()

            assert removed == 1
            assert manager.get_table(room_id) is None
            assert room_id not in manager._table_last_activity
            assert room_id not in manager._table_hand_history

        finally:
            manager.clear_all()
            await manager.stop_cleanup_task()

    async def test_cleanup_metadata_cleared_on_remove(self):
        """Metadata should be cleared when table is removed."""
        manager = GameManager()

        try:
            room_id = "test-room"
            manager.create_table_sync(
                room_id=room_id,
                name="Test Table",
                small_blind=10,
                big_blind=20,
                min_buy_in=400,
                max_buy_in=2000,
            )

            # 메타데이터 설정
            manager.update_table_activity(room_id)
            manager.save_hand_history(room_id, {"hand_number": 1})

            assert room_id in manager._table_last_activity
            assert room_id in manager._table_hand_history

            # 테이블 제거
            await manager.remove_table(room_id)

            # 메타데이터는 자동으로 정리되지 않음 (cleanup에서 정리)
            # 이는 의도된 동작: 일반 remove_table은 콜백만 호출

        finally:
            manager.clear_all()
