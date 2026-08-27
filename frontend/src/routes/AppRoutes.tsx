import { Navigate, Route, Routes } from 'react-router-dom';
import { isAuthenticated } from '../services/api';
import { RequireAuth } from '../features/auth/components/RequireAuth';
import { AppLayout } from '../layouts/AppLayout';
import { LoginPage } from '../pages/LoginPage';
import { DashboardPage } from '../pages/DashboardPage';
import { FinancialPage } from '../pages/FinancialPage';
import { MarketPage } from '../pages/MarketPage';
import { IntelligencePage } from '../pages/IntelligencePage';
import { AdvisorPage } from '../pages/AdvisorPage';
import { InvestmentWorkspacePage } from '../pages/InvestmentWorkspacePage';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="financial" element={<FinancialPage />} />
        <Route path="market" element={<MarketPage />} />
        <Route path="intelligence" element={<IntelligencePage />} />
        <Route path="investir" element={<InvestmentWorkspacePage />} />
        <Route path="advisor" element={<AdvisorPage />} />
      </Route>
      <Route path="*" element={<Navigate to={isAuthenticated() ? '/dashboard' : '/login'} replace />} />
    </Routes>
  );
}
