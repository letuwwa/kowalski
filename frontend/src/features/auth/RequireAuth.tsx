import { Navigate, Outlet, useLocation } from 'react-router';
import { useAuth } from './authContext';

export function RequireAuth() {
  const { user } = useAuth();
  const { pathname, search, hash } = useLocation();

  return user
    ? <Outlet />
    : <Navigate to="/login" replace state={{ from: `${pathname}${search}${hash}` }} />;
}
