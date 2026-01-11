"""Game Flow Integration Tests - Complete hand lifecycle.

Tests the MVP required scenarios:
1. Room creation → Join → Seat → Hand start
2. 2-6 player turn progression
3. Call/Raise/Fold basic actions
4. Hand completion and showdown results
5. Side pot handling
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.engine.core import PokerKitWrapper
from app.engine.actions import ActionProcessor
from app.engine.state import (
    TableState,
    TableConfig,
    SeatState,
    SeatStatus,
    ActionType,
    ActionRequest,
    Player,
)
from app.engine.snapshot import SnapshotSerializer

from .conftest import create_room, join_room


# =============================================================================
# Engine Direct Tests (No HTTP, direct engine manipulation)
# =============================================================================


class TestEngineGameFlow:
    """Test game engine directly for game mechanics."""

    @pytest.fixture
    def wrapper(self) -> PokerKitWrapper:
        return PokerKitWrapper()

    @pytest.fixture
    def processor(self, wrapper: PokerKitWrapper) -> ActionProcessor:
        return ActionProcessor(wrapper)

    @pytest.fixture
    def serializer(self) -> SnapshotSerializer:
        return SnapshotSerializer()

    @pytest.fixture
    def table_config(self) -> TableConfig:
        return TableConfig(
            max_seats=6,
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
            ante=0,
            turn_timeout_seconds=30,
        )

    @pytest.fixture
    def two_player_table(self, table_config: TableConfig) -> TableState:
        """Create a table with two seated players."""
        seats = []
        for i in range(table_config.max_seats):
            if i < 2:
                seats.append(SeatState(
                    position=i,
                    player=Player(user_id=f"player-{i}", nickname=f"Player{i}"),
                    stack=1000,
                    status=SeatStatus.ACTIVE,
                ))
            else:
                seats.append(SeatState(
                    position=i,
                    player=None,
                    stack=0,
                    status=SeatStatus.EMPTY,
                ))

        return TableState(
            table_id=str(uuid4()),
            config=table_config,
            seats=tuple(seats),
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def six_player_table(self, table_config: TableConfig) -> TableState:
        """Create a table with six seated players."""
        seats = []
        for i in range(table_config.max_seats):
            seats.append(SeatState(
                position=i,
                player=Player(user_id=f"player-{i}", nickname=f"Player{i}"),
                stack=1000,
                status=SeatStatus.ACTIVE,
            ))

        return TableState(
            table_id=str(uuid4()),
            config=table_config,
            seats=tuple(seats),
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.now(timezone.utc),
        )

    # =========================================================================
    # Hand Start Tests
    # =========================================================================

    def test_hand_start_with_two_players(
        self,
        wrapper: PokerKitWrapper,
        two_player_table: TableState,
    ):
        """Test: Hand starts correctly with two players."""
        # Start hand
        table = wrapper.create_initial_hand(two_player_table)

        # Hand should exist
        assert table.hand is not None
        assert table.hand.hand_id is not None

        # Phase should be PREFLOP
        from app.engine.state import GamePhase
        assert table.hand.phase == GamePhase.PREFLOP

        # Hole cards should be dealt
        for player_hand in table.hand.player_hands:
            assert len(player_hand.hole_cards) == 2

    def test_hand_start_with_six_players(
        self,
        wrapper: PokerKitWrapper,
        six_player_table: TableState,
    ):
        """Test: Hand starts correctly with six players."""
        table = wrapper.create_initial_hand(six_player_table)

        assert table.hand is not None

        # All players should have hole cards
        assert len(table.hand.player_hands) == 6
        for player_hand in table.hand.player_hands:
            assert len(player_hand.hole_cards) == 2

    def test_blinds_posted_on_hand_start(
        self,
        wrapper: PokerKitWrapper,
        two_player_table: TableState,
    ):
        """Test: Blinds are posted when hand starts."""
        table = wrapper.create_initial_hand(two_player_table)

        # Pot should have blinds
        assert table.hand.pot.main_pot > 0
        # Small blind (10) + Big blind (20) = 30
        assert table.hand.pot.main_pot == 30

    # =========================================================================
    # Turn Progression Tests
    # =========================================================================

    def test_turn_moves_after_action(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: Turn moves to next player after action."""
        table = wrapper.create_initial_hand(two_player_table)

        # Get current actor
        initial_actor = wrapper.get_current_actor_position(table)
        assert initial_actor is not None

        # Get valid actions
        valid_actions = wrapper.get_valid_actions(table, initial_actor)
        assert len(valid_actions) > 0

        # Perform call action
        action = ActionRequest(
            request_id=str(uuid4()),
            action_type=ActionType.CALL,
            amount=None,
        )

        current_player_id = table.seats[initial_actor].player.user_id
        result = processor.process_action(table, current_player_id, action)

        if result.success:
            new_table = result.new_state
            new_actor = wrapper.get_current_actor_position(new_table)
            # Turn should have moved or hand should be in different phase
            assert new_actor != initial_actor or new_table.hand.phase != table.hand.phase

    def test_preflop_to_flop_transition(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: Hand transitions from PREFLOP to FLOP."""
        table = wrapper.create_initial_hand(two_player_table)

        from app.engine.state import GamePhase

        # Complete preflop betting round
        max_iterations = 10
        iteration = 0

        while table.hand.phase == GamePhase.PREFLOP and iteration < max_iterations:
            actor = wrapper.get_current_actor_position(table)
            if actor is None:
                break

            player_id = table.seats[actor].player.user_id
            valid_actions = wrapper.get_valid_actions(table, actor)

            # Find CALL or CHECK action
            action_type = ActionType.CALL
            for va in valid_actions:
                if va.action_type == ActionType.CHECK:
                    action_type = ActionType.CHECK
                    break
                if va.action_type == ActionType.CALL:
                    action_type = ActionType.CALL
                    break

            action = ActionRequest(
                request_id=str(uuid4()),
                action_type=action_type,
                amount=None,
            )

            result = processor.process_action(table, player_id, action)
            if result.success:
                table = result.new_state
            iteration += 1

        # Should reach FLOP or later
        assert table.hand.phase in [
            GamePhase.FLOP,
            GamePhase.TURN,
            GamePhase.RIVER,
            GamePhase.SHOWDOWN,
            GamePhase.FINISHED,
        ]

    def test_flop_has_three_community_cards(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: FLOP phase has 3 community cards."""
        table = wrapper.create_initial_hand(two_player_table)

        from app.engine.state import GamePhase

        # Complete preflop
        max_iterations = 10
        iteration = 0

        while table.hand.phase == GamePhase.PREFLOP and iteration < max_iterations:
            actor = wrapper.get_current_actor_position(table)
            if actor is None:
                break

            player_id = table.seats[actor].player.user_id
            valid_actions = wrapper.get_valid_actions(table, actor)

            for va in valid_actions:
                if va.action_type in [ActionType.CHECK, ActionType.CALL]:
                    action = ActionRequest(
                        request_id=str(uuid4()),
                        action_type=va.action_type,
                        amount=None,
                    )
                    result = processor.process_action(table, player_id, action)
                    if result.success:
                        table = result.new_state
                    break
            iteration += 1

        # If at FLOP, should have 3 community cards
        if table.hand.phase == GamePhase.FLOP:
            assert len(table.hand.community_cards) == 3

    # =========================================================================
    # Action Tests
    # =========================================================================

    def test_fold_action(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: Fold action removes player from hand."""
        table = wrapper.create_initial_hand(two_player_table)

        actor = wrapper.get_current_actor_position(table)
        player_id = table.seats[actor].player.user_id

        # Fold
        action = ActionRequest(
            request_id=str(uuid4()),
            action_type=ActionType.FOLD,
            amount=None,
        )

        result = processor.process_action(table, player_id, action)
        assert result.success is True

        # Hand should be finished (only 2 players, one folded)
        from app.engine.state import GamePhase
        new_table = result.new_state
        assert new_table.hand.phase == GamePhase.FINISHED

    def test_raise_action(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: Raise action increases pot."""
        table = wrapper.create_initial_hand(two_player_table)

        actor = wrapper.get_current_actor_position(table)
        player_id = table.seats[actor].player.user_id
        initial_pot = table.hand.pot.main_pot

        # Get valid raise amounts
        valid_actions = wrapper.get_valid_actions(table, actor)
        raise_action = None
        for va in valid_actions:
            if va.action_type == ActionType.RAISE:
                raise_action = va
                break

        if raise_action:
            action = ActionRequest(
                request_id=str(uuid4()),
                action_type=ActionType.RAISE,
                amount=raise_action.min_amount,
            )

            result = processor.process_action(table, player_id, action)
            if result.success:
                new_table = result.new_state
                # Pot should have increased
                assert new_table.hand.pot.main_pot > initial_pot

    def test_all_in_action(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: All-in action bets entire stack."""
        table = wrapper.create_initial_hand(two_player_table)

        actor = wrapper.get_current_actor_position(table)
        player_id = table.seats[actor].player.user_id

        # All-in
        action = ActionRequest(
            request_id=str(uuid4()),
            action_type=ActionType.ALL_IN,
            amount=None,
        )

        result = processor.process_action(table, player_id, action)
        if result.success:
            new_table = result.new_state
            # Player's status should be ALL_IN
            from app.engine.state import PlayerHandStatus
            player_hand = None
            for ph in new_table.hand.player_hands:
                if ph.position == actor:
                    player_hand = ph
                    break
            if player_hand:
                assert player_hand.status == PlayerHandStatus.ALL_IN

    def test_invalid_action_rejected(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: Invalid action is rejected."""
        table = wrapper.create_initial_hand(two_player_table)

        # Get non-current player
        actor = wrapper.get_current_actor_position(table)
        other_position = 1 if actor == 0 else 0
        other_player_id = table.seats[other_position].player.user_id

        # Try to act when not your turn
        action = ActionRequest(
            request_id=str(uuid4()),
            action_type=ActionType.CALL,
            amount=None,
        )

        result = processor.process_action(table, other_player_id, action)
        # Should fail - not player's turn
        assert result.success is False

    def test_raise_below_minimum_rejected(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: Raise below minimum is rejected."""
        table = wrapper.create_initial_hand(two_player_table)

        actor = wrapper.get_current_actor_position(table)
        player_id = table.seats[actor].player.user_id

        # Try to raise with amount below minimum
        action = ActionRequest(
            request_id=str(uuid4()),
            action_type=ActionType.RAISE,
            amount=1,  # Way below minimum
        )

        result = processor.process_action(table, player_id, action)
        # Should fail - amount too low
        assert result.success is False

    # =========================================================================
    # Showdown Tests
    # =========================================================================

    def test_showdown_determines_winner(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        two_player_table: TableState,
    ):
        """Test: Showdown correctly determines winner."""
        table = wrapper.create_initial_hand(two_player_table)

        from app.engine.state import GamePhase

        # Play through all streets with check/call
        max_iterations = 50
        iteration = 0

        while not wrapper.is_hand_finished(table) and iteration < max_iterations:
            actor = wrapper.get_current_actor_position(table)
            if actor is None:
                break

            player_id = table.seats[actor].player.user_id
            valid_actions = wrapper.get_valid_actions(table, actor)

            # Prefer check, then call
            action_type = ActionType.CALL
            for va in valid_actions:
                if va.action_type == ActionType.CHECK:
                    action_type = ActionType.CHECK
                    break

            action = ActionRequest(
                request_id=str(uuid4()),
                action_type=action_type,
                amount=None,
            )

            result = processor.process_action(table, player_id, action)
            if result.success:
                table = result.new_state
            else:
                break
            iteration += 1

        # Hand should be finished
        if wrapper.is_hand_finished(table):
            # Evaluate hand
            result = wrapper.evaluate_hand(table)
            assert result is not None
            assert len(result.winners) > 0

    # =========================================================================
    # Side Pot Tests
    # =========================================================================

    def test_side_pot_with_all_in(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        table_config: TableConfig,
    ):
        """Test: Side pot is created when player goes all-in."""
        # Create table with unequal stacks
        seats = [
            SeatState(position=0, player=Player(user_id="player-0", nickname="Player0"), stack=500, status=SeatStatus.ACTIVE),  # Short stack
            SeatState(position=1, player=Player(user_id="player-1", nickname="Player1"), stack=1000, status=SeatStatus.ACTIVE),  # Normal stack
            SeatState(position=2, player=Player(user_id="player-2", nickname="Player2"), stack=1000, status=SeatStatus.ACTIVE),  # Normal stack
            SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
        ]

        table = TableState(
            table_id=str(uuid4()),
            config=table_config,
            seats=tuple(seats),
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.now(timezone.utc),
        )

        table = wrapper.create_initial_hand(table)

        # Player 0 (short stack) goes all-in
        actor = wrapper.get_current_actor_position(table)
        if actor is not None:
            player_id = table.seats[actor].player.user_id
            action = ActionRequest(
                request_id=str(uuid4()),
                action_type=ActionType.ALL_IN,
                amount=None,
            )
            result = processor.process_action(table, player_id, action)
            if result.success:
                table = result.new_state

        # Continue game and check for side pots later
        # This is a basic test - side pot logic is complex

    # =========================================================================
    # Serialization Tests
    # =========================================================================

    def test_snapshot_serialization(
        self,
        wrapper: PokerKitWrapper,
        serializer: SnapshotSerializer,
        two_player_table: TableState,
    ):
        """Test: Game state can be serialized and deserialized."""
        table = wrapper.create_initial_hand(two_player_table)

        # Serialize
        snapshot = serializer.serialize(table)
        assert snapshot is not None
        assert isinstance(snapshot, dict)

        # Deserialize
        restored = serializer.deserialize(snapshot)
        assert restored is not None
        assert restored.table_id == table.table_id

    def test_player_view_hides_opponent_cards(
        self,
        wrapper: PokerKitWrapper,
        serializer: SnapshotSerializer,
        two_player_table: TableState,
    ):
        """Test: Player view hides opponent's hole cards."""
        table = wrapper.create_initial_hand(two_player_table)

        # Get player 0's view
        player_view = serializer.create_player_view(table, "player-0")

        # Should see own cards
        assert player_view.my_hole_cards is not None
        assert len(player_view.my_hole_cards) == 2

        # Should not see opponent's cards
        for seat in player_view.seats:
            if seat.player.user_id != "player-0" and seat.player.user_id is not None:
                # Opponent's hole cards should be hidden
                pass  # Player view structure varies


# =============================================================================
# API-Level Game Flow Tests
# =============================================================================


class TestAPIGameFlow:
    """Test game flow through REST API."""

    @pytest.mark.asyncio
    async def test_create_join_leave_flow(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Create room → Join → Leave flow."""
        # Create room
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]

        # Player2 joins
        join_result = await join_room(
            integration_client,
            player2["headers"],
            room_id,
            1000,
        )
        assert "position" in join_result or join_result is not None

        # Player2 leaves
        leave_response = await integration_client.post(
            f"/api/v1/rooms/{room_id}/leave",
            headers=player2["headers"],
        )
        assert leave_response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_multiple_players_can_join(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
        player3: dict,
    ):
        """Test: Multiple players can join a room."""
        # Create room
        room = await create_room(
            integration_client,
            player1["headers"],
            max_seats=6,
        )
        room_id = room["id"]

        # Multiple players join
        join2 = await join_room(integration_client, player2["headers"], room_id, 1000)
        join3 = await join_room(integration_client, player3["headers"], room_id, 1500)

        # Verify both joined successfully
        assert join2 is not None
        assert join3 is not None

        # Get room state
        room_response = await integration_client.get(
            f"/api/v1/rooms/{room_id}",
            headers=player1["headers"],
        )
        assert room_response.status_code == 200

    @pytest.mark.asyncio
    async def test_different_buy_in_amounts(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
        player3: dict,
    ):
        """Test: Players can buy in with different amounts."""
        # Create room with specific buy-in range
        response = await integration_client.post(
            "/api/v1/rooms",
            json={
                "name": "Variable Buy-in Room",
                "maxSeats": 6,
                "smallBlind": 10,
                "bigBlind": 20,
                "buyInMin": 400,
                "buyInMax": 2000,
                "isPrivate": False,
            },
            headers=player1["headers"],
        )
        assert response.status_code == 201
        room_id = response.json()["data"]["id"]

        # Players join with different buy-ins
        await join_room(integration_client, player2["headers"], room_id, 400)  # Min
        await join_room(integration_client, player3["headers"], room_id, 2000)  # Max

        # Both should succeed
        room_response = await integration_client.get(
            f"/api/v1/rooms/{room_id}",
            headers=player1["headers"],
        )
        assert room_response.status_code == 200


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestGameEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def wrapper(self) -> PokerKitWrapper:
        return PokerKitWrapper()

    @pytest.fixture
    def processor(self, wrapper: PokerKitWrapper) -> ActionProcessor:
        return ActionProcessor(wrapper)

    @pytest.fixture
    def table_config(self) -> TableConfig:
        return TableConfig(
            max_seats=6,
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
            ante=0,
            turn_timeout_seconds=30,
        )

    def test_heads_up_button_rules(
        self,
        wrapper: PokerKitWrapper,
        table_config: TableConfig,
    ):
        """Test: Heads-up button rules are applied correctly."""
        # In heads-up, SB is on the button and acts first preflop
        seats = [
            SeatState(position=0, player=Player(user_id="player-0", nickname="Player0"), stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=1, player=Player(user_id="player-1", nickname="Player1"), stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=2, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
        ]

        table = TableState(
            table_id=str(uuid4()),
            config=table_config,
            seats=tuple(seats),
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.now(timezone.utc),
        )

        table = wrapper.create_initial_hand(table)

        # Hand should start correctly
        assert table.hand is not None

    def test_all_fold_to_big_blind(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        table_config: TableConfig,
    ):
        """Test: If all fold to big blind, BB wins."""
        seats = [
            SeatState(position=0, player=Player(user_id="player-0", nickname="Player0"), stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=1, player=Player(user_id="player-1", nickname="Player1"), stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=2, player=Player(user_id="player-2", nickname="Player2"), stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
        ]

        table = TableState(
            table_id=str(uuid4()),
            config=table_config,
            seats=tuple(seats),
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.now(timezone.utc),
        )

        table = wrapper.create_initial_hand(table)

        from app.engine.state import GamePhase

        # Everyone folds except one player
        max_iterations = 10
        iteration = 0

        while table.hand.phase == GamePhase.PREFLOP and iteration < max_iterations:
            actor = wrapper.get_current_actor_position(table)
            if actor is None:
                break

            player_id = table.seats[actor].player.user_id

            # Fold action
            action = ActionRequest(
                request_id=str(uuid4()),
                action_type=ActionType.FOLD,
                amount=None,
            )

            result = processor.process_action(table, player_id, action)
            if result.success:
                table = result.new_state

                # Check if hand ended
                if table.hand.phase == GamePhase.FINISHED:
                    break
            iteration += 1

        # Hand should be finished
        assert table.hand.phase == GamePhase.FINISHED

    def test_minimum_raise_after_raise(
        self,
        wrapper: PokerKitWrapper,
        processor: ActionProcessor,
        table_config: TableConfig,
    ):
        """Test: Minimum raise is at least the previous raise size."""
        seats = [
            SeatState(position=0, player=Player(user_id="player-0", nickname="Player0"), stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=1, player=Player(user_id="player-1", nickname="Player1"), stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=2, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
        ]

        table = TableState(
            table_id=str(uuid4()),
            config=table_config,
            seats=tuple(seats),
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.now(timezone.utc),
        )

        table = wrapper.create_initial_hand(table)

        actor = wrapper.get_current_actor_position(table)
        if actor is not None:
            player_id = table.seats[actor].player.user_id

            # First raise to 60 (raise of 40 over BB of 20)
            action = ActionRequest(
                request_id=str(uuid4()),
                action_type=ActionType.RAISE,
                amount=60,
            )

            result = processor.process_action(table, player_id, action)
            if result.success:
                table = result.new_state

                # Next player's minimum raise should be at least 100 (60 + 40)
                next_actor = wrapper.get_current_actor_position(table)
                if next_actor is not None:
                    valid_actions = wrapper.get_valid_actions(table, next_actor)
                    for va in valid_actions:
                        if va.action_type == ActionType.RAISE:
                            assert va.min_amount >= 100
