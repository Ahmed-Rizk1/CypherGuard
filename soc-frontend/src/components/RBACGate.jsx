/**
 * RBACGate — Role-Based Access Control UI wrapper.
 * Only renders children if the user's role is in the allowed list.
 */
import { useAuth } from '../hooks/AuthContext';

const ROLE_HIERARCHY = { owner: 4, admin: 3, analyst: 2, viewer: 1 };

export default function RBACGate({ allowedRoles = [], minRole = null, children, fallback = null }) {
  const { user } = useAuth();
  if (!user) return fallback;

  if (minRole) {
    const userLevel = ROLE_HIERARCHY[user.role] || 0;
    const minLevel = ROLE_HIERARCHY[minRole] || 0;
    return userLevel >= minLevel ? children : fallback;
  }

  if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    return fallback;
  }

  return children;
}
