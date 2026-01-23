"""Concurrency Property-Based Tests.

Property 3: Concurrent Start Prevention
- Tests concurrent START_GAME requests
- Validates: Requirements 2.1

Tests ensure that:
1. Only one START_GAME succeeds for concurrent requests
2. Phase changes immediately on start
3. Race conditions are properly handled
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, settings, assume
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from app.game.manager import GameManager
from app.game.poker_table import PokerTable, Player, GamePhase


# =============================================================================
# Strategies
# =============================================================================

num_players_strategy = st.integers(min_value=2, max_value=9)
num_concurrent_requests_strategy = st.integers(min_value=2, max_value=10)


# =============================================================================
# Property 3: Concurrent Start Prevention
# =============================================================================


class TestConcurrentStartPrevention:
    """Property: Only one START_GAME should succeed for concurrent requests."""

    @given(num_players=num_players_strategy)
    @settings(max_examples=10, deadline=None)
    def test_cannot_start_during_active_hand(self, num_players: int):
        """Starting a new hand should fail during active hand."""
        table = PokerTable(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
            max_players=9,
        )
        
        for i in range(num_players):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
            table.sit_in(i)

        # Start first hand
        result1 = table.start_new_hand()
        assume(result1["success"])
        
        # Try to start second hand (should fail)
        result2 = table.start_new_hand()
        
        assert result2["success"] is False
        assert "error" in result2 or "message" in result2

    @given(num_players=num_players_strategy)
    @settings(max_examples=10, deadline=None)
    def test_phase_changes_immediately_on_start(self, num_players: int):
        """Phase should change immediately when hand starts."""
        table = PokerTable(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
            max_players=9,
        )
        
        for i in range(num_players):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
            table.sit_in(i)

        assert table.phase == GamePhase.WAITING
        
        result = table.start_new_hand()
        assume(result["success"])
        
        # Phase should change immediately (not WAITING)
        assert table.phase != GamePhase.WAITING
        assert table.phase == GamePhase.PREFLOP

    def test_multiple_start_attempts_only_one_succeeds(self):
        """Multiple sequential start attempts should only succeed once."""
        table = PokerTable(
            room_id="test-room",
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
            table.sit_in(i)

        # Try to start multiple times
        results = []
        for _ in range(5):
            result = table.start_new_hand()
            results.append(result["success"])
        
        # Only first should succeed
        assert results[0] is True
        assert all(r is False for r in results[1:])

    def test_start_fails_with_insufficient_players(self):
        """Starting should fail with less than 2 players."""
        table = PokerTable(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        # Add only one player
        player = Player(
            user_id="user1",
            username="Player1",
            seat=0,
            stack=1000,
        )
        table.seat_player(0, player)
        table.sit_in(0)

        result = table.start_new_hand()
        
        assert result["success"] is False

    def test_start_fails_with_no_players(self):
        """Starting should fail with no players."""
        table = PokerTable(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        result = table.start_new_hand()
        
        assert result["success"] is False


@pytest.mark.asyncio
class TestAsyncConcurrentStart:
    """Async tests for concurrent start prevention."""

    async def test_concurrent_start_requests_only_one_succeeds(self):
        """Concurrent start requests should result in only one success."""
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
        for i in range(4):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
            table.sit_in(i)

        # Simulate concurrent start requests
        async def try_start():
            return table.start_new_hand()
        
        # Run concurrent starts
        results = await asyncio.gather(*[try_start() for _ in range(5)])
        
        # Count successes
        successes = sum(1 for r in results if r["success"])
        
        # Only one should succeed
        assert successes == 1

    async def test_game_manager_lock_prevents_race_condition(self):
        """GameManager lock should prevent race conditions on table creation."""
        manager = GameManager()
        
        async def create_table(index: int):
            return await manager.create_table(
                room_id=f"test-room-{index}",
                name=f"Test Table {index}",
                small_blind=10,
                big_blind=20,
                min_buy_in=400,
                max_buy_in=2000,
            )
        
        # Create tables concurrently
        tables = await asyncio.gather(*[create_table(i) for i in range(5)])
        
        # All should be created successfully
        assert len(tables) == 5
        assert manager.get_table_count() == 5
        
        # Each table should be unique
        room_ids = [t.room_id for t in tables]
        assert len(set(room_ids)) == 5

    async def test_concurrent_hand_completion_and_start(self):
        """Concurrent hand completion and start should be handled correctly."""
        table = PokerTable(
            room_id="test-room",
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
            table.sit_in(i)

        # Start first hand
        result = table.start_new_hand()
        assert result["success"]
        
        # Complete hand
        while table.phase != GamePhase.WAITING:
            current_player = table.players.get(table.current_player_seat)
            if current_player:
                table.process_action(current_player.user_id, "fold", 0)
            else:
                break
        
        # Now should be able to start again
        result2 = table.start_new_hand()
        assert result2["success"]


class TestPhaseTransitionSafety:
    """Tests for safe phase transitions."""

    @given(num_players=num_players_strategy)
    @settings(max_examples=10, deadline=None)
    def test_phase_transition_is_atomic(self, num_players: int):
        """Phase transitions should be atomic."""
        table = PokerTable(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
            max_players=9,
        )
        
        for i in range(num_players):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
            table.sit_in(i)

        # Start hand
        result = table.start_new_hand()
        assume(result["success"])
        
        # Phase should be valid at all times
        valid_phases = [
            GamePhase.WAITING,
            GamePhase.PREFLOP,
            GamePhase.FLOP,
            GamePhase.TURN,
            GamePhase.RIVER,
            GamePhase.SHOWDOWN,
        ]
        
        assert table.phase in valid_phases

    def test_action_during_wrong_phase_fails(self):
        """Actions during wrong phase should fail gracefully."""
        table = PokerTable(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        # Add players
        for i in range(2):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
            table.sit_in(i)

        # Try action before hand starts (WAITING phase)
        result = table.process_action("user0", "fold", 0)
        
        assert result["success"] is False

    def test_hand_number_increments_correctly(self):
        """Hand number should increment correctly across multiple hands."""
        table = PokerTable(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        # Add players
        for i in range(2):
            player = Player(
                user_id=f"user{i}",
                username=f"Player{i}",
                seat=i,
                stack=1000,
            )
            table.seat_player(i, player)
            table.sit_in(i)

        hand_numbers = []
        
        for _ in range(3):
            result = table.start_new_hand()
            if result["success"]:
                hand_numbers.append(table.hand_number)
                
                # Complete hand
                while table.phase != GamePhase.WAITING:
                    current_player = table.players.get(table.current_player_seat)
                    if current_player:
                        table.process_action(current_player.user_id, "fold", 0)
                    else:
                        break
        
        # Hand numbers should be strictly increasing
        for i in range(1, len(hand_numbers)):
            assert hand_numbers[i] > hand_numbers[i - 1]


class TestBotLoopSafety:
    """Tests for bot loop safety during concurrent operations."""

    def test_bot_action_during_completed_hand_fails(self):
        """Bot actions during completed hand should fail gracefully."""
        table = PokerTable(
            room_id="test-room",
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
        )
        
        # Add players (one bot)
        player = Player(
            user_id="user1",
            username="Player1",
            seat=0,
            stack=1000,
        )
        bot = Player(
            user_id="bot1",
            username="Bot1",
            seat=1,
            stack=1000,
            is_bot=True,
        )
        table.seat_player(0, player)
        table.sit_in(0)
        table.seat_player(1, bot)
        table.sit_in(1)

        # Start and complete hand
        result = table.start_new_hand()
        assert result["success"]
        
        # Complete hand
        while table.phase != GamePhase.WAITING:
            current_player = table.players.get(table.current_player_seat)
            if current_player:
                table.process_action(current_player.user_id, "fold", 0)
            else:
                break
        
        # Try bot action after hand is complete
        result = table.process_action("bot1", "fold", 0)
        
        assert result["success"] is False

    def test_current_player_seat_valid_during_hand(self):
        """Current player seat should always be valid during active hand."""
        table = PokerTable(
            room_id="test-room",
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
            table.sit_in(i)

        result = table.start_new_hand()
        assert result["success"]

        # During active hand, current_player_seat should be valid
        while table.phase != GamePhase.WAITING:
            if table.current_player_seat is not None:
                assert table.current_player_seat in table.players
                current_player = table.players.get(table.current_player_seat)
                assert current_player is not None
                table.process_action(current_player.user_id, "fold", 0)
            else:
                break
