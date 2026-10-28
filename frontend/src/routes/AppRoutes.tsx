import { lazy, Suspense, type ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { isAuthenticated } from '../services/api';
import { RequireAuth } from '../features/auth/components/RequireAuth';
import { AppLayout } from '../layouts/AppLayout';
import { LoginPage } from '../pages/LoginPage';

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
      <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
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
        <Route path="trading" element={lazyPage(<TradingPage />)} />
      </Route>
      <Route path="*" element={<Navigate to={isAuthenticated() ? '/dashboard' : '/login'} replace />} />
    </Routes>
  );
}
