"""Tests for admin partner API endpoints - Admin authorization check."""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.models.user import User
from app.models.partner import Partner


class TestAdminPartnerAuthorization:
    """Tests for admin partner API authorization.

    Critical Security Issue: C-1 (관리자 권한 체크 누락, 95% confidence)
    모든 엔드포인트가 관리자 권한을 요구해야 합니다.
    """

    @pytest.mark.asyncio
    async def test_create_partner_without_admin_forbidden(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """일반 유저는 파트너 생성 불가 (403 Forbidden)."""
        data = {
            "userId": str(uuid4()),
            "name": "New Partner",
            "commissionType": "revenue_share",
            "commissionRate": 10,
        }

        response = await test_client.post(
            "/api/v1/admin/partners",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 403
        result = response.json()
        assert result["detail"]["error"]["code"] == "ADMIN_REQUIRED"
        assert "관리자 권한" in result["detail"]["error"]["message"]

    @pytest.mark.asyncio
    async def test_create_partner_with_admin_success(
        self, test_client: AsyncClient, admin_auth_headers: dict
    ):
        """관리자는 파트너 생성 가능."""
        data = {
            "userId": str(uuid4()),
            "name": "Admin Created Partner",
            "commissionType": "revenue_share",
            "commissionRate": 15,
        }

        response = await test_client.post(
            "/api/v1/admin/partners",
            json=data,
            headers=admin_auth_headers,
        )

        # 201 Created or 400 (if user_id doesn't exist)
        assert response.status_code in [201, 400]
        if response.status_code == 201:
            result = response.json()
            assert result["name"] == data["name"]

    @pytest.mark.asyncio
    async def test_list_partners_without_admin_forbidden(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """일반 유저는 파트너 목록 조회 불가."""
        response = await test_client.get(
            "/api/v1/admin/partners",
            headers=auth_headers,
        )

        assert response.status_code == 403
        result = response.json()
        assert result["detail"]["error"]["code"] == "ADMIN_REQUIRED"

    @pytest.mark.asyncio
    async def test_list_partners_with_admin_success(
        self, test_client: AsyncClient, admin_auth_headers: dict, test_partner: Partner
    ):
        """관리자는 파트너 목록 조회 가능."""
        response = await test_client.get(
            "/api/v1/admin/partners",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert "items" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_get_partner_without_admin_forbidden(
        self, test_client: AsyncClient, auth_headers: dict, test_partner: Partner
    ):
        """일반 유저는 파트너 상세 조회 불가."""
        response = await test_client.get(
            f"/api/v1/admin/partners/{test_partner.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_partner_with_admin_success(
        self, test_client: AsyncClient, admin_auth_headers: dict, test_partner: Partner
    ):
        """관리자는 파트너 상세 조회 가능."""
        response = await test_client.get(
            f"/api/v1/admin/partners/{test_partner.id}",
            headers=admin_auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["id"] == test_partner.id
        assert result["name"] == test_partner.name

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint,method",
        [
            ("/api/v1/admin/partners", "POST"),
            ("/api/v1/admin/partners", "GET"),
            ("/api/v1/admin/partners/{id}", "GET"),
            ("/api/v1/admin/partners/{id}", "PATCH"),
            ("/api/v1/admin/partners/{id}", "DELETE"),
            ("/api/v1/admin/partners/{id}/regenerate-code", "POST"),
            ("/api/v1/admin/partners/{id}/referrals", "GET"),
            ("/api/v1/admin/partners/settlements", "GET"),
            ("/api/v1/admin/partners/{id}/settlements", "GET"),
            ("/api/v1/admin/partners/settlements/generate", "POST"),
            ("/api/v1/admin/partners/settlements/{sid}", "PATCH"),
            ("/api/v1/admin/partners/settlements/{sid}/pay", "POST"),
        ],
    )
    async def test_all_endpoints_require_admin(
        self,
        test_client: AsyncClient,
        auth_headers: dict,
        endpoint: str,
        method: str,
        test_partner: Partner,
    ):
        """모든 엔드포인트가 관리자 권한을 요구하는지 확인."""
        # Replace path parameters
        endpoint = endpoint.replace("{id}", test_partner.id)
        endpoint = endpoint.replace("{sid}", str(uuid4()))

        # Make request based on method
        if method == "POST":
            response = await test_client.post(endpoint, json={}, headers=auth_headers)
        elif method == "GET":
            response = await test_client.get(endpoint, headers=auth_headers)
        elif method == "PATCH":
            response = await test_client.patch(endpoint, json={}, headers=auth_headers)
        elif method == "DELETE":
            response = await test_client.delete(endpoint, headers=auth_headers)

        # All should return 403 Forbidden for non-admin users
        assert response.status_code == 403
        result = response.json()
        assert result["detail"]["error"]["code"] == "ADMIN_REQUIRED"

    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(self, test_client: AsyncClient):
        """인증되지 않은 요청은 401 Unauthorized."""
        response = await test_client.get("/api/v1/admin/partners")

        assert response.status_code == 401
        result = response.json()
        assert result["detail"]["error"]["code"] == "AUTH_REQUIRED"
