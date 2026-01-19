"""블라인드 위치 테스트 - 2인부터 9인까지 모든 경우의 수 검증.

포커 표준 규칙:
- 헤즈업(2인): 딜러=SB, 상대=BB (딜러가 먼저 프리플랍 액션)
- 3인 이상: 딜러 좌측=SB, 그 다음=BB, 딜러(BTN)는 프리플랍 마지막 액션
"""

import pytest
from app.game.poker_table import (
    PokerTable,
    Player,
    GamePhase,
    CLOCKWISE_SEAT_ORDER,
    get_seat_to_clockwise_index,
)


def create_table() -> PokerTable:
    """테스트용 기본 테이블 생성."""
    return PokerTable(
        room_id="test-blind-position",
        name="Blind Position Test",
        small_blind=10,
        big_blind=20,
        min_buy_in=400,
        max_buy_in=2000,
        max_players=9,
    )


def get_blind_positions(table: PokerTable) -> dict:
    """핸드 시작 후 SB, BB 좌석 번호 반환."""
    sb_seat = None
    bb_seat = None

    for seat, player in table.players.items():
        if player and player.current_bet == table.small_blind:
            sb_seat = seat
        elif player and player.current_bet == table.big_blind:
            bb_seat = seat

    return {"sb_seat": sb_seat, "bb_seat": bb_seat, "dealer_seat": table.dealer_seat}


def get_clockwise_sorted_seats(seats: list, max_players: int = 9) -> list:
    """좌석 리스트를 시계방향 순서로 정렬."""
    seat_to_idx = get_seat_to_clockwise_index(max_players)
    return sorted(seats, key=lambda s: seat_to_idx.get(s, s))


def get_expected_positions(player_count: int, dealer_seat: int, seats: list, max_players: int = 9) -> dict:
    """예상 SB/BB 좌석 계산.

    Args:
        player_count: 플레이어 수
        dealer_seat: 딜러 좌석 번호
        seats: 좌석 리스트 (정렬 안 되어도 됨)
        max_players: 테이블 최대 플레이어 수

    Returns:
        {'sb_seat': int, 'bb_seat': int}
    """
    # 시계방향 순서로 정렬
    clockwise_seats = get_clockwise_sorted_seats(seats, max_players)
    dealer_idx = clockwise_seats.index(dealer_seat)

    if player_count == 2:
        # 헤즈업: 딜러=SB, 상대=BB
        sb_seat = dealer_seat
        bb_seat = clockwise_seats[(dealer_idx + 1) % len(clockwise_seats)]
    else:
        # 3인 이상: 딜러 다음이 SB, 그 다음이 BB
        sb_seat = clockwise_seats[(dealer_idx + 1) % len(clockwise_seats)]
        bb_seat = clockwise_seats[(dealer_idx + 2) % len(clockwise_seats)]

    return {"sb_seat": sb_seat, "bb_seat": bb_seat}


class TestHeadsUp:
    """2인(헤즈업) 블라인드 위치 테스트."""

    def test_heads_up_dealer_is_sb(self):
        """헤즈업에서 딜러가 SB인지 확인."""
        table = create_table()

        p1 = Player(user_id="user1", username="Player1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="Player2", seat=1, stack=1000)

        table.seat_player(0, p1)
        table.seat_player(1, p2)

        result = table.start_new_hand()
        assert result["success"], f"핸드 시작 실패: {result.get('error')}"

        positions = get_blind_positions(table)

        # 헤즈업 규칙: 딜러 = SB
        assert positions["sb_seat"] == positions["dealer_seat"], \
            f"헤즈업에서 딜러({positions['dealer_seat']})가 SB여야 함, 실제 SB={positions['sb_seat']}"

        # BB는 상대방
        assert positions["bb_seat"] != positions["dealer_seat"], \
            f"BB({positions['bb_seat']})는 딜러({positions['dealer_seat']})가 아니어야 함"

    def test_heads_up_various_seats(self):
        """헤즈업 - 다양한 좌석 조합 테스트."""
        seat_combos = [
            (0, 1), (0, 4), (2, 7), (3, 8), (1, 5), (4, 6)
        ]

        for seat_a, seat_b in seat_combos:
            table = create_table()

            p1 = Player(user_id="user1", username="P1", seat=seat_a, stack=1000)
            p2 = Player(user_id="user2", username="P2", seat=seat_b, stack=1000)

            table.seat_player(seat_a, p1)
            table.seat_player(seat_b, p2)

            result = table.start_new_hand()
            assert result["success"], f"핸드 시작 실패 (seats: {seat_a}, {seat_b})"

            positions = get_blind_positions(table)

            # 딜러 = SB
            assert positions["sb_seat"] == positions["dealer_seat"], \
                f"좌석({seat_a}, {seat_b}): 딜러({positions['dealer_seat']})가 SB({positions['sb_seat']})여야 함"


class TestThreePlayers:
    """3인 블라인드 위치 테스트."""

    def test_three_players_standard(self):
        """3인 게임 기본 테스트."""
        table = create_table()
        seats = [0, 1, 2]

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        expected = get_expected_positions(3, positions["dealer_seat"], seats)

        assert positions["sb_seat"] == expected["sb_seat"], \
            f"SB 불일치: 예상={expected['sb_seat']}, 실제={positions['sb_seat']}, 딜러={positions['dealer_seat']}"
        assert positions["bb_seat"] == expected["bb_seat"], \
            f"BB 불일치: 예상={expected['bb_seat']}, 실제={positions['bb_seat']}, 딜러={positions['dealer_seat']}"

    def test_three_players_non_adjacent(self):
        """3인 게임 - 비연속 좌석."""
        table = create_table()
        seats = [0, 3, 6]

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        expected = get_expected_positions(3, positions["dealer_seat"], seats)

        assert positions["sb_seat"] == expected["sb_seat"], \
            f"비연속 3인 SB 불일치: 예상={expected['sb_seat']}, 실제={positions['sb_seat']}"
        assert positions["bb_seat"] == expected["bb_seat"], \
            f"비연속 3인 BB 불일치: 예상={expected['bb_seat']}, 실제={positions['bb_seat']}"


class TestFourPlayers:
    """4인 블라인드 위치 테스트."""

    def test_four_players_standard(self):
        """4인 게임 기본 테스트."""
        table = create_table()
        seats = [0, 1, 2, 3]

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        expected = get_expected_positions(4, positions["dealer_seat"], seats)

        assert positions["sb_seat"] == expected["sb_seat"], \
            f"4인 SB 불일치: 예상={expected['sb_seat']}, 실제={positions['sb_seat']}, 딜러={positions['dealer_seat']}"
        assert positions["bb_seat"] == expected["bb_seat"], \
            f"4인 BB 불일치: 예상={expected['bb_seat']}, 실제={positions['bb_seat']}, 딜러={positions['dealer_seat']}"

    def test_four_players_scattered(self):
        """4인 게임 - 흩어진 좌석."""
        table = create_table()
        seats = [0, 2, 5, 8]

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        expected = get_expected_positions(4, positions["dealer_seat"], seats)

        assert positions["sb_seat"] == expected["sb_seat"]
        assert positions["bb_seat"] == expected["bb_seat"]


class TestFivePlayers:
    """5인 블라인드 위치 테스트."""

    def test_five_players_standard(self):
        """5인 게임 기본 테스트."""
        table = create_table()
        seats = [0, 1, 2, 3, 4]

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        expected = get_expected_positions(5, positions["dealer_seat"], seats)

        assert positions["sb_seat"] == expected["sb_seat"], \
            f"5인 SB 불일치: 예상={expected['sb_seat']}, 실제={positions['sb_seat']}"
        assert positions["bb_seat"] == expected["bb_seat"], \
            f"5인 BB 불일치: 예상={expected['bb_seat']}, 실제={positions['bb_seat']}"


class TestSixPlayers:
    """6인 블라인드 위치 테스트."""

    def test_six_players_standard(self):
        """6인 게임 기본 테스트."""
        table = create_table()
        seats = [0, 1, 2, 3, 4, 5]

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        expected = get_expected_positions(6, positions["dealer_seat"], seats)

        assert positions["sb_seat"] == expected["sb_seat"]
        assert positions["bb_seat"] == expected["bb_seat"]


class TestNinePlayers:
    """9인(풀 링) 블라인드 위치 테스트."""

    def test_nine_players_full_ring(self):
        """9인 풀 링 게임 테스트."""
        table = create_table()
        seats = list(range(9))  # 0~8

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        expected = get_expected_positions(9, positions["dealer_seat"], seats)

        assert positions["sb_seat"] == expected["sb_seat"], \
            f"9인 SB 불일치: 예상={expected['sb_seat']}, 실제={positions['sb_seat']}, 딜러={positions['dealer_seat']}"
        assert positions["bb_seat"] == expected["bb_seat"], \
            f"9인 BB 불일치: 예상={expected['bb_seat']}, 실제={positions['bb_seat']}, 딜러={positions['dealer_seat']}"


class TestMultipleHands:
    """여러 핸드 연속 진행 시 블라인드 순환 테스트."""

    def test_dealer_rotation_three_players(self):
        """3인 게임에서 딜러 버튼이 시계방향으로 이동하는지 확인."""
        table = create_table()
        seats = [0, 1, 2]

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        dealer_sequence = []

        for hand_num in range(6):  # 6핸드 진행 (2번 순환)
            result = table.start_new_hand()
            assert result["success"], f"핸드 {hand_num} 시작 실패"

            positions = get_blind_positions(table)
            dealer_sequence.append(positions["dealer_seat"])

            # 블라인드 위치 검증
            expected = get_expected_positions(3, positions["dealer_seat"], seats)
            assert positions["sb_seat"] == expected["sb_seat"], f"핸드 {hand_num}: SB 불일치"
            assert positions["bb_seat"] == expected["bb_seat"], f"핸드 {hand_num}: BB 불일치"

            # 핸드 종료 시뮬레이션 (모두 폴드)
            table.phase = GamePhase.WAITING

        # 딜러가 시계방향으로 순환했는지 확인
        for i in range(1, len(dealer_sequence)):
            prev_dealer = dealer_sequence[i - 1]
            curr_dealer = dealer_sequence[i]

            prev_idx = seats.index(prev_dealer)
            expected_next = seats[(prev_idx + 1) % len(seats)]

            assert curr_dealer == expected_next, \
                f"딜러 순환 오류: {dealer_sequence}, 핸드 {i}에서 예상={expected_next}, 실제={curr_dealer}"


class TestBetAmounts:
    """베팅 금액 정확성 테스트."""

    def test_correct_blind_amounts(self):
        """SB/BB 금액이 정확한지 확인."""
        table = create_table()  # SB=10, BB=20

        for i in range(4):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=i, stack=1000)
            table.seat_player(i, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)

        sb_player = table.players[positions["sb_seat"]]
        bb_player = table.players[positions["bb_seat"]]

        assert sb_player.current_bet == 10, f"SB 금액 오류: {sb_player.current_bet}"
        assert bb_player.current_bet == 20, f"BB 금액 오류: {bb_player.current_bet}"

        # 스택에서 차감됐는지 확인
        assert sb_player.stack == 990, f"SB 스택 오류: {sb_player.stack}"
        assert bb_player.stack == 980, f"BB 스택 오류: {bb_player.stack}"


class TestFirstActionPlayer:
    """첫 액션 플레이어 검증."""

    def test_heads_up_sb_acts_first_preflop(self):
        """헤즈업에서 SB(딜러)가 프리플랍 첫 액션."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)

        table.seat_player(0, p1)
        table.seat_player(1, p2)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)

        # 헤즈업: SB(딜러)가 프리플랍에서 먼저 액션
        assert table.current_player_seat == positions["sb_seat"], \
            f"헤즈업 첫 액션: 예상 SB({positions['sb_seat']}), 실제={table.current_player_seat}"

    def test_three_plus_utg_acts_first_preflop(self):
        """3인 이상에서 UTG가 프리플랍 첫 액션."""
        table = create_table()
        seats = [0, 1, 2]  # 순서대로

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        dealer = positions["dealer_seat"]

        # 3인: UTG = BB 다음 = 딜러
        dealer_idx = seats.index(dealer)
        expected_utg = seats[(dealer_idx + 3) % 3]  # 3인이면 딜러=UTG

        # 3인 게임에서 UTG = 딜러(BTN)
        assert table.current_player_seat == dealer, \
            f"3인 첫 액션: 예상 딜러/UTG({dealer}), 실제={table.current_player_seat}"


class TestPostflopActionOrder:
    """Postflop 액션 순서 검증 (헤즈업 vs 3인 이상)."""

    def test_heads_up_bb_acts_first_postflop(self):
        """헤즈업에서 BB가 postflop 첫 액션."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)

        table.seat_player(0, p1)
        table.seat_player(1, p2)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        sb_seat = positions["sb_seat"]
        bb_seat = positions["bb_seat"]

        # Preflop: SB(딜러)가 먼저 액션
        assert table.current_player_seat == sb_seat, \
            f"Preflop 첫 액션: 예상 SB({sb_seat}), 실제={table.current_player_seat}"

        # SB가 콜 (BB와 같은 금액)
        result = table.process_action(p1.user_id if sb_seat == 0 else p2.user_id, "call")
        assert result["success"], f"SB 콜 실패: {result.get('error')}"

        # BB가 체크 (Preflop 끝)
        result = table.process_action(p1.user_id if bb_seat == 0 else p2.user_id, "check")
        assert result["success"], f"BB 체크 실패: {result.get('error')}"

        # Flop: 페이즈 전환 확인
        assert table.phase == GamePhase.FLOP, \
            f"Flop 페이즈 예상, 실제={table.phase.value}"

        # Postflop: BB가 먼저 액션
        assert table.current_player_seat == bb_seat, \
            f"Postflop 첫 액션: 예상 BB({bb_seat}), 실제={table.current_player_seat}"

    def test_heads_up_bb_acts_first_all_streets(self):
        """헤즈업에서 모든 postflop 스트릿(Flop, Turn, River)에서 BB 먼저 액션."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=2, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=5, stack=1000)

        table.seat_player(2, p1)
        table.seat_player(5, p2)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        sb_seat = positions["sb_seat"]
        bb_seat = positions["bb_seat"]

        # Preflop: SB 콜, BB 체크
        sb_user_id = p1.user_id if sb_seat == 2 else p2.user_id
        bb_user_id = p1.user_id if bb_seat == 2 else p2.user_id

        result = table.process_action(sb_user_id, "call")
        assert result["success"]
        result = table.process_action(bb_user_id, "check")
        assert result["success"]

        # Flop: BB 먼저
        assert table.phase == GamePhase.FLOP
        assert table.current_player_seat == bb_seat, \
            f"Flop: 예상 BB({bb_seat}), 실제={table.current_player_seat}"

        # BB 체크, SB 체크
        result = table.process_action(bb_user_id, "check")
        assert result["success"]
        result = table.process_action(sb_user_id, "check")
        assert result["success"]

        # Turn: BB 먼저
        assert table.phase == GamePhase.TURN
        assert table.current_player_seat == bb_seat, \
            f"Turn: 예상 BB({bb_seat}), 실제={table.current_player_seat}"

        # BB 체크, SB 체크
        result = table.process_action(bb_user_id, "check")
        assert result["success"]
        result = table.process_action(sb_user_id, "check")
        assert result["success"]

        # River: BB 먼저
        assert table.phase == GamePhase.RIVER
        assert table.current_player_seat == bb_seat, \
            f"River: 예상 BB({bb_seat}), 실제={table.current_player_seat}"

    def test_three_players_sb_acts_first_postflop(self):
        """3인 이상 게임에서 SB가 postflop 첫 액션."""
        table = create_table()
        seats = [0, 1, 2]

        for i, seat in enumerate(seats):
            p = Player(user_id=f"user{i}", username=f"P{i}", seat=seat, stack=1000)
            table.seat_player(seat, p)

        result = table.start_new_hand()
        assert result["success"]

        positions = get_blind_positions(table)
        sb_seat = positions["sb_seat"]
        bb_seat = positions["bb_seat"]
        dealer_seat = positions["dealer_seat"]

        # Preflop: UTG(딜러) 먼저 액션
        assert table.current_player_seat == dealer_seat

        # UTG(딜러) 콜
        dealer_player = table.players[dealer_seat]
        result = table.process_action(dealer_player.user_id, "call")
        assert result["success"]

        # SB 콜
        sb_player = table.players[sb_seat]
        result = table.process_action(sb_player.user_id, "call")
        assert result["success"]

        # BB 체크
        bb_player = table.players[bb_seat]
        result = table.process_action(bb_player.user_id, "check")
        assert result["success"]

        # Postflop: SB가 먼저 액션 (딜러가 아님)
        assert table.phase == GamePhase.FLOP
        assert table.current_player_seat == sb_seat, \
            f"3인 Postflop: 예상 SB({sb_seat}), 실제={table.current_player_seat}"


class TestPlayerCountTransition:
    """2↔3인 전환 시 블라인드 및 액션 순서 전환 테스트."""

    def test_three_to_two_transition(self):
        """3인 → 2인(헤즈업) 전환 시 블라인드 규칙 변경."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=1, stack=1000)
        p3 = Player(user_id="user3", username="P3", seat=2, stack=1000)

        table.seat_player(0, p1)
        table.seat_player(1, p2)
        table.seat_player(2, p3)

        # 3인 게임 시작
        result = table.start_new_hand()
        assert result["success"]
        assert len(table.get_active_players()) == 3

        # 3인 게임 블라인드 확인
        positions_3p = get_blind_positions(table)
        dealer_3p = positions_3p["dealer_seat"]
        sb_3p = positions_3p["sb_seat"]
        bb_3p = positions_3p["bb_seat"]

        # 3인: 딜러 ≠ SB
        assert dealer_3p != sb_3p, "3인 게임에서 딜러는 SB가 아니어야 함"

        # 핸드 완료 (모두 폴드)
        current_player = table.players[table.current_player_seat]
        table.process_action(current_player.user_id, "fold")
        current_player = table.players[table.current_player_seat]
        table.process_action(current_player.user_id, "fold")

        # 한 명이 떠남 (헤즈업으로 전환)
        table.remove_player(2)  # P3 제거

        # 2인 게임 시작
        result = table.start_new_hand()
        assert result["success"]
        assert len(table.get_active_players()) == 2

        # 헤즈업 블라인드 확인
        positions_2p = get_blind_positions(table)
        dealer_2p = positions_2p["dealer_seat"]
        sb_2p = positions_2p["sb_seat"]
        bb_2p = positions_2p["bb_seat"]

        # 헤즈업: 딜러 = SB
        assert dealer_2p == sb_2p, \
            f"헤즈업 전환 후 딜러({dealer_2p})가 SB({sb_2p})여야 함"
        assert dealer_2p != bb_2p, \
            f"헤즈업 전환 후 딜러({dealer_2p})가 BB({bb_2p})가 아니어야 함"

        # Preflop 액션 순서: SB(딜러) 먼저
        assert table.current_player_seat == sb_2p, \
            f"헤즈업 전환 후 첫 액션: 예상 SB({sb_2p}), 실제={table.current_player_seat}"

    def test_two_to_three_transition(self):
        """2인(헤즈업) → 3인 전환 시 블라인드 규칙 변경."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=0, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=3, stack=1000)

        table.seat_player(0, p1)
        table.seat_player(3, p2)

        # 2인 게임 시작
        result = table.start_new_hand()
        assert result["success"]
        assert len(table.get_active_players()) == 2

        # 헤즈업 블라인드 확인
        positions_2p = get_blind_positions(table)
        dealer_2p = positions_2p["dealer_seat"]
        sb_2p = positions_2p["sb_seat"]
        bb_2p = positions_2p["bb_seat"]

        # 헤즈업: 딜러 = SB
        assert dealer_2p == sb_2p, "헤즈업에서 딜러가 SB여야 함"

        # 핸드 완료 (한 명 폴드)
        sb_player = table.players[sb_2p]
        table.process_action(sb_player.user_id, "fold")

        # 새로운 플레이어 합류 (3인으로 전환)
        p3 = Player(user_id="user3", username="P3", seat=5, stack=1000)
        table.seat_player(5, p3)

        # 3인 게임 시작
        result = table.start_new_hand()
        assert result["success"]
        assert len(table.get_active_players()) == 3

        # 3인 블라인드 확인
        positions_3p = get_blind_positions(table)
        dealer_3p = positions_3p["dealer_seat"]
        sb_3p = positions_3p["sb_seat"]
        bb_3p = positions_3p["bb_seat"]

        # 3인: 딜러 ≠ SB
        assert dealer_3p != sb_3p, \
            f"3인 전환 후 딜러({dealer_3p})가 SB({sb_3p})가 아니어야 함"

        # 3인: SB와 BB가 다름
        assert sb_3p != bb_3p, \
            f"3인 전환 후 SB({sb_3p})와 BB({bb_3p})가 달라야 함"

        # Preflop 액션 순서: UTG(딜러) 먼저
        assert table.current_player_seat == dealer_3p, \
            f"3인 전환 후 첫 액션: 예상 딜러/UTG({dealer_3p}), 실제={table.current_player_seat}"

    def test_transition_preserves_dealer_rotation(self):
        """전환 시 딜러 버튼 회전이 유지되는지 확인."""
        table = create_table()

        p1 = Player(user_id="user1", username="P1", seat=1, stack=1000)
        p2 = Player(user_id="user2", username="P2", seat=4, stack=1000)
        p3 = Player(user_id="user3", username="P3", seat=7, stack=1000)

        table.seat_player(1, p1)
        table.seat_player(4, p2)
        table.seat_player(7, p3)

        # 첫 핸드: 3인
        result = table.start_new_hand()
        assert result["success"]
        first_dealer = table.dealer_seat

        # 핸드 완료
        table.process_action(table.players[table.current_player_seat].user_id, "fold")
        table.process_action(table.players[table.current_player_seat].user_id, "fold")

        # P3 제거 → 헤즈업
        table.remove_player(7)

        # 두 번째 핸드: 헤즈업
        result = table.start_new_hand()
        assert result["success"]
        second_dealer = table.dealer_seat

        # 딜러가 시계방향으로 이동했는지 확인
        remaining_seats = [1, 4]
        assert second_dealer in remaining_seats, \
            f"딜러({second_dealer})가 남은 좌석({remaining_seats})에 있어야 함"

        # 딜러가 변경되었는지 확인 (첫 핸드와 다름)
        if first_dealer in remaining_seats:
            # 첫 딜러가 남아있다면, 다음 딜러로 이동했어야 함
            next_dealer = table.get_next_clockwise_seat(first_dealer, remaining_seats)
            assert second_dealer == next_dealer, \
                f"딜러 회전 유지: 예상({next_dealer}), 실제({second_dealer})"
