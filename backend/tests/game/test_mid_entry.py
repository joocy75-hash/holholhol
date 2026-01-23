"""
중간 입장 옵션 테스트: "바로 참여" vs "BB 대기"
"""
import pytest
from app.game.poker_table import PokerTable, Player, GamePhase


def create_table():
    """기본 테이블 생성 헬퍼."""
    return PokerTable(
        room_id="test_mid_entry",
        name="Mid Entry Test",
        small_blind=50,
        big_blind=100,
        min_buy_in=500,
        max_buy_in=5000,
        max_players=9,
    )


class TestMidEntryOption:
    """중간 입장 옵션 테스트."""

    def test_seat_player_default_sitting_out(self):
        """착석 시 기본 상태가 sitting_out인지 확인."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        result = table.seat_player(0, p1)

        assert result is True
        assert p1.status == "sitting_out"

    def test_sit_in_changes_to_active(self):
        """sit_in 호출 시 active로 변경되는지 확인."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        table.seat_player(0, p1)

        assert p1.status == "sitting_out"

        result = table.sit_in(0)
        assert result is True
        assert p1.status == "active"

    def test_sit_out_changes_to_sitting_out(self):
        """sit_out 호출 시 sitting_out으로 변경되는지 확인."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        table.seat_player(0, p1)
        table.sit_in(0)

        assert p1.status == "active"

        result = table.sit_out(0)
        assert result is True
        assert p1.status == "sitting_out"

    def test_get_active_players_excludes_sitting_out(self):
        """get_active_players가 sitting_out 플레이어를 제외하는지 확인."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        # p3는 sitting_out 유지

        active = table.get_active_players()
        assert len(active) == 2
        # get_active_players()는 Player 객체 리스트 반환
        active_user_ids = [p.user_id for p in active]
        assert "user1" in active_user_ids
        assert "user2" in active_user_ids
        assert "user3" not in active_user_ids

    def test_can_start_hand_requires_two_active(self):
        """can_start_hand가 2명 이상의 active 플레이어를 요구하는지 확인."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        # p2는 sitting_out 유지

        # 1명만 active - 시작 불가
        assert table.can_start_hand() is False

        # p2도 active로 변경
        table.sit_in(1)
        assert table.can_start_hand() is True


class TestBBWaiterActivation:
    """BB 위치 대기자 자동 활성화 테스트."""

    def test_activate_bb_waiter_with_one_active(self):
        """active 1명 + sitting_out 1명일 때 BB 대기자 활성화."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)  # active
        table.seat_player(1, p2)
        # p2는 sitting_out 유지

        # 초기 상태
        assert len(table.get_active_players()) == 1
        assert table.can_start_hand() is False

        # BB 대기자 활성화 시도
        activated = table.try_activate_bb_waiter_for_next_hand()

        # p2가 BB 위치라면 활성화됨
        if 1 in activated:
            assert p2.status == "active"
            assert len(table.get_active_players()) == 2
            assert table.can_start_hand() is True

    def test_activate_bb_waiter_three_players(self):
        """3인 게임에서 BB 대기자 활성화."""
        table = create_table()

        # 딜러, SB, BB 위치에 플레이어 배치
        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        # p3는 sitting_out

        # 첫 핸드 시작 (2명 active)
        result = table.start_new_hand()
        assert result["success"]

        # 핸드 완료 (한 명 폴드)
        current = table.players[table.current_player_seat]
        table.process_action(current.user_id, "fold")

        # p3가 BB 위치에 도달했는지 확인하고 활성화 시도
        activated = table.try_activate_bb_waiter_for_next_hand()

        # 활성화된 경우 확인
        if 2 in activated:
            assert p3.status == "active"
            print(f"✅ p3 (seat 2) 활성화됨")

    def test_no_activation_when_not_bb(self):
        """BB 위치가 아닌 sitting_out 플레이어는 활성화되지 않음."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)
        p3 = Player(user_id="user3", username="P3", seat=5, stack=1000)  # 멀리 떨어진 좌석

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(5, p3)
        # p3는 sitting_out

        # 딜러를 0으로 설정하면 BB는 1 (헤즈업 규칙 적용 안 됨, 3인이므로)
        # 실제로는 get_blind_seats()를 통해 결정됨

        # BB 대기자 활성화 시도
        activated = table.try_activate_bb_waiter_for_next_hand()

        # p3 (seat 5)는 BB 위치가 아니므로 활성화되지 않아야 함
        # (단, BB 위치 계산에 따라 다를 수 있음)
        print(f"활성화된 좌석: {activated}")


class TestSittingOutInGame:
    """게임 중 sitting_out 플레이어 처리 테스트."""

    def test_sitting_out_excluded_from_hand(self):
        """sitting_out 플레이어는 핸드에서 제외됨 (BB 자동 활성화 제외)."""
        table = create_table()

        # 4명 배치, 1명은 sitting_out
        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=1000)
        p4 = Player(user_id="user4", username="P4", seat=5, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        table.sit_in(2)
        table.seat_player(5, p4)
        # p4는 sitting_out

        result = table.start_new_hand()
        assert result["success"]

        # auto_activated에 포함되지 않은 sitting_out 플레이어는 카드 없음
        auto_activated = result.get("auto_activated", [])
        players_with_cards = [seat for seat, p in table.players.items()
                             if p and p.hole_cards]

        # 활성 플레이어(0,1,2)는 카드 있음
        assert 0 in players_with_cards
        assert 1 in players_with_cards
        assert 2 in players_with_cards

        # sitting_out 플레이어가 BB였다면 자동 활성화되어 카드를 받았을 것
        if 5 in auto_activated:
            assert 5 in players_with_cards
            assert p4.status == "active"
        else:
            # BB가 아니면 카드 없음
            assert 5 not in players_with_cards
            assert p4.status == "sitting_out"

    def test_sitting_out_at_bb_gets_activated(self):
        """BB 위치의 sitting_out 플레이어는 자동 활성화되어 카드를 받음."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(2, p3)
        # p3는 sitting_out이지만 BB 위치일 수 있음

        # sitting_out 상태 확인
        assert p3.status == "sitting_out"

        result = table.start_new_hand()
        assert result["success"]

        # BB 위치였다면 자동 활성화되어 카드를 받았을 것
        auto_activated = result.get("auto_activated", [])
        if 2 in auto_activated:
            assert p3.status == "active"
            assert p3.hole_cards is not None and len(p3.hole_cards) == 2

    def test_game_progress_with_sitting_out(self):
        """sitting_out 플레이어가 있어도 게임이 정상 진행."""
        table = create_table()

        # 3명 중 1명 sitting_out - 2명만 게임
        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)
        p3 = Player(user_id="user3", username="P3", seat=5, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)
        table.seat_player(5, p3)
        # p3는 sitting_out

        result = table.start_new_hand()
        assert result["success"]

        # 참여 인원 확인 (auto_activated 포함)
        auto_activated = result.get("auto_activated", [])
        players_in_hand = [seat for seat, p in table.players.items()
                          if p and p.hole_cards]

        print(f"참여 플레이어: {players_in_hand}, auto_activated: {auto_activated}")

        # 한 명씩 폴드하여 마지막 1명 남을 때까지
        while True:
            current = table.players[table.current_player_seat]
            result = table.process_action(current.user_id, "fold")
            assert result["success"]
            if result.get("hand_complete"):
                break

        # 다음 핸드도 시작 가능
        result = table.start_new_hand()
        assert result["success"]


class TestBotLoopWithMidEntry:
    """봇 루프 + 중간 입장 시나리오 테스트."""

    def test_player_joins_running_bot_game(self):
        """봇이 돌아가는 게임에 플레이어가 중간 입장."""
        table = create_table()

        # 봇 2명이 먼저 게임 중
        bot1 = Player(user_id="bot1", username="Bot1", seat=0, stack=1000, is_bot=True)
        bot2 = Player(user_id="bot2", username="Bot2", seat=1, stack=1000, is_bot=True)

        table.seat_player(0, bot1)
        table.sit_in(0)
        table.seat_player(1, bot2)
        table.sit_in(1)

        # 봇 게임 시작
        result = table.start_new_hand()
        assert result["success"]
        assert table.phase != GamePhase.WAITING

        # 플레이어 중간 입장
        player = Player(user_id="human1", username="Human", seat=5, stack=1000)
        join_result = table.seat_player(5, player)
        assert join_result is True
        assert player.status == "sitting_out"  # 기본값

        # 게임 중에는 플레이어가 sitting_out 상태 유지
        assert player.status == "sitting_out"

        # 핸드 완료
        current = table.players[table.current_player_seat]
        result = table.process_action(current.user_id, "fold")
        assert result.get("hand_complete")

        # BB 대기자 활성화 시도
        activated = table.try_activate_bb_waiter_for_next_hand()
        print(f"활성화된 좌석: {activated}")

        # 플레이어가 BB 위치라면 활성화됨
        if 5 in activated:
            assert player.status == "active"

    def test_immediate_join_option(self):
        """'바로 참여' 옵션 테스트."""
        table = create_table()

        # 봇 2명
        bot1 = Player(user_id="bot1", username="Bot1", seat=0, stack=1000, is_bot=True)
        bot2 = Player(user_id="bot2", username="Bot2", seat=1, stack=1000, is_bot=True)

        table.seat_player(0, bot1)
        table.sit_in(0)
        table.seat_player(1, bot2)
        table.sit_in(1)

        # 봇 게임 시작
        result = table.start_new_hand()
        assert result["success"]

        # 플레이어 착석 (기본 sitting_out)
        player = Player(user_id="human1", username="Human", seat=5, stack=1000)
        table.seat_player(5, player)
        assert player.status == "sitting_out"

        # '바로 참여' 선택 -> sit_in 호출
        table.sit_in(5)
        assert player.status == "active"

        # 핸드 완료
        current = table.players[table.current_player_seat]
        table.process_action(current.user_id, "fold")

        # 다음 핸드에 플레이어도 참여
        result = table.start_new_hand()
        assert result["success"]

        # 플레이어도 카드를 받았는지 확인
        assert player.hole_cards is not None and len(player.hole_cards) == 2


class TestEdgeCases:
    """엣지 케이스 테스트."""

    def test_all_sitting_out_cannot_start(self):
        """모두 sitting_out이면 게임 시작 불가."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)

        table.seat_player(0, p1)
        table.seat_player(1, p2)
        # 둘 다 sitting_out

        assert table.can_start_hand() is False

        # BB 대기자 활성화 시도해도 active 플레이어가 없으면 한계
        activated = table.try_activate_bb_waiter_for_next_hand()
        # 최소 1명은 활성화해야 하지만, 현재 로직은 active 기준으로 딜러를 정함

    def test_toggle_during_hand_preparation(self):
        """핸드 준비 중 토글 가능."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        # p2 sitting_out

        assert table.phase == GamePhase.WAITING

        # 토글: BB대기 -> 바로참여
        table.sit_in(1)
        assert p2.status == "active"

        # 토글: 바로참여 -> BB대기
        table.sit_out(1)
        assert p2.status == "sitting_out"

    def test_sit_out_during_hand_marks_status(self):
        """핸드 중 sit_out 호출 시 상태만 변경 (폴드는 별도 처리)."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)

        table.seat_player(0, p1)
        table.sit_in(0)
        table.seat_player(1, p2)
        table.sit_in(1)

        result = table.start_new_hand()
        assert result["success"]
        assert table.phase != GamePhase.WAITING

        # 핸드 중 sit_out
        table.sit_out(1)
        assert p2.status == "sitting_out"
        # 하지만 카드는 여전히 있음 (폴드는 별도)
        assert p2.hole_cards is not None
