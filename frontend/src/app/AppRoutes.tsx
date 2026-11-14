import { OverviewPage } from '../features/overview/OverviewPage';
import { HistoryPage } from '../features/scans/HistoryPage';
import { ReportPage } from '../features/scans/ReportPage';
import {
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from 'react-router';
import { ScansPage } from '../features/scans/ScansPage';
import { ProfilePage } from '../features/account/ProfilePage';
import { LoginPage } from '../features/auth/LoginPage';
import { RegisterPage } from '../features/auth/RegisterPage';
import { RequireAuth } from '../features/auth/RequireAuth';
import { WorkspaceLayout } from './WorkspaceLayout';

function PageLayout() {
  return (
    <main className="auth-page">
      <p className="auth-product">Kowalski</p>
      <Outlet />
    </main>
  );
}

function NotFoundPage() {
  return (
    <section>
      <h1>Page not found</h1>
      <Link to="/">Go to home</Link>
    </section>
  );
}

function AccountRedirect() {
  const { search, hash } = useLocation();
  return <Navigate to={{ pathname: '/profile', search, hash }} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route index element={<Navigate to="/dashboard" replace />} />
      <Route path="account" element={<AccountRedirect />} />
      <Route element={<PageLayout />}>
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route element={<RequireAuth />}>
        <Route element={<WorkspaceLayout />}>
          <Route path="dashboard" element={<OverviewPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="scans/:id/report" element={<ReportPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="scans" element={<ScansPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
