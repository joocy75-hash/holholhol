import { AdminRole } from '@/types';

type Permission =
  | 'view_dashboard'
  | 'view_users'
  | 'ban_users'
  | 'adjust_balance'
  | 'approve_large_withdrawal'
  | 'manage_rooms'
  | 'view_hands'
  | 'manage_announcements'
  | 'manage_maintenance'
  | 'manage_admins';

const rolePermissions: Record<AdminRole, Permission[]> = {
  [AdminRole.VIEWER]: ['view_dashboard', 'view_users', 'view_hands'],
  [AdminRole.OPERATOR]: [
    'view_dashboard',
    'view_users',
    'ban_users',
    'manage_rooms',
    'view_hands',
    'manage_announcements',
  ],
  [AdminRole.SUPERVISOR]: [
    'view_dashboard',
    'view_users',
    'ban_users',
    'adjust_balance',
    'approve_large_withdrawal',
    'manage_rooms',
    'view_hands',
    'manage_announcements',
    'manage_maintenance',
  ],
  [AdminRole.ADMIN]: [
    'view_dashboard',
    'view_users',
    'ban_users',
    'adjust_balance',
    'approve_large_withdrawal',
    'manage_rooms',
    'view_hands',
    'manage_announcements',
    'manage_maintenance',
    'manage_admins',
  ],
};

export function hasPermission(role: AdminRole, permission: Permission): boolean {
  return rolePermissions[role]?.includes(permission) ?? false;
}

export function canAccessRoute(role: AdminRole, route: string): boolean {
  const routePermissions: Record<string, Permission> = {
    '/': 'view_dashboard',
    '/users': 'view_users',
    '/bans': 'ban_users',
    '/rooms': 'manage_rooms',
    '/hands': 'view_hands',
    '/crypto': 'view_dashboard',
    '/announcements': 'manage_announcements',
    '/maintenance': 'manage_maintenance',
    '/settings': 'manage_admins',
  };

  const permission = routePermissions[route];
  if (!permission) return true;

  return hasPermission(role, permission);
}
