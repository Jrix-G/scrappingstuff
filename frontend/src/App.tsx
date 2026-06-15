import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './Pages/Home';
import Home_by from './Pages/Home_by';
import Dashboard from './Pages/Dashboard';
import DashPage from './Pages/DashPage';
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

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/homeby" element={<Home_by />} />
        <Route path="/dashboard" element={<Dashboard />} />

        {/* 12 pages internes du dashboard (shell partagé) */}
        <Route path="/discovery" element={<DashPage loader={discovery} />} />
        <Route path="/radar" element={<DashPage loader={radar} />} />
        <Route path="/trends" element={<DashPage loader={trends} />} />
        <Route path="/reddit" element={<DashPage loader={reddit} />} />
        <Route path="/market" element={<DashPage loader={market} />} />
        <Route path="/analytics" element={<DashPage loader={analytics} />} />
        <Route path="/saved" element={<DashPage loader={saved} />} />
        <Route path="/watchlists" element={<DashPage loader={watchlists} />} />
        <Route path="/alerts" element={<DashPage loader={alerts} />} />
        <Route path="/settings" element={<DashPage loader={settings} />} />
        <Route path="/billing" element={<DashPage loader={billing} />} />
        <Route path="/account" element={<DashPage loader={account} />} />

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
  );
}

export default App;
