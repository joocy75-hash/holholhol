"""
Hand History API Tests - 핸드 히스토리 API 테스트

**Validates: Phase 3.4 - 핸드 리플레이 기능**
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_main_db
from app.models.admin_user import AdminRole
from app.utils.dependencies import get_current_user


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_viewer_user():
    """Mock viewer user (VIEW_HANDS permission)."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "viewer"
    user.email = "viewer@test.com"
    user.role = AdminRole.viewer
    user.is_active = True
    return user


@pytest.fixture
def mock_operator_user():
    """Mock operator user (VIEW_HANDS + EXPORT_HANDS permissions)."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "operator"
    user.email = "operator@test.com"
    user.role = AdminRole.operator
    user.is_active = True
    return user


@pytest.fixture
def mock_supervisor_user():
    """Mock supervisor user."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "supervisor"
    user.email = "supervisor@test.com"
    user.role = AdminRole.supervisor
    user.is_active = True
    return user


@pytest.fixture
def sample_hand():
    """Sample hand data."""
    return {
        "id": str(uuid4()),
        "table_id": str(uuid4()),
        "hand_number": 42,
        "started_at": datetime(2026, 1, 17, 10, 0, 0),
        "ended_at": datetime(2026, 1, 17, 10, 2, 0),
        "initial_state": {
            "dealer_position": 0,
            "small_blind": 10,
            "big_blind": 20,
            "players": [
                {"seat": 0, "user_id": "user-1", "stack": 1000},
                {"seat": 1, "user_id": "user-2", "stack": 1500},
            ],
        },
        "result": {
            "pot_total": 100,
            "community_cards": ["Ah", "Kd", "Qc", "Js", "Th"],
            "winners": [{"user_id": "user-1", "amount": 100, "seat": 0}],
        },
    }


@pytest.fixture
def sample_participants():
    """Sample participants data."""
    return [
        MagicMock(
            user_id="user-1",
            seat=0,
            hole_cards='["As", "Ad"]',
            bet_amount=50,
            won_amount=100,
            final_action="showdown",
        ),
        MagicMock(
            user_id="user-2",
            seat=1,
            hole_cards='["Kh", "Kc"]',
            bet_amount=50,
            won_amount=0,
            final_action="showdown",
        ),
    ]


@pytest.fixture
def sample_events():
    """Sample events data."""
    return [
        MagicMock(
            seq_no=1,
            event_type="post_blind",
            payload={"seat": 0, "amount": 10, "blind_type": "small"},
            created_at=datetime(2026, 1, 17, 10, 0, 1),
        ),
        MagicMock(
            seq_no=2,
            event_type="post_blind",
            payload={"seat": 1, "amount": 20, "blind_type": "big"},
            created_at=datetime(2026, 1, 17, 10, 0, 2),
        ),
        MagicMock(
            seq_no=3,
            event_type="deal_hole_cards",
            payload={},
            created_at=datetime(2026, 1, 17, 10, 0, 3),
        ),
        MagicMock(
            seq_no=4,
            event_type="call",
            payload={"seat": 0, "amount": 10},
            created_at=datetime(2026, 1, 17, 10, 0, 10),
        ),
        MagicMock(
            seq_no=5,
            event_type="check",
            payload={"seat": 1},
            created_at=datetime(2026, 1, 17, 10, 0, 15),
        ),
        MagicMock(
            seq_no=6,
            event_type="deal_flop",
            payload={"cards": ["Ah", "Kd", "Qc"]},
            created_at=datetime(2026, 1, 17, 10, 0, 20),
        ),
        MagicMock(
            seq_no=7,
            event_type="bet",
            payload={"seat": 0, "amount": 30},
            created_at=datetime(2026, 1, 17, 10, 0, 25),
        ),
        MagicMock(
            seq_no=8,
            event_type="call",
            payload={"seat": 1, "amount": 30},
            created_at=datetime(2026, 1, 17, 10, 0, 30),
        ),
        MagicMock(
            seq_no=9,
            event_type="deal_turn",
            payload={"card": "Js"},
            created_at=datetime(2026, 1, 17, 10, 1, 0),
        ),
        MagicMock(
            seq_no=10,
            event_type="deal_river",
            payload={"card": "Th"},
            created_at=datetime(2026, 1, 17, 10, 1, 30),
        ),
        MagicMock(
            seq_no=11,
            event_type="showdown",
            payload={},
            created_at=datetime(2026, 1, 17, 10, 1, 45),
        ),
        MagicMock(
            seq_no=12,
            event_type="pot_won",
            payload={"seat": 0, "amount": 100},
            created_at=datetime(2026, 1, 17, 10, 2, 0),
        ),
    ]


def create_mock_hand(sample_hand, sample_participants, sample_events):
    """Create a mock Hand object."""
    hand = MagicMock()
    hand.id = sample_hand["id"]
    hand.table_id = sample_hand["table_id"]
    hand.hand_number = sample_hand["hand_number"]
    hand.started_at = sample_hand["started_at"]
    hand.ended_at = sample_hand["ended_at"]
    hand.initial_state = sample_hand["initial_state"]
    hand.result = sample_hand["result"]
    hand.participants = sample_participants
    hand.events = sample_events
    return hand


def create_mock_table(table_id, name="테스트 테이블"):
    """Create a mock Table object."""
    table = MagicMock()
    table.id = table_id
    table.name = name
    table.small_blind = 10
    table.big_blind = 20
    return table


def create_mock_user(user_id, nickname):
    """Create a mock User object."""
    user = MagicMock()
    user.id = user_id
    user.nickname = nickname
    return user


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock()


# ============================================================================
# GET /api/hands Tests (Search/List)
# ============================================================================


class TestSearchHands:
    """GET /api/hands 테스트."""

    def test_search_hands_viewer_access(self, client, mock_viewer_user, mock_db_session):
        """Viewer도 핸드 검색 가능."""
        # Setup mocks
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        hands_result = MagicMock()
        hands_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[count_result, hands_result])

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                "/api/hands",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
        finally:
            app.dependency_overrides.clear()

    def test_search_hands_pagination(self, client, mock_viewer_user, mock_db_session):
        """핸드 검색 페이지네이션."""
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        hands_result = MagicMock()
        hands_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[count_result, hands_result])

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                "/api/hands?page=2&page_size=10",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert data["page_size"] == 10
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# GET /api/hands/{hand_id} Tests (Detail)
# ============================================================================


class TestGetHandDetail:
    """GET /api/hands/{hand_id} 테스트."""

    def test_get_hand_detail_success(
        self, client, mock_viewer_user, mock_db_session,
        sample_hand, sample_participants, sample_events
    ):
        """핸드 상세 조회 성공."""
        hand_id = sample_hand["id"]
        mock_hand = create_mock_hand(sample_hand, sample_participants, sample_events)
        mock_table = create_mock_table(sample_hand["table_id"])

        # Setup mock responses
        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = mock_hand

        table_result = MagicMock()
        table_result.scalar_one_or_none.return_value = mock_table

        users_result = MagicMock()
        mock_users = [
            create_mock_user("user-1", "Player1"),
            create_mock_user("user-2", "Player2"),
        ]
        users_result.scalars.return_value.all.return_value = mock_users

        mock_db_session.execute = AsyncMock(
            side_effect=[hand_result, table_result, users_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()

            # 기본 정보 검증
            assert data["id"] == hand_id
            assert data["table_name"] == "테스트 테이블"
            assert data["hand_number"] == 42

            # 참가자 정보 검증
            assert len(data["participants"]) == 2
            assert data["participants"][0]["seat"] == 0
            assert data["participants"][0]["hole_cards"] == ["As", "Ad"]

            # 타임라인 검증
            assert len(data["timeline"]) == 12
            assert data["timeline"][0]["event_type"] == "post_blind"
            assert data["timeline"][5]["event_type"] == "deal_flop"
            assert data["timeline"][5]["cards"] == ["Ah", "Kd", "Qc"]

            # 결과 검증
            assert data["pot_size"] == 100
            assert data["community_cards"] == ["Ah", "Kd", "Qc", "Js", "Th"]
        finally:
            app.dependency_overrides.clear()

    def test_get_hand_not_found(self, client, mock_viewer_user, mock_db_session):
        """존재하지 않는 핸드 조회."""
        hand_id = str(uuid4())

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=hand_result)

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 404
            assert "핸드를 찾을 수 없습니다" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_get_hand_with_timeline_phases(
        self, client, mock_viewer_user, mock_db_session,
        sample_hand, sample_participants, sample_events
    ):
        """타임라인 페이즈 검증."""
        hand_id = sample_hand["id"]
        mock_hand = create_mock_hand(sample_hand, sample_participants, sample_events)
        mock_table = create_mock_table(sample_hand["table_id"])

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = mock_hand

        table_result = MagicMock()
        table_result.scalar_one_or_none.return_value = mock_table

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[hand_result, table_result, users_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()

            # 페이즈 전환 검증
            phases = [action["phase"] for action in data["timeline"]]
            assert "preflop" in phases
            assert "flop" in phases
            assert "turn" in phases
            assert "river" in phases
            assert "showdown" in phases
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# GET /api/hands/{hand_id}/export Tests
# ============================================================================


class TestExportHand:
    """GET /api/hands/{hand_id}/export 테스트."""

    def test_export_hand_json(
        self, client, mock_operator_user, mock_db_session,
        sample_hand, sample_participants, sample_events
    ):
        """JSON 형식 내보내기."""
        hand_id = sample_hand["id"]
        mock_hand = create_mock_hand(sample_hand, sample_participants, sample_events)
        mock_table = create_mock_table(sample_hand["table_id"])

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = mock_hand

        table_result = MagicMock()
        table_result.scalar_one_or_none.return_value = mock_table

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [
            create_mock_user("user-1", "Player1"),
            create_mock_user("user-2", "Player2"),
        ]

        mock_db_session.execute = AsyncMock(
            side_effect=[hand_result, table_result, users_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_operator_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}/export?format=json",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["format"] == "json"
            assert data["hand_id"] == hand_id
            assert "hand_id" in data["data"]
            assert "participants" in data["data"]
            assert "events" in data["data"]
        finally:
            app.dependency_overrides.clear()

    def test_export_hand_text(
        self, client, mock_operator_user, mock_db_session,
        sample_hand, sample_participants, sample_events
    ):
        """텍스트 형식 내보내기."""
        hand_id = sample_hand["id"]
        mock_hand = create_mock_hand(sample_hand, sample_participants, sample_events)
        mock_table = create_mock_table(sample_hand["table_id"])

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = mock_hand

        table_result = MagicMock()
        table_result.scalar_one_or_none.return_value = mock_table

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = [
            create_mock_user("user-1", "Player1"),
            create_mock_user("user-2", "Player2"),
        ]

        mock_db_session.execute = AsyncMock(
            side_effect=[hand_result, table_result, users_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_operator_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}/export?format=text",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["format"] == "text"
            assert "text" in data["data"]

            # 텍스트 내용 검증
            text = data["data"]["text"]
            assert "Hand #42" in text
            assert "테스트 테이블" in text
            assert "*** PLAYERS ***" in text
            assert "*** ACTIONS ***" in text
            assert "*** FLOP ***" in text
        finally:
            app.dependency_overrides.clear()

    def test_export_hand_viewer_forbidden(self, client, mock_viewer_user):
        """Viewer는 내보내기 불가."""
        hand_id = str(uuid4())

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user

        try:
            response = client.get(
                f"/api/hands/{hand_id}/export",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 403
            assert "EXPORT_HANDS" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_export_hand_not_found(self, client, mock_operator_user, mock_db_session):
        """존재하지 않는 핸드 내보내기."""
        hand_id = str(uuid4())

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=hand_result)

        app.dependency_overrides[get_current_user] = lambda: mock_operator_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}/export",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """헬퍼 함수 테스트."""

    def test_parse_hole_cards_valid(self):
        """유효한 홀카드 파싱."""
        from app.api.hands import _parse_hole_cards

        result = _parse_hole_cards('["As", "Ad"]')
        assert result == ["As", "Ad"]

    def test_parse_hole_cards_none(self):
        """None 홀카드 파싱."""
        from app.api.hands import _parse_hole_cards

        result = _parse_hole_cards(None)
        assert result is None

    def test_parse_hole_cards_invalid(self):
        """잘못된 JSON 홀카드 파싱."""
        from app.api.hands import _parse_hole_cards

        result = _parse_hole_cards("invalid json")
        assert result is None

    def test_extract_phase(self):
        """페이즈 추출 테스트."""
        from app.api.hands import _extract_phase

        assert _extract_phase("deal_hole_cards") == "preflop"
        assert _extract_phase("deal_flop") == "flop"
        assert _extract_phase("deal_turn") == "turn"
        assert _extract_phase("deal_river") == "river"
        assert _extract_phase("showdown") == "showdown"
        assert _extract_phase("hand_end") == "finished"
        assert _extract_phase("call") is None
        assert _extract_phase("bet") is None


# ============================================================================
# Permission Tests
# ============================================================================


class TestHandPermissions:
    """핸드 API 권한 테스트."""

    def test_unauthenticated_access_denied(self, client):
        """인증 없이 접근 불가."""
        response = client.get("/api/hands")
        assert response.status_code in [401, 403]

    def test_viewer_can_view_hands(self, client, mock_viewer_user, mock_db_session):
        """Viewer는 VIEW_HANDS 권한 있음."""
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        hands_result = MagicMock()
        hands_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(side_effect=[count_result, hands_result])

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                "/api/hands",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_operator_can_export_hands(self, client, mock_operator_user, mock_db_session):
        """Operator는 EXPORT_HANDS 권한 있음."""
        hand_id = str(uuid4())

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(return_value=hand_result)

        app.dependency_overrides[get_current_user] = lambda: mock_operator_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}/export",
                headers={"Authorization": "Bearer test-token"},
            )

            # 핸드는 없지만 권한 검사는 통과 (404)
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# Initial State & Result Parsing Tests
# ============================================================================


class TestDataParsing:
    """데이터 파싱 테스트."""

    def test_initial_state_parsing(
        self, client, mock_viewer_user, mock_db_session,
        sample_hand, sample_participants, sample_events
    ):
        """초기 상태 파싱 검증."""
        hand_id = sample_hand["id"]
        mock_hand = create_mock_hand(sample_hand, sample_participants, sample_events)
        mock_table = create_mock_table(sample_hand["table_id"])

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = mock_hand

        table_result = MagicMock()
        table_result.scalar_one_or_none.return_value = mock_table

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[hand_result, table_result, users_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()

            # initial_state 검증
            initial = data["initial_state"]
            assert initial["dealer_position"] == 0
            assert initial["small_blind"] == 10
            assert initial["big_blind"] == 20
            assert len(initial["players"]) == 2
        finally:
            app.dependency_overrides.clear()

    def test_result_parsing(
        self, client, mock_viewer_user, mock_db_session,
        sample_hand, sample_participants, sample_events
    ):
        """결과 파싱 검증."""
        hand_id = sample_hand["id"]
        mock_hand = create_mock_hand(sample_hand, sample_participants, sample_events)
        mock_table = create_mock_table(sample_hand["table_id"])

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = mock_hand

        table_result = MagicMock()
        table_result.scalar_one_or_none.return_value = mock_table

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[hand_result, table_result, users_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()

            # result 검증
            result = data["result"]
            assert result["pot_total"] == 100
            assert result["community_cards"] == ["Ah", "Kd", "Qc", "Js", "Th"]
            assert len(result["winners"]) == 1
        finally:
            app.dependency_overrides.clear()

    def test_participant_net_result(
        self, client, mock_viewer_user, mock_db_session,
        sample_hand, sample_participants, sample_events
    ):
        """참가자 순수익 계산 검증."""
        hand_id = sample_hand["id"]
        mock_hand = create_mock_hand(sample_hand, sample_participants, sample_events)
        mock_table = create_mock_table(sample_hand["table_id"])

        hand_result = MagicMock()
        hand_result.scalar_one_or_none.return_value = mock_hand

        table_result = MagicMock()
        table_result.scalar_one_or_none.return_value = mock_table

        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[hand_result, table_result, users_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
        app.dependency_overrides[get_main_db] = lambda: mock_db_session

        try:
            response = client.get(
                f"/api/hands/{hand_id}",
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()

            # 첫 번째 참가자: won_amount(100) - bet_amount(50) = 50
            assert data["participants"][0]["net_result"] == 50
            # 두 번째 참가자: won_amount(0) - bet_amount(50) = -50
            assert data["participants"][1]["net_result"] == -50
        finally:
            app.dependency_overrides.clear()
