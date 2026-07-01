import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import type { Plan } from './auth/AuthContext';
import Home from './Pages/Home';
import Home_by from './Pages/Home_by';
import Dashboard from './Pages/Dashboard';
import DashPage from './Pages/DashPage';
import Validate from './Pages/Validate';
import PublicPage from './Pages/PublicPage';
import * as loginHtml from './auth/html/login';
import * as registerHtml from './auth/html/register';
import * as forgotHtml from './auth/html/forgot';
import * as resetHtml from './auth/html/reset';
import * as verifyHtml from './auth/html/verify';
import * as pricingHtml from './auth/html/pricing';

/* Loaders stables (référence constante) pour chaque page interne :
   ils importent le module porté et exposent sa fonction de montage. */
const discovery = () => import('./dashboard/page-discovery').then((m) => ({ mount: m.mountDiscovery }));
const radar = () => import('./dashboard/page-radar').then((m) => ({ mount: m.mountRadar }));
const trends = () => import('./dashboard/page-trends').then((m) => ({ mount: m.mountTrends }));
const reddit = () => import('./dashboard/page-reddit').then((m) => ({ mount: m.mountReddit }));
const market = () => import('./dashboard/page-market').then((m) => ({ mount: m.mountMarket }));
const analytics = () => import('./dashboard/page-engine').then((m) => ({ mount: m.mountEngine }));
const saved = () => import('./dashboard/page-saved').then((m) => ({ mount: m.mountSaved }));
const watchlists = () => import('./dashboard/page-watch').then((m) => ({ mount: m.mountWatch }));
const alerts = () => import('./dashboard/page-alerts').then((m) => ({ mount: m.mountAlerts }));
const settings = () => import('./dashboard/page-settings').then((m) => ({ mount: m.mountSettings }));
const billing = () => import('./dashboard/page-billing').then((m) => ({ mount: m.mountBilling }));
const account = () => import('./dashboard/page-account').then((m) => ({ mount: m.mountAccount }));

function ProtectedRoute({ children, requirePlan }:
    { children: React.ReactNode; requirePlan?: Plan[] }) {
  const { user, profile, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  // Fail-CLOSED : si aucun plan résolu, on ne suppose JAMAIS un accès payant.
  if (requirePlan) {
    const plan = profile?.plan ?? 'free';
    if (!requirePlan.includes(plan)) return <Navigate to="/pricing" replace />;
  }
  return <>{children}</>;
}

function App() {
  return (
    <AuthProvider>
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/homeby" element={<Home_by />} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/validate" element={<ProtectedRoute requirePlan={['starter', 'pro']}><Validate /></ProtectedRoute>} />

        {/* 12 pages internes du dashboard (shell partagé, protégées) */}
        <Route path="/discovery"  element={<ProtectedRoute><DashPage loader={discovery} /></ProtectedRoute>} />
        <Route path="/radar"      element={<ProtectedRoute><DashPage loader={radar} /></ProtectedRoute>} />
        <Route path="/trends"     element={<ProtectedRoute><DashPage loader={trends} /></ProtectedRoute>} />
        <Route path="/reddit"     element={<ProtectedRoute><DashPage loader={reddit} /></ProtectedRoute>} />
        <Route path="/market"     element={<ProtectedRoute><DashPage loader={market} /></ProtectedRoute>} />
        <Route path="/analytics"  element={<ProtectedRoute><DashPage loader={analytics} /></ProtectedRoute>} />
        <Route path="/saved"      element={<ProtectedRoute><DashPage loader={saved} /></ProtectedRoute>} />
        <Route path="/watchlists" element={<ProtectedRoute><DashPage loader={watchlists} /></ProtectedRoute>} />
        <Route path="/alerts"     element={<ProtectedRoute><DashPage loader={alerts} /></ProtectedRoute>} />
        <Route path="/settings"   element={<ProtectedRoute><DashPage loader={settings} /></ProtectedRoute>} />
        <Route path="/billing"    element={<ProtectedRoute><DashPage loader={billing} /></ProtectedRoute>} />
        <Route path="/account"    element={<ProtectedRoute><DashPage loader={account} /></ProtectedRoute>} />

        {/* pages publiques (pré-login) */}
        <Route path="/login" element={<PublicPage html={loginHtml.html} className={loginHtml.className} auth />} />
        <Route path="/register" element={<PublicPage html={registerHtml.html} className={registerHtml.className} auth />} />
        <Route path="/forgot" element={<PublicPage html={forgotHtml.html} className={forgotHtml.className} auth />} />
        <Route path="/reset" element={<PublicPage html={resetHtml.html} className={resetHtml.className} auth />} />
        <Route path="/verify" element={<PublicPage html={verifyHtml.html} className={verifyHtml.className} auth />} />
        <Route path="/pricing" element={<PublicPage html={pricingHtml.html} className={pricingHtml.className} />} />

        <Route path="*" element={<Home />} />
      </Routes>
    </Router>
    </AuthProvider>
  );
}

export default App;
