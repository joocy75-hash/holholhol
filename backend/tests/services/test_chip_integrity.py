"""Chip Integrity Service Tests - 칩 무결성 검증 테스트.

프로덕션 배포 전 필수 테스트:
- ChipSnapshot 무결성 해시 검증
- 칩 보존 법칙 (conservation law) 검증
- 멀티플레이어 칩 분배 정합성
- 레이크 수집 후 칩 합계 검증
- 스냅샷 변조 탐지
"""

import pytest

from app.services.chip_integrity import (
    ChipIntegrityService,
    ChipSnapshot,
    ChipChangeResult,
    get_chip_integrity_service,
)


class TestChipSnapshot:
    """ChipSnapshot 단위 테스트."""

    def test_compute_hash_deterministic(self):
        """같은 데이터로 항상 같은 해시가 생성되어야 함."""
        snapshot = ChipSnapshot(
            table_id="table-1",
            hand_number=1,
            stacks={0: 1000, 1: 2000, 2: 1500},
            total_chips=4500,
        )

        hash1 = snapshot.compute_hash()
        hash2 = snapshot.compute_hash()

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_compute_hash_different_for_different_data(self):
        """다른 데이터는 다른 해시를 생성해야 함."""
        snapshot1 = ChipSnapshot(
            table_id="table-1",
            hand_number=1,
            stacks={0: 1000, 1: 2000},
            total_chips=3000,
        )

        snapshot2 = ChipSnapshot(
            table_id="table-1",
            hand_number=1,
            stacks={0: 1000, 1: 2001},  # 1칩 차이
            total_chips=3001,
        )

        assert snapshot1.compute_hash() != snapshot2.compute_hash()

    def test_verify_hash_success(self):
        """올바른 해시는 검증에 성공해야 함."""
        snapshot = ChipSnapshot(
            table_id="table-1",
            hand_number=1,
            stacks={0: 1000, 1: 2000},
            total_chips=3000,
        )
        snapshot.integrity_hash = snapshot.compute_hash()

        assert snapshot.verify_hash() is True

    def test_verify_hash_fail_on_tampering(self):
        """데이터 변조 시 검증에 실패해야 함."""
        snapshot = ChipSnapshot(
            table_id="table-1",
            hand_number=1,
            stacks={0: 1000, 1: 2000},
            total_chips=3000,
        )
        snapshot.integrity_hash = snapshot.compute_hash()

        # 데이터 변조
        snapshot.stacks[0] = 1500  # 칩 조작 시도

        assert snapshot.verify_hash() is False

    def test_verify_hash_fail_on_total_chips_tampering(self):
        """total_chips 변조 시 검증에 실패해야 함."""
        snapshot = ChipSnapshot(
            table_id="table-1",
            hand_number=1,
            stacks={0: 1000, 1: 2000},
            total_chips=3000,
        )
        snapshot.integrity_hash = snapshot.compute_hash()

        # total_chips 변조
        snapshot.total_chips = 5000

        assert snapshot.verify_hash() is False

    def test_hash_includes_table_id(self):
        """테이블 ID가 해시에 포함되어야 함."""
        snapshot1 = ChipSnapshot(
            table_id="table-1",
            hand_number=1,
            stacks={0: 1000},
            total_chips=1000,
        )

        snapshot2 = ChipSnapshot(
            table_id="table-2",  # 다른 테이블
            hand_number=1,
            stacks={0: 1000},
            total_chips=1000,
        )

        assert snapshot1.compute_hash() != snapshot2.compute_hash()

    def test_hash_includes_hand_number(self):
        """핸드 번호가 해시에 포함되어야 함."""
        snapshot1 = ChipSnapshot(
            table_id="table-1",
            hand_number=1,
            stacks={0: 1000},
            total_chips=1000,
        )

        snapshot2 = ChipSnapshot(
            table_id="table-1",
            hand_number=2,  # 다른 핸드
            stacks={0: 1000},
            total_chips=1000,
        )

        assert snapshot1.compute_hash() != snapshot2.compute_hash()


class TestChipChangeResult:
    """ChipChangeResult 단위 테스트."""

    def test_is_valid_with_zero_discrepancy(self):
        """불일치가 0이면 유효함."""
        result = ChipChangeResult(
            success=True,
            total_before=10000,
            total_after=9500,
            rake_collected=500,
            discrepancy=0,
        )

        assert result.is_valid is True

    def test_is_valid_with_discrepancy(self):
        """불일치가 있으면 유효하지 않음."""
        result = ChipChangeResult(
            success=False,
            total_before=10000,
            total_after=9400,  # 100칩 누락
            rake_collected=500,
            discrepancy=100,
        )

        assert result.is_valid is False


class TestChipIntegrityService:
    """ChipIntegrityService 통합 테스트."""

    @pytest.fixture
    def service(self):
        """각 테스트마다 새로운 서비스 인스턴스 생성."""
        return ChipIntegrityService()

    def test_capture_hand_start_basic(self, service):
        """기본 스냅샷 캡처 테스트."""
        player_stacks = {0: 1000, 1: 2000, 2: 1500}

        snapshot = service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks=player_stacks,
        )

        assert snapshot.table_id == "table-1"
        assert snapshot.hand_number == 1
        assert snapshot.stacks == player_stacks
        assert snapshot.total_chips == 4500
        assert snapshot.integrity_hash != ""
        assert snapshot.verify_hash() is True

    def test_capture_hand_start_stores_snapshot(self, service):
        """스냅샷이 올바르게 저장되어야 함."""
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 1000},
        )

        assert service.has_snapshot("table-1") is True
        assert service.get_snapshot("table-1") is not None

    def test_capture_hand_start_copies_stacks(self, service):
        """스택은 복사본으로 저장되어야 함 (원본 변경 영향 없음)."""
        original_stacks = {0: 1000, 1: 2000}

        snapshot = service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks=original_stacks,
        )

        # 원본 수정
        original_stacks[0] = 5000

        # 스냅샷은 영향 받지 않음
        assert snapshot.stacks[0] == 1000

    def test_validate_hand_completion_success_no_rake(self, service):
        """레이크 없이 칩 보존 검증 성공."""
        # 핸드 시작: 3명 총 4500칩
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 1000, 1: 2000, 2: 1500},
        )

        # 핸드 종료: 플레이어 1이 모두 승리 (레이크 없음)
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 0, 1: 4500, 2: 0},
            rake_collected=0,
        )

        assert result.success is True
        assert result.is_valid is True
        assert result.total_before == 4500
        assert result.total_after == 4500
        assert result.discrepancy == 0

    def test_validate_hand_completion_success_with_rake(self, service):
        """레이크 포함 칩 보존 검증 성공."""
        # 핸드 시작: 10000칩
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 5000, 1: 5000},
        )

        # 핸드 종료: 레이크 500칩 수집
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 9500, 1: 0},
            rake_collected=500,
        )

        assert result.success is True
        assert result.is_valid is True
        assert result.total_before == 10000
        assert result.total_after == 9500
        assert result.rake_collected == 500
        assert result.discrepancy == 0

    def test_validate_hand_completion_fail_chip_mismatch(self, service):
        """칩 불일치 시 검증 실패."""
        # 핸드 시작: 10000칩
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 5000, 1: 5000},
        )

        # 핸드 종료: 칩이 사라짐 (버그 또는 조작)
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 9000, 1: 0},  # 1000칩 누락
            rake_collected=0,
        )

        assert result.success is False
        assert result.is_valid is False
        assert result.discrepancy == 1000
        assert "칩 보존 법칙 위반" in result.error

    def test_validate_hand_completion_fail_extra_chips(self, service):
        """칩이 추가된 경우 검증 실패."""
        # 핸드 시작: 10000칩
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 5000, 1: 5000},
        )

        # 핸드 종료: 칩이 추가됨 (버그 또는 조작)
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 11000, 1: 0},  # 1000칩 추가
            rake_collected=0,
        )

        assert result.success is False
        assert result.discrepancy == 1000

    def test_validate_hand_completion_no_snapshot(self, service):
        """스냅샷 없이 검증 시 실패."""
        result = service.validate_hand_completion(
            table_id="nonexistent",
            final_stacks={0: 5000},
            rake_collected=0,
        )

        assert result.success is False
        assert "스냅샷이 없습니다" in result.error

    def test_validate_hand_completion_clears_snapshot(self, service):
        """검증 후 스냅샷이 정리되어야 함."""
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 1000},
        )

        service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 1000},
            rake_collected=0,
        )

        assert service.has_snapshot("table-1") is False

    def test_multiplayer_chip_distribution_heads_up(self, service):
        """헤즈업(2명) 칩 분배 검증."""
        # 헤즈업 시작
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 5000, 5: 5000},  # 0번, 5번 좌석
        )

        # 플레이어 0이 1000칩 승리
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 6000, 5: 4000},
            rake_collected=0,
        )

        assert result.success is True

    def test_multiplayer_chip_distribution_full_table(self, service):
        """풀 테이블(9명) 칩 분배 검증."""
        # 9명 테이블
        initial_stacks = {i: 10000 for i in range(9)}  # 각 10000칩

        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks=initial_stacks,
        )

        # 플레이어 0이 올인으로 모두 승리, 레이크 2000칩
        final_stacks = {0: 88000}  # 90000 - 2000(rake)
        for i in range(1, 9):
            final_stacks[i] = 0

        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks=final_stacks,
            rake_collected=2000,
        )

        assert result.success is True
        assert result.total_before == 90000
        assert result.total_after == 88000
        assert result.rake_collected == 2000

    def test_split_pot_chip_distribution(self, service):
        """스플릿 팟(동점) 칩 분배 검증."""
        # 2명 올인 동점
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 5000, 1: 5000},
        )

        # 동점으로 팟 분배, 레이크 없음
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 5000, 1: 5000},  # 각자 원래대로
            rake_collected=0,
        )

        assert result.success is True

    def test_split_pot_with_odd_chips(self, service):
        """홀수 칩 스플릿 팟 검증."""
        # 홀수 팟 (1001칩 팟)
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 500, 1: 501},  # 총 1001칩
        )

        # 2명 동점: 500, 501로 분배 (포지션 우선권)
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 500, 1: 501},
            rake_collected=0,
        )

        assert result.success is True

    def test_multiple_tables_independent(self, service):
        """여러 테이블 독립성 검증."""
        # 테이블 1 시작
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 1000},
        )

        # 테이블 2 시작
        service.capture_hand_start(
            table_id="table-2",
            hand_number=1,
            player_stacks={0: 2000},
        )

        # 각 테이블 독립적으로 스냅샷 유지
        assert service.has_snapshot("table-1")
        assert service.has_snapshot("table-2")

        # 테이블 1 완료
        result1 = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 1000},
            rake_collected=0,
        )

        # 테이블 2는 여전히 스냅샷 유지
        assert result1.success is True
        assert not service.has_snapshot("table-1")
        assert service.has_snapshot("table-2")

    def test_clear_snapshot(self, service):
        """스냅샷 수동 정리 테스트."""
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 1000},
        )

        assert service.has_snapshot("table-1")

        service.clear_snapshot("table-1")

        assert not service.has_snapshot("table-1")

    def test_clear_nonexistent_snapshot_no_error(self, service):
        """존재하지 않는 스냅샷 정리 시 에러 없음."""
        service.clear_snapshot("nonexistent")  # 에러 발생하지 않아야 함

    def test_get_all_snapshots(self, service):
        """모든 스냅샷 조회 테스트."""
        service.capture_hand_start("table-1", 1, {0: 1000})
        service.capture_hand_start("table-2", 1, {0: 2000})

        snapshots = service.get_all_snapshots()

        assert len(snapshots) == 2
        assert "table-1" in snapshots
        assert "table-2" in snapshots

    def test_get_all_snapshots_returns_copy(self, service):
        """스냅샷 조회 결과가 복사본인지 확인."""
        service.capture_hand_start("table-1", 1, {0: 1000})

        snapshots = service.get_all_snapshots()
        snapshots["table-new"] = None  # 수정 시도

        # 원본에 영향 없음
        assert "table-new" not in service.get_all_snapshots()

    def test_overwrite_snapshot_on_new_hand(self, service):
        """새 핸드 시작 시 기존 스냅샷 덮어쓰기."""
        # 첫 번째 핸드
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 1000},
        )

        # 두 번째 핸드 (기존 스냅샷 덮어쓰기)
        snapshot = service.capture_hand_start(
            table_id="table-1",
            hand_number=2,
            player_stacks={0: 2000},
        )

        assert snapshot.hand_number == 2
        assert snapshot.stacks[0] == 2000


class TestSingletonInstance:
    """싱글톤 인스턴스 테스트."""

    def test_get_chip_integrity_service_returns_same_instance(self):
        """싱글톤 인스턴스 반환 확인."""
        service1 = get_chip_integrity_service()
        service2 = get_chip_integrity_service()

        assert service1 is service2


class TestEdgeCases:
    """엣지 케이스 테스트."""

    @pytest.fixture
    def service(self):
        return ChipIntegrityService()

    def test_empty_stacks(self, service):
        """빈 스택으로 시작."""
        snapshot = service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={},
        )

        assert snapshot.total_chips == 0

        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={},
            rake_collected=0,
        )

        assert result.success is True

    def test_single_player(self, service):
        """1명 플레이어 시나리오."""
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 10000},
        )

        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 10000},
            rake_collected=0,
        )

        assert result.success is True

    def test_very_large_stacks(self, service):
        """매우 큰 스택 처리."""
        large_stack = 1_000_000_000  # 10억 칩

        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: large_stack, 1: large_stack},
        )

        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: large_stack * 2, 1: 0},
            rake_collected=0,
        )

        assert result.success is True
        assert result.total_before == large_stack * 2

    def test_player_joining_during_hand_detected(self, service):
        """핸드 중 플레이어 추가 시 불일치 감지."""
        # 2명으로 시작
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 5000, 1: 5000},
        )

        # 종료 시 3명 (버그 상황)
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 5000, 1: 5000, 2: 5000},  # 5000칩 추가
            rake_collected=0,
        )

        assert result.success is False
        assert result.discrepancy == 5000

    def test_player_leaving_during_hand_detected(self, service):
        """핸드 중 플레이어 이탈 및 칩 손실 감지."""
        # 3명으로 시작
        service.capture_hand_start(
            table_id="table-1",
            hand_number=1,
            player_stacks={0: 5000, 1: 5000, 2: 5000},
        )

        # 종료 시 2명 (칩 손실)
        result = service.validate_hand_completion(
            table_id="table-1",
            final_stacks={0: 5000, 1: 5000},  # 5000칩 누락
            rake_collected=0,
        )

        assert result.success is False
        assert result.discrepancy == 5000
