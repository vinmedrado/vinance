import { lazy, Suspense, type ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { isAuthenticated } from '../services/api';
import { RequireAuth } from '../features/auth/components/RequireAuth';
import { AppLayout } from '../layouts/AppLayout';
import { LoginPage } from '../pages/LoginPage';
import { BootstrapPage } from '../pages/BootstrapPage';
import { InvitationRegistrationPage } from '../pages/InvitationRegistrationPage';
import { PasswordRecoveryPage } from '../pages/PasswordRecoveryPage';
import { PasswordResetPage } from '../pages/PasswordResetPage';
import { RequirePlatformAdmin } from '../features/platform-access/components/RequirePlatformAdmin';
import { FinancialContextProvider } from '../features/household/context/FinancialContextProvider';

const DashboardPage = lazy(() => import('../pages/DashboardPage').then((module) => ({ default: module.DashboardPage })));
const FinancialPage = lazy(() => import('../pages/FinancialPage').then((module) => ({ default: module.FinancialPage })));
const MarketPage = lazy(() => import('../pages/MarketPage').then((module) => ({ default: module.MarketPage })));
const IntelligencePage = lazy(() => import('../pages/IntelligencePage').then((module) => ({ default: module.IntelligencePage })));
const AdvisorPage = lazy(() => import('../pages/AdvisorPage').then((module) => ({ default: module.AdvisorPage })));
const InvestmentWorkspacePage = lazy(() => import('../pages/InvestmentWorkspacePage').then((module) => ({ default: module.InvestmentWorkspacePage })));
const HouseholdPage = lazy(() => import('../pages/HouseholdPage').then((module) => ({ default: module.HouseholdPage })));
const FinancialDataPage = lazy(() => import('../pages/FinancialDataPage').then((module) => ({ default: module.FinancialDataPage })));
const AccountSecurityPage = lazy(() => import('../pages/AccountSecurityPage').then((module) => ({ default: module.AccountSecurityPage })));
const TradingPage = lazy(() => import('../pages/TradingPage').then((module) => ({ default: module.TradingPage })));
const AccountSettingsPage = lazy(() => import('../pages/AccountSettingsPage').then((module) => ({ default: module.AccountSettingsPage })));
const AccessAdministrationPage = lazy(() => import('../pages/AccessAdministrationPage').then((module) => ({ default: module.AccessAdministrationPage })));

function lazyPage(page: ReactNode) {
  return (
    <Suspense fallback={<div className="vn-route-loading" role="status" aria-live="polite">Carregando página…</div>}>
      {page}
    </Suspense>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/access/bootstrap" element={<BootstrapPage />} />
      <Route path="/access/invitation" element={<InvitationRegistrationPage />} />
      <Route path="/access/recover" element={<PasswordRecoveryPage />} />
      <Route path="/access/reset" element={<PasswordResetPage />} />
      <Route path="/" element={<RequireAuth><FinancialContextProvider><AppLayout /></FinancialContextProvider></RequireAuth>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={lazyPage(<DashboardPage />)} />
        <Route path="financial" element={lazyPage(<FinancialPage />)} />
        <Route path="financial/manage" element={lazyPage(<FinancialDataPage />)} />
        <Route path="household" element={lazyPage(<HouseholdPage />)} />
        <Route path="market" element={lazyPage(<MarketPage />)} />
        <Route path="intelligence" element={lazyPage(<IntelligencePage />)} />
        <Route path="investir" element={lazyPage(<InvestmentWorkspacePage />)} />
        <Route path="advisor" element={lazyPage(<AdvisorPage />)} />
        <Route path="account/security" element={lazyPage(<AccountSecurityPage />)} />
        <Route path="account/settings" element={lazyPage(<AccountSettingsPage />)} />
        <Route path="admin/access" element={<RequirePlatformAdmin>{lazyPage(<AccessAdministrationPage />)}</RequirePlatformAdmin>} />
        <Route path="trading" element={lazyPage(<TradingPage />)} />
      </Route>
      <Route path="*" element={<Navigate to={isAuthenticated() ? '/dashboard' : '/login'} replace />} />
    </Routes>
  );
}
