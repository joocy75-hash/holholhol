from enum import Enum
from typing import Set
from app.models.admin_user import AdminRole


class Permission(str, Enum):
    # Dashboard
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_METRICS = "view_metrics"

    # Users
    VIEW_USERS = "view_users"
    VIEW_USER_DETAILS = "view_user_details"
    BAN_USERS = "ban_users"
    ADJUST_BALANCE = "adjust_balance"
    APPROVE_LARGE_ADJUSTMENT = "approve_large_adjustment"

    # Rooms
    VIEW_ROOMS = "view_rooms"
    CREATE_ROOM = "create_room"
    UPDATE_ROOM = "update_room"
    DELETE_ROOM = "delete_room"
    FORCE_CLOSE_ROOM = "force_close_room"
    SEND_ROOM_MESSAGE = "send_room_message"

    # Hands
    VIEW_HANDS = "view_hands"
    EXPORT_HANDS = "export_hands"

    # Crypto
    VIEW_DEPOSITS = "view_deposits"
    VIEW_WITHDRAWALS = "view_withdrawals"
    APPROVE_WITHDRAWAL = "approve_withdrawal"
    APPROVE_LARGE_WITHDRAWAL = "approve_large_withdrawal"
    VIEW_WALLET = "view_wallet"

    # Announcements
    VIEW_ANNOUNCEMENTS = "view_announcements"
    CREATE_ANNOUNCEMENT = "create_announcement"
    BROADCAST_ANNOUNCEMENT = "broadcast_announcement"

    # Maintenance
    VIEW_MAINTENANCE = "view_maintenance"
    SCHEDULE_MAINTENANCE = "schedule_maintenance"
    ACTIVATE_MAINTENANCE = "activate_maintenance"

    # Suspicious
    VIEW_SUSPICIOUS = "view_suspicious"
    RESOLVE_SUSPICIOUS = "resolve_suspicious"

    # Audit
    VIEW_AUDIT_LOGS = "view_audit_logs"

    # Admin Management
    VIEW_ADMINS = "view_admins"
    CREATE_ADMIN = "create_admin"
    MODIFY_ADMIN = "modify_admin"

    # Partners (총판 관리)
    VIEW_PARTNERS = "view_partners"
    CREATE_PARTNER = "create_partner"
    UPDATE_PARTNER = "update_partner"
    DELETE_PARTNER = "delete_partner"

    # Settlements (정산)
    VIEW_SETTLEMENTS = "view_settlements"
    GENERATE_SETTLEMENT = "generate_settlement"
    APPROVE_SETTLEMENT = "approve_settlement"
    PAY_SETTLEMENT = "pay_settlement"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[AdminRole, Set[Permission]] = {
    AdminRole.viewer: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_METRICS,
        Permission.VIEW_USERS,
        Permission.VIEW_ROOMS,
        Permission.VIEW_HANDS,
        Permission.VIEW_DEPOSITS,
        Permission.VIEW_WITHDRAWALS,
        Permission.VIEW_WALLET,
        Permission.VIEW_ANNOUNCEMENTS,
        Permission.VIEW_MAINTENANCE,
        Permission.VIEW_SUSPICIOUS,
    },
    AdminRole.operator: {
        # All viewer permissions
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_METRICS,
        Permission.VIEW_USERS,
        Permission.VIEW_USER_DETAILS,
        Permission.VIEW_ROOMS,
        Permission.VIEW_HANDS,
        Permission.EXPORT_HANDS,
        Permission.VIEW_DEPOSITS,
        Permission.VIEW_WITHDRAWALS,
        Permission.VIEW_WALLET,
        Permission.VIEW_ANNOUNCEMENTS,
        Permission.VIEW_MAINTENANCE,
        Permission.VIEW_SUSPICIOUS,
        # Operator-specific
        Permission.BAN_USERS,
        Permission.CREATE_ROOM,
        Permission.UPDATE_ROOM,
        Permission.DELETE_ROOM,
        Permission.SEND_ROOM_MESSAGE,
        Permission.APPROVE_WITHDRAWAL,
        Permission.CREATE_ANNOUNCEMENT,
        Permission.RESOLVE_SUSPICIOUS,
        Permission.VIEW_AUDIT_LOGS,
    },
    AdminRole.supervisor: {
        # All operator permissions
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_METRICS,
        Permission.VIEW_USERS,
        Permission.VIEW_USER_DETAILS,
        Permission.BAN_USERS,
        Permission.VIEW_ROOMS,
        Permission.CREATE_ROOM,
        Permission.UPDATE_ROOM,
        Permission.DELETE_ROOM,
        Permission.SEND_ROOM_MESSAGE,
        Permission.VIEW_HANDS,
        Permission.EXPORT_HANDS,
        Permission.VIEW_DEPOSITS,
        Permission.VIEW_WITHDRAWALS,
        Permission.APPROVE_WITHDRAWAL,
        Permission.VIEW_WALLET,
        Permission.VIEW_ANNOUNCEMENTS,
        Permission.CREATE_ANNOUNCEMENT,
        Permission.VIEW_MAINTENANCE,
        Permission.VIEW_SUSPICIOUS,
        Permission.RESOLVE_SUSPICIOUS,
        Permission.VIEW_AUDIT_LOGS,
        # Supervisor-specific
        Permission.ADJUST_BALANCE,
        Permission.APPROVE_LARGE_WITHDRAWAL,
        Permission.FORCE_CLOSE_ROOM,
        Permission.BROADCAST_ANNOUNCEMENT,
        Permission.SCHEDULE_MAINTENANCE,
    },
    AdminRole.admin: {
        # All permissions
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_METRICS,
        Permission.VIEW_USERS,
        Permission.VIEW_USER_DETAILS,
        Permission.BAN_USERS,
        Permission.ADJUST_BALANCE,
        Permission.APPROVE_LARGE_ADJUSTMENT,
        Permission.VIEW_ROOMS,
        Permission.CREATE_ROOM,
        Permission.UPDATE_ROOM,
        Permission.DELETE_ROOM,
        Permission.FORCE_CLOSE_ROOM,
        Permission.SEND_ROOM_MESSAGE,
        Permission.VIEW_HANDS,
        Permission.EXPORT_HANDS,
        Permission.VIEW_DEPOSITS,
        Permission.VIEW_WITHDRAWALS,
        Permission.APPROVE_WITHDRAWAL,
        Permission.APPROVE_LARGE_WITHDRAWAL,
        Permission.VIEW_WALLET,
        Permission.VIEW_ANNOUNCEMENTS,
        Permission.CREATE_ANNOUNCEMENT,
        Permission.BROADCAST_ANNOUNCEMENT,
        Permission.VIEW_MAINTENANCE,
        Permission.SCHEDULE_MAINTENANCE,
        Permission.ACTIVATE_MAINTENANCE,
        Permission.VIEW_SUSPICIOUS,
        Permission.RESOLVE_SUSPICIOUS,
        Permission.VIEW_AUDIT_LOGS,
        Permission.VIEW_ADMINS,
        Permission.CREATE_ADMIN,
        Permission.MODIFY_ADMIN,
        # Partner management
        Permission.VIEW_PARTNERS,
        Permission.CREATE_PARTNER,
        Permission.UPDATE_PARTNER,
        Permission.DELETE_PARTNER,
        # Settlement management
        Permission.VIEW_SETTLEMENTS,
        Permission.GENERATE_SETTLEMENT,
        Permission.APPROVE_SETTLEMENT,
        Permission.PAY_SETTLEMENT,
    },
    # 파트너 역할 - 자신의 데이터만 조회 가능
    AdminRole.partner: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_SETTLEMENTS,  # 자신의 정산 내역만
    },
}


def has_permission(role: AdminRole, permission: Permission) -> bool:
    """Check if a role has a specific permission"""
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_role_permissions(role: AdminRole) -> Set[Permission]:
    """Get all permissions for a role"""
    return ROLE_PERMISSIONS.get(role, set())
