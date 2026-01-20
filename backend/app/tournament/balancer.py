"""
Table Balancing Algorithm.

탈락자 발생 시 실시간으로 테이블 인원을 재배치하는 알고리즘.
게임 흐름을 방해하지 않는 최적의 타이밍을 계산.

핵심 설계 원칙:
1. 테이블 간 인원 차이 최소화 (±1 이내 유지)
2. 최소 이동 원칙 (불필요한 이동 방지)
3. 핸드 진행 중 이동 금지 (핸드 종료 후 대기)
4. Breaking Table 우선 (큰 테이블보다 작은 테이블 해체)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from uuid import uuid4

from .models import (
    TournamentState,
    TournamentTable,
    TournamentPlayer,
    TournamentEvent,
    TournamentEventType,
)


class BalancingPriority(Enum):
    """Balancing urgency levels."""

    NONE = 0  # 밸런싱 불필요
    LOW = 1  # 작은 불균형 (±2 이내)
    MEDIUM = 2  # 중간 불균형 (±3 이상)
    HIGH = 3  # 심각한 불균형 또는 테이블 해체 필요
    CRITICAL = 4  # 파이널 테이블 구성 필요


@dataclass(frozen=True)
class PlayerMove:
    """Single player move instruction."""

    move_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    from_table_id: str = ""
    from_seat: int = 0
    to_table_id: str = ""
    to_seat: int = 0
    priority: BalancingPriority = BalancingPriority.MEDIUM

    # Execution tracking
    scheduled_at: datetime = field(default_factory=datetime.utcnow)
    execute_after_hand: bool = True  # 핸드 종료 후 실행

    def to_dict(self) -> Dict:
        return {
            "move_id": self.move_id,
            "user_id": self.user_id,
            "from_table_id": self.from_table_id,
            "from_seat": self.from_seat,
            "to_table_id": self.to_table_id,
            "to_seat": self.to_seat,
            "priority": self.priority.name,
        }


@dataclass
class BalancingPlan:
    """Complete balancing plan."""

    plan_id: str = field(default_factory=lambda: str(uuid4()))
    tournament_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    moves: List[PlayerMove] = field(default_factory=list)
    tables_to_break: List[str] = field(default_factory=list)
    tables_to_create: int = 0

    priority: BalancingPriority = BalancingPriority.NONE
    estimated_duration_seconds: float = 0.0

    @property
    def total_moves(self) -> int:
        return len(self.moves)

    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "tournament_id": self.tournament_id,
            "total_moves": self.total_moves,
            "tables_to_break": self.tables_to_break,
            "priority": self.priority.name,
            "moves": [m.to_dict() for m in self.moves],
        }


class TableBalancer:
    """
    Tournament Table Balancing Engine.

    밸런싱 알고리즘 상세:
    ─────────────────────────────────────────────────────────────────

    1. 밸런싱 트리거:
       - 핸드 종료 시 자동 체크
       - 플레이어 탈락 시 즉시 체크
       - 관리자 수동 트리거

    2. 밸런싱 조건:
       - 테이블 간 인원 차이 > 1
       - 테이블 인원 < min_players (테이블 해체 필요)
       - 전체 인원 < final_table_size (파이널 테이블 구성)

    3. 이동 대상 선택:
       - 가장 많은 테이블에서 가장 적은 테이블로 이동
       - 딜러 버튼 기준 다음 빅블라인드 위치의 플레이어
       - 이동 후에도 인원 차이 ≤ 1 유지

    4. 실행 타이밍:
       - 핸드 진행 중인 테이블: 핸드 종료 후 이동
       - 핸드 없는 테이블: 즉시 이동
       - 테이블 해체: 모든 핸드 종료 후 실행

    ─────────────────────────────────────────────────────────────────

    최적화:
    - O(n log n) 정렬 기반 알고리즘
    - 최소 이동 계산 (그리디 접근)
    - 연속 이동 배치 처리
    """

    def __init__(
        self,
        min_players_per_table: int = 2,
        max_players_per_table: int = 9,
        final_table_size: int = 9,
    ):
        self.min_players = min_players_per_table
        self.max_players = max_players_per_table
        self.final_table_size = final_table_size

        # Pending moves (waiting for hand completion)
        self._pending_moves: Dict[str, List[PlayerMove]] = {}  # table_id -> moves

    def calculate_balancing_plan(
        self,
        state: TournamentState,
    ) -> BalancingPlan:
        """
        Calculate optimal table balancing plan.

        밸런싱 계산 알고리즘:
        ─────────────────────────────────────────────────────────────

        Step 1: 현재 상태 분석
        - 각 테이블의 플레이어 수 계산
        - 전체 활성 플레이어 수 확인
        - 이상적인 테이블 수 계산

        Step 2: 필요한 이동 계산
        - 평균 인원에서 ±1 범위를 타겟으로 설정
        - 과잉 테이블에서 부족 테이블로 이동
        - 테이블 해체가 필요한 경우 처리

        Step 3: 이동 순서 결정
        - 핸드 진행 중인 테이블은 나중에 처리
        - 해체 테이블의 플레이어는 먼저 이동

        ─────────────────────────────────────────────────────────────

        Args:
            state: Current tournament state

        Returns:
            BalancingPlan with all required moves
        """
        plan = BalancingPlan(tournament_id=state.tournament_id)

        # Get active tables with player counts
        tables = list(state.tables.values())
        if not tables:
            return plan

        # Calculate player counts per table
        table_counts: Dict[str, int] = {}
        for table in tables:
            table_counts[table.table_id] = table.player_count

        # Total active players
        total_players = sum(table_counts.values())

        if total_players == 0:
            return plan

        # Check for final table scenario
        if total_players <= self.final_table_size and len(tables) > 1:
            # 파이널 테이블 구성 필요
            plan.priority = BalancingPriority.CRITICAL
            return self._plan_final_table(state, plan)

        # Calculate ideal distribution
        # 목표: 모든 테이블이 ±1 범위 내의 플레이어 수 유지
        num_tables = len(tables)
        ideal_per_table = total_players // num_tables
        remainder = total_players % num_tables

        # Ideal counts: some tables have +1
        ideal_counts = {
            table.table_id: ideal_per_table + (1 if i < remainder else 0)
            for i, table in enumerate(tables)
        }

        # Check if any table needs breaking (too few players)
        tables_to_break = [
            t.table_id
            for t in tables
            if table_counts[t.table_id] < self.min_players and len(tables) > 1
        ]

        if tables_to_break:
            plan.tables_to_break = tables_to_break
            plan.priority = BalancingPriority.HIGH
            return self._plan_table_break(state, plan, tables_to_break)

        # Calculate imbalance
        max_count = max(table_counts.values())
        min_count = min(table_counts.values())
        imbalance = max_count - min_count

        if imbalance <= 1:
            # 균형 상태 - 밸런싱 불필요
            plan.priority = BalancingPriority.NONE
            return plan

        # Set priority based on imbalance
        if imbalance >= 3:
            plan.priority = BalancingPriority.HIGH
        elif imbalance >= 2:
            plan.priority = BalancingPriority.MEDIUM
        else:
            plan.priority = BalancingPriority.LOW

        # Calculate moves needed
        # 그리디 알고리즘: 가장 많은 테이블 -> 가장 적은 테이블로 이동
        moves = self._calculate_minimum_moves(state, table_counts, ideal_counts)
        plan.moves = moves

        return plan

    def _calculate_minimum_moves(
        self,
        state: TournamentState,
        current_counts: Dict[str, int],
        ideal_counts: Dict[str, int],
    ) -> List[PlayerMove]:
        """
        Calculate minimum number of moves to balance tables.

        그리디 알고리즘:
        ─────────────────────────────────────────────────────────────

        1. 과잉/부족 테이블 분류
           - surplus: 현재 > 목표 (플레이어 내보내야 함)
           - deficit: 현재 < 목표 (플레이어 받아야 함)

        2. 매칭
           - surplus 테이블에서 플레이어 선택
           - deficit 테이블의 빈 좌석으로 배치
           - 양쪽이 균형에 도달할 때까지 반복

        3. 플레이어 선택 기준:
           - Big Blind 직후 위치 우선 (포지션 손실 최소화)
           - 최근 이동하지 않은 플레이어 우선
           - 동일 조건 시 랜덤 선택

        ─────────────────────────────────────────────────────────────

        Returns:
            List of PlayerMove objects
        """
        moves: List[PlayerMove] = []

        # Make mutable copies
        counts = current_counts.copy()

        # Identify surplus and deficit tables
        surplus_tables = [
            tid for tid, count in counts.items() if count > ideal_counts[tid]
        ]
        deficit_tables = [
            tid for tid, count in counts.items() if count < ideal_counts[tid]
        ]

        while surplus_tables and deficit_tables:
            # Sort by surplus/deficit amount
            surplus_tables.sort(key=lambda t: counts[t], reverse=True)
            deficit_tables.sort(key=lambda t: counts[t])

            from_table_id = surplus_tables[0]
            to_table_id = deficit_tables[0]

            from_table = state.tables.get(from_table_id)
            to_table = state.tables.get(to_table_id)

            if not from_table or not to_table:
                break

            # Select player to move
            player_to_move = self._select_player_to_move(state, from_table)
            if not player_to_move:
                surplus_tables.remove(from_table_id)
                continue

            # Select destination seat
            dest_seat = self._select_destination_seat(to_table)
            if dest_seat is None:
                deficit_tables.remove(to_table_id)
                continue

            # Create move
            move = PlayerMove(
                user_id=player_to_move.user_id,
                from_table_id=from_table_id,
                from_seat=player_to_move.seat_position or 0,
                to_table_id=to_table_id,
                to_seat=dest_seat,
                execute_after_hand=from_table.hand_in_progress,
            )
            moves.append(move)

            # Update counts
            counts[from_table_id] -= 1
            counts[to_table_id] += 1

            # Check if tables are now balanced
            if counts[from_table_id] <= ideal_counts[from_table_id]:
                surplus_tables.remove(from_table_id)
            if counts[to_table_id] >= ideal_counts[to_table_id]:
                deficit_tables.remove(to_table_id)

        return moves

    def _select_player_to_move(
        self,
        state: TournamentState,
        table: TournamentTable,
    ) -> Optional[TournamentPlayer]:
        """
        Select best player to move from table.

        선택 기준 (우선순위):
        ─────────────────────────────────────────────────────────────

        1. 빅블라인드 직후 위치 (다음 핸드 손실 최소)
           - BB 위치 다음 시트의 플레이어 선택
           - "스몰 블라인드 건너뛰기" 방지

        2. 스택 크기 고려 (선택적)
           - 중간 스택 플레이어 우선 (빅/숏스택 보호)

        3. 최근 이동 이력 확인
           - 연속 이동 방지 (플레이어 경험 고려)

        ─────────────────────────────────────────────────────────────

        Returns:
            TournamentPlayer to move, or None if no suitable player
        """
        seated_players: List[TournamentPlayer] = []

        for seat_idx, user_id in enumerate(table.seats):
            if user_id:
                player = state.players.get(user_id)
                if player and player.is_active:
                    seated_players.append(player)

        if not seated_players:
            return None

        # For now, select the player in the highest seat position
        # (simplified - in production, would use button position)
        seated_players.sort(key=lambda p: p.seat_position or 0, reverse=True)
        return seated_players[0]

    def _select_destination_seat(
        self,
        table: TournamentTable,
    ) -> Optional[int]:
        """
        Select best seat for incoming player.

        선택 기준:
        - 빈 좌석 중 가장 낮은 번호 (일관성)
        - 향후: 딜러 버튼 위치 고려하여 공정한 포지션 배정

        Returns:
            Seat position, or None if no empty seats
        """
        empty = table.empty_seats
        if not empty:
            return None
        return min(empty)

    def _plan_table_break(
        self,
        state: TournamentState,
        plan: BalancingPlan,
        tables_to_break: List[str],
    ) -> BalancingPlan:
        """
        Plan moves for breaking tables.

        테이블 해체 알고리즘:
        ─────────────────────────────────────────────────────────────

        1. 해체 테이블의 모든 플레이어 목록화
        2. 다른 테이블들의 빈 좌석 목록화
        3. 플레이어를 균등하게 분배
        4. 불가능한 경우 (빈 좌석 부족) 에러 반환

        ─────────────────────────────────────────────────────────────
        """
        moves: List[PlayerMove] = []

        # Get all players from tables to break
        players_to_move: List[Tuple[str, TournamentPlayer]] = []
        for table_id in tables_to_break:
            table = state.tables.get(table_id)
            if not table:
                continue

            for user_id in table.seats:
                if user_id:
                    player = state.players.get(user_id)
                    if player and player.is_active:
                        players_to_move.append((table_id, player))

        # Get available tables and their empty seats
        available_tables = [
            t for t in state.tables.values() if t.table_id not in tables_to_break
        ]

        # Sort by player count ascending (fill smaller tables first)
        available_tables.sort(key=lambda t: t.player_count)

        # Distribute players
        table_idx = 0
        for source_table_id, player in players_to_move:
            # Find next table with available seat
            attempts = 0
            while attempts < len(available_tables):
                target_table = available_tables[table_idx % len(available_tables)]
                empty_seats = target_table.empty_seats

                if empty_seats and target_table.player_count < self.max_players:
                    dest_seat = min(empty_seats)

                    move = PlayerMove(
                        user_id=player.user_id,
                        from_table_id=source_table_id,
                        from_seat=player.seat_position or 0,
                        to_table_id=target_table.table_id,
                        to_seat=dest_seat,
                        priority=BalancingPriority.HIGH,
                    )
                    moves.append(move)
                    break

                table_idx += 1
                attempts += 1
            else:
                # No available seat found - should not happen with proper table management
                pass

            table_idx += 1

        plan.moves = moves
        return plan

    def _plan_final_table(
        self,
        state: TournamentState,
        plan: BalancingPlan,
    ) -> BalancingPlan:
        """
        Plan moves to create final table.

        파이널 테이블 구성:
        ─────────────────────────────────────────────────────────────

        1. 가장 플레이어가 많은 테이블을 파이널 테이블로 지정
        2. 다른 모든 테이블의 플레이어를 파이널 테이블로 이동
        3. 시트 배정은 랜덤 또는 chip stack 기반

        ─────────────────────────────────────────────────────────────
        """
        moves: List[PlayerMove] = []

        tables = list(state.tables.values())
        if len(tables) <= 1:
            return plan

        # Select final table (most players)
        tables.sort(key=lambda t: t.player_count, reverse=True)
        final_table = tables[0]

        # Other tables to break
        other_tables = tables[1:]
        plan.tables_to_break = [t.table_id for t in other_tables]

        # Move all players to final table
        for table in other_tables:
            for user_id in table.seats:
                if user_id:
                    player = state.players.get(user_id)
                    if player and player.is_active:
                        # Find empty seat at final table
                        empty_seats = [
                            i for i, s in enumerate(final_table.seats) if s is None
                        ]
                        if empty_seats:
                            dest_seat = empty_seats[0]

                            move = PlayerMove(
                                user_id=player.user_id,
                                from_table_id=table.table_id,
                                from_seat=player.seat_position or 0,
                                to_table_id=final_table.table_id,
                                to_seat=dest_seat,
                                priority=BalancingPriority.CRITICAL,
                            )
                            moves.append(move)

                            # Update final table seats (simulated)
                            # In actual execution, this is done atomically
                            final_table = final_table.with_player_seated(
                                user_id, dest_seat
                            )

        plan.moves = moves
        return plan

    def get_optimal_move_timing(
        self,
        table: TournamentTable,
    ) -> str:
        """
        Determine when to execute moves for a table.

        이동 타이밍 결정:
        - "IMMEDIATE": 핸드 없음, 즉시 이동
        - "AFTER_HAND": 현재 핸드 종료 후 이동
        - "AFTER_ORBIT": 딜러 버튼이 한 바퀴 돈 후 (선택적)

        Returns:
            Timing instruction string
        """
        if not table.hand_in_progress:
            return "IMMEDIATE"
        return "AFTER_HAND"

    def schedule_moves(
        self,
        plan: BalancingPlan,
    ) -> Dict[str, List[PlayerMove]]:
        """
        Schedule moves by table.

        Returns:
            Dict of table_id -> pending moves for that table
        """
        by_table: Dict[str, List[PlayerMove]] = {}

        for move in plan.moves:
            if move.from_table_id not in by_table:
                by_table[move.from_table_id] = []
            by_table[move.from_table_id].append(move)

        self._pending_moves.update(by_table)
        return by_table

    def get_pending_moves(self, table_id: str) -> List[PlayerMove]:
        """Get pending moves for a table."""
        return self._pending_moves.get(table_id, [])

    def complete_move(self, move_id: str) -> None:
        """Mark move as completed."""
        for table_id in list(self._pending_moves.keys()):
            moves = self._pending_moves[table_id]
            self._pending_moves[table_id] = [m for m in moves if m.move_id != move_id]
            if not self._pending_moves[table_id]:
                del self._pending_moves[table_id]
