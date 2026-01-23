import { AdminRole } from '@/types';

/**
 * Permission definitions matching backend ROLE_PERMISSIONS
 * 
 * Sync with: admin-backend/app/utils/permissions.py
 */
type Permission =
  // Dashboard
  | 'view_dashboard'
  | 'view_metrics'
  // Users
  | 'view_users'
  | 'view_user_details'
  | 'ban_users'
  | 'adjust_balance'
  | 'approve_large_adjustment'
  // Rooms
  | 'view_rooms'
  | 'create_room'      // 방 생성 권한 추가
  | 'update_room'      // 방 수정 권한 추가
  | 'delete_room'      // 방 삭제 권한 추가
  | 'force_close_room'
  | 'send_room_message'
  // Hands
  | 'view_hands'
  | 'export_hands'
  // Crypto
  | 'view_deposits'
  | 'view_withdrawals'
  | 'approve_withdrawal'
  | 'approve_large_withdrawal'
  | 'view_wallet'
  // Announcements
  | 'view_announcements'
  | 'create_announcement'
  | 'broadcast_announcement'
  // Maintenance
  | 'view_maintenance'
  | 'schedule_maintenance'
  | 'activate_maintenance'
  // Suspicious
  | 'view_suspicious'
  | 'resolve_suspicious'
  // Audit
  | 'view_audit_logs'
  // Admin Management
  | 'view_admins'
  | 'create_admin'
  | 'modify_admin'
  // Partners
  | 'view_partners'
  | 'create_partner'
  | 'update_partner'
  | 'delete_partner'
  // Settlements
  | 'view_settlements'
  | 'generate_settlement'
  | 'approve_settlement'
  | 'pay_settlement';

const rolePermissions: Record<AdminRole, Permission[]> = {
  [AdminRole.VIEWER]: [
    'view_dashboard',
    'view_metrics',
    'view_users',
    'view_rooms',
    'view_hands',
    'view_deposits',
    'view_withdrawals',
    'view_wallet',
    'view_announcements',
    'view_maintenance',
    'view_suspicious',
    'view_partners',
    'view_settlements',
  ],
  [AdminRole.OPERATOR]: [
    // All viewer permissions
    'view_dashboard',
    'view_metrics',
    'view_users',
    'view_user_details',
    'view_rooms',
    'view_hands',
    'export_hands',
    'view_deposits',
    'view_withdrawals',
    'view_wallet',
    'view_announcements',
    'view_maintenance',
    'view_suspicious',
    'view_partners',
    'view_settlements',
    // Operator-specific
    'ban_users',
    'send_room_message',
    'approve_withdrawal',
    'create_announcement',
    'resolve_suspicious',
    'view_audit_logs',
  ],
  [AdminRole.SUPERVISOR]: [
    // All operator permissions
    'view_dashboard',
    'view_metrics',
    'view_users',
    'view_user_details',
    'ban_users',
    'view_rooms',
    'send_room_message',
    'view_hands',
    'export_hands',
    'view_deposits',
    'view_withdrawals',
    'approve_withdrawal',
    'view_wallet',
    'view_announcements',
    'create_announcement',
    'view_maintenance',
    'view_suspicious',
    'resolve_suspicious',
    'view_audit_logs',
    'view_partners',
    'view_settlements',
    // Supervisor-specific
    'adjust_balance',
    'approve_large_withdrawal',
    'create_room',        // 방 생성 권한
    'update_room',        // 방 수정 권한
    'force_close_room',
    'broadcast_announcement',
    'schedule_maintenance',
    'create_partner',
    'update_partner',
    'generate_settlement',
    'approve_settlement',
  ],
  [AdminRole.ADMIN]: [
    // All permissions
    'view_dashboard',
    'view_metrics',
    'view_users',
    'view_user_details',
    'ban_users',
    'adjust_balance',
    'approve_large_adjustment',
    'view_rooms',
    'create_room',        // 방 생성 권한
    'update_room',        // 방 수정 권한
    'delete_room',        // 방 삭제 권한
    'force_close_room',
    'send_room_message',
    'view_hands',
    'export_hands',
    'view_deposits',
    'view_withdrawals',
    'approve_withdrawal',
    'approve_large_withdrawal',
    'view_wallet',
    'view_announcements',
    'create_announcement',
    'broadcast_announcement',
    'view_maintenance',
    'schedule_maintenance',
    'activate_maintenance',
    'view_suspicious',
    'resolve_suspicious',
    'view_audit_logs',
    'view_admins',
    'create_admin',
    'modify_admin',
    // Partners
    'view_partners',
    'create_partner',
    'update_partner',
    'delete_partner',
    // Settlements
    'view_settlements',
    'generate_settlement',
    'approve_settlement',
    'pay_settlement',
  ],
  // Partner role - 자신의 데이터만 조회 가능 (파트너 포털 전용)
  [AdminRole.PARTNER]: [
    'view_dashboard',
    'view_settlements',
  ],
};

export function hasPermission(role: AdminRole, permission: Permission): boolean {
  return rolePermissions[role]?.includes(permission) ?? false;
}

export function canAccessRoute(role: AdminRole, route: string): boolean {
  // Route to permission mapping
  const routePermissions: Record<string, Permission> = {
    '/': 'view_dashboard',
    '/users': 'view_users',
    '/bans': 'ban_users',
    '/rooms': 'view_rooms',
    '/hands': 'view_hands',
    '/deposits': 'view_deposits',
    '/suspicious': 'view_suspicious',
    '/announcements': 'view_announcements',
    '/maintenance': 'view_maintenance',
    '/audit': 'view_audit_logs',
    '/settings': 'view_admins',
    '/partners': 'view_partners',
    '/settlements': 'view_settlements',
  };

  const permission = routePermissions[route];
  if (!permission) return true;

  return hasPermission(role, permission);
}

/**
 * Get all permissions for a role
 */
export function getRolePermissions(role: AdminRole): Permission[] {
  return rolePermissions[role] ?? [];
}
