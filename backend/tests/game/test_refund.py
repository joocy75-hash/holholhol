"""환불 (Uncalled Bets) 로직 테스트.

포커 규칙:
- 모든 플레이어가 폴드하면 마지막 플레이어의 초과 베팅(uncalled bet) 반환
- 환불 금액 = 승자의 베팅 - max(다른 플레이어들의 베팅)
"""

import pytest
from app.game.poker_table import PokerTable, Player, GamePhase


def create_table(small_blind: int = 50, big_blind: int = 100) -> PokerTable:
    """테스트용 테이블 생성."""
    return PokerTable(
        room_id="test-refund",
        name="Refund Test",
        small_blind=small_blind,
        big_blind=big_blind,
        min_buy_in=1000,
        max_buy_in=10000,
        max_players=9,
    )


class TestRefundCalculation:
    """환불 계산 테스트."""

    def test_no_refund_when_called(self):
        """콜된 경우 환불 없음."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=2000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=2000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=2000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        table.sit_in(2)

        result = table.start_new_hand()
        assert result["success"]

        # UTG 레이즈 to 300
        utg_seat = table.current_player_seat
        utg_player = table.players[utg_seat]
        result = table.process_action(utg_player.user_id, "raise", 300)
        assert result["success"]

        # SB 콜
        sb_seat = table.current_player_seat
        sb_player = table.players[sb_seat]
        result = table.process_action(sb_player.user_id, "call")
        assert result["success"]

        # BB 폴드 → 2명 남음, 쇼다운
        bb_seat = table.current_player_seat
        bb_player = table.players[bb_seat]
        result = table.process_action(bb_player.user_id, "fold")
        assert result["success"]

        # 2명 남았으므로 쇼다운 진행 (환불 없음)
        if result.get("hand_result"):
            hand_result = result["hand_result"]
            assert hand_result.get("refund") is None

    def test_refund_on_all_fold(self):
        """모두 폴드 시 환불 발생."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=2000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=2000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=2000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        table.sit_in(2)

        result = table.start_new_hand()
        assert result["success"]

        # UTG 레이즈 to 500
        utg_seat = table.current_player_seat
        utg_player = table.players[utg_seat]
        result = table.process_action(utg_player.user_id, "raise", 500)
        assert result["success"]

        # SB 폴드
        sb_seat = table.current_player_seat
        sb_player = table.players[sb_seat]
        result = table.process_action(sb_player.user_id, "fold")
        assert result["success"]

        # BB 폴드 → UTG 승리, 환불 발생
        bb_seat = table.current_player_seat
        bb_player = table.players[bb_seat]
        result = table.process_action(bb_player.user_id, "fold")
        assert result["success"]
        assert result["hand_complete"]

        hand_result = result.get("hand_result")
        assert hand_result is not None

        refund = hand_result.get("refund")
        assert refund is not None

        # 환불 금액 = UTG 베팅(500) - max(SB, BB 베팅) = 500 - 100(BB) = 400
        assert refund["seat"] == utg_seat
        assert refund["userId"] == utg_player.user_id
        assert refund["amount"] == 400

    def test_refund_with_raise_and_fold(self):
        """레이즈 후 모두 폴드."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=2000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=2000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)

        result = table.start_new_hand()
        assert result["success"]

        # 헤즈업: SB(딜러)가 먼저 액션
        # SB 레이즈 to 300
        first_seat = table.current_player_seat
        first_player = table.players[first_seat]
        result = table.process_action(first_player.user_id, "raise", 300)
        assert result["success"]

        # BB 폴드
        second_seat = table.current_player_seat
        second_player = table.players[second_seat]
        result = table.process_action(second_player.user_id, "fold")
        assert result["success"]
        assert result["hand_complete"]

        hand_result = result.get("hand_result")
        assert hand_result is not None

        refund = hand_result.get("refund")
        assert refund is not None

        # 환불 금액 = SB 베팅(300) - BB 베팅(100) = 200
        assert refund["seat"] == first_seat
        assert refund["amount"] == 200

    def test_no_refund_when_bet_equals_call(self):
        """레이즈 후 콜된 경우 환불 없음."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=2000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=2000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=2000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        table.sit_in(2)

        result = table.start_new_hand()
        assert result["success"]

        # UTG 레이즈 to 300
        utg_seat = table.current_player_seat
        utg_player = table.players[utg_seat]
        result = table.process_action(utg_player.user_id, "raise", 300)
        assert result["success"]

        # SB 콜 (300으로 맞춤)
        sb_seat = table.current_player_seat
        sb_player = table.players[sb_seat]
        result = table.process_action(sb_player.user_id, "call")
        assert result["success"]

        # BB 폴드 → UTG와 SB 2명 남음 (쇼다운)
        bb_seat = table.current_player_seat
        bb_player = table.players[bb_seat]
        result = table.process_action(bb_player.user_id, "fold")
        assert result["success"]

        # 2명 남았으므로 쇼다운 진행
        # UTG 베팅 = SB 베팅 = 300 → 환불 없음
        if result.get("hand_result"):
            hand_result = result["hand_result"]
            refund = hand_result.get("refund")
            assert refund is None


class TestRefundInHandResult:
    """HandResult에 환불 정보 포함 테스트."""

    def test_hand_result_contains_refund_info(self):
        """HandResult에 refund 필드가 올바르게 포함됨."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=2000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=2000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=2000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        table.sit_in(2)

        result = table.start_new_hand()
        assert result["success"]

        # UTG 레이즈 to 1000
        utg_seat = table.current_player_seat
        utg_player = table.players[utg_seat]
        result = table.process_action(utg_player.user_id, "raise", 1000)
        assert result["success"]

        # SB 폴드
        sb_seat = table.current_player_seat
        sb_player = table.players[sb_seat]
        result = table.process_action(sb_player.user_id, "fold")
        assert result["success"]

        # BB 폴드
        bb_seat = table.current_player_seat
        bb_player = table.players[bb_seat]
        result = table.process_action(bb_player.user_id, "fold")
        assert result["success"]

        hand_result = result.get("hand_result")
        assert hand_result is not None

        # 필수 필드 확인
        assert "winners" in hand_result
        assert "pot" in hand_result
        assert "showdown" in hand_result
        assert "communityCards" in hand_result
        assert "refund" in hand_result

        refund = hand_result["refund"]
        assert refund is not None
        assert "seat" in refund
        assert "userId" in refund
        assert "amount" in refund

        # 환불 금액 = 1000 - 100 = 900
        assert refund["amount"] == 900

    def test_hand_result_refund_none_on_showdown(self):
        """쇼다운 시 환불 없음."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=2000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=2000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)

        result = table.start_new_hand()
        assert result["success"]

        # 헤즈업: 체크다운으로 쇼다운까지
        # SB 콜
        first_player = table.players[table.current_player_seat]
        result = table.process_action(first_player.user_id, "call")
        assert result["success"]

        # BB 체크
        second_player = table.players[table.current_player_seat]
        result = table.process_action(second_player.user_id, "check")
        assert result["success"]

        # Flop ~ River 체크다운
        while table.phase != GamePhase.WAITING:
            if table.current_player_seat is None:
                break
            current_player = table.players[table.current_player_seat]
            result = table.process_action(current_player.user_id, "check")
            if result.get("hand_complete"):
                break

        hand_result = result.get("hand_result")
        if hand_result:
            # 쇼다운이므로 환불 없음
            refund = hand_result.get("refund")
            assert refund is None


class TestRefundEdgeCases:
    """환불 엣지 케이스 테스트."""

    def test_refund_preflop_all_fold(self):
        """프리플랍에서 모두 폴드."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=2000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=2000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=2000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        table.sit_in(2)

        result = table.start_new_hand()
        assert result["success"]

        # UTG 폴드
        utg_player = table.players[table.current_player_seat]
        result = table.process_action(utg_player.user_id, "fold")
        assert result["success"]

        # SB 폴드 → BB 승리
        sb_player = table.players[table.current_player_seat]
        result = table.process_action(sb_player.user_id, "fold")
        assert result["success"]
        assert result["hand_complete"]

        hand_result = result.get("hand_result")
        assert hand_result is not None

        # BB는 100 베팅, SB는 50 베팅 → BB 환불 없음 (최고 베팅)
        refund = hand_result.get("refund")
        # BB 베팅(100) - SB 베팅(50) = 50 환불? 아니, UTG는 0 베팅
        # SB 50, BB 100, UTG 0 → BB 베팅(100) - max(50, 0) = 50 환불
        assert refund is not None
        assert refund["amount"] == 50

    def test_refund_multiple_callers_then_fold(self):
        """여러 명이 콜 후 마지막에 폴드."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=2000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=2000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=2000)
        p4 = Player(user_id="user4", username="P4", seat=3, stack=2000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        table.sit_in(2)
        table.seat_player(3, p4)
        table.sit_in(3)

        result = table.start_new_hand()
        assert result["success"]

        # UTG 레이즈 to 300
        utg_player = table.players[table.current_player_seat]
        utg_seat = table.current_player_seat
        result = table.process_action(utg_player.user_id, "raise", 300)
        assert result["success"]

        # BTN 콜
        btn_player = table.players[table.current_player_seat]
        result = table.process_action(btn_player.user_id, "call")
        assert result["success"]

        # SB 콜
        sb_player = table.players[table.current_player_seat]
        result = table.process_action(sb_player.user_id, "call")
        assert result["success"]

        # BB 레이즈 to 800
        bb_player = table.players[table.current_player_seat]
        bb_seat = table.current_player_seat
        result = table.process_action(bb_player.user_id, "raise", 800)
        assert result["success"]

        # UTG 폴드
        result = table.process_action(utg_player.user_id, "fold")
        assert result["success"]

        # BTN 폴드
        result = table.process_action(btn_player.user_id, "fold")
        assert result["success"]

        # SB 폴드 → BB 승리
        result = table.process_action(sb_player.user_id, "fold")
        assert result["success"]
        assert result["hand_complete"]

        hand_result = result.get("hand_result")
        assert hand_result is not None

        refund = hand_result.get("refund")
        assert refund is not None

        # BB 베팅(800) - max(UTG 300, BTN 300, SB 300) = 500 환불
        assert refund["seat"] == bb_seat
        assert refund["amount"] == 500
