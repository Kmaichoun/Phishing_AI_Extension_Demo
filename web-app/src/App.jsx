import { lazy, Suspense } from 'react';
import { AppHeader } from './components/AppHeader';
import { ChatWidget } from './components/ChatWidget';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Redirect, useRouter } from './contexts/RouterContext';

const LoginPage = lazy(() =>
  import('./pages/LoginPage').then(module => ({ default: module.LoginPage }))
);
const ScannerPage = lazy(() =>
  import('./pages/ScannerPage').then(module => ({ default: module.ScannerPage }))
);
const QrPage = lazy(() =>
  import('./pages/QrPage').then(module => ({ default: module.QrPage }))
);
const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then(module => ({ default: module.DashboardPage }))
);
const SettingsPage = lazy(() =>
  import('./pages/SettingsPage').then(module => ({ default: module.SettingsPage }))
);

function PageFallback() {
  return (
    <main className="route-loading" aria-live="polite">
      <span className="route-loading-mark" aria-hidden="true" />
      <p>กำลังเปิดหน้า</p>
    </main>
  );
}

const MethodologyPage = lazy(() => import('./pages/MethodologyPage').then(m => ({ default: m.MethodologyPage })));
const StatusPage = lazy(() => import('./pages/StatusPage').then(m => ({ default: m.StatusPage })));
const SecurityPage = lazy(() => import('./pages/SecurityPage').then(m => ({ default: m.SecurityPage })));
const AdminPage = lazy(() => import('./pages/AdminPage').then(m => ({ default: m.AdminPage })));

function AppShell({ children }) {
  return (
    <>
      <div className="shell workspace-shell">
        <AppHeader />
        <main className="app-main overflow-x-hidden w-full max-w-full">
          {children}
        </main>
        <ChatWidget />
      </div>
    </>
  );
}

function ProtectedAppPage({ children }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}

export default function App() {
  const { path } = useRouter();

  let page;
  if (path === '/login') page = <LoginPage />;
  if (path === '/settings') {
    page = <ProtectedAppPage><SettingsPage /></ProtectedAppPage>;
  }
  if (path === '/scan') {
    page = <ProtectedAppPage><ScannerPage /></ProtectedAppPage>;
  }
  if (path === '/qr') {
    page = <ProtectedAppPage><QrPage /></ProtectedAppPage>;
  }
  if (path === '/dashboard') {
    page = <ProtectedAppPage><DashboardPage /></ProtectedAppPage>;
  }
  if (path === '/methodology') page = <ProtectedAppPage><MethodologyPage /></ProtectedAppPage>;
  if (path === '/status') page = <ProtectedAppPage><StatusPage /></ProtectedAppPage>;
  if (path === '/security') page = <ProtectedAppPage><SecurityPage /></ProtectedAppPage>;
  if (path === '/admin') page = <ProtectedAppPage><AdminPage /></ProtectedAppPage>;
  if (!page) page = <Redirect to="/scan" />;
  return <Suspense fallback={<PageFallback />}>{page}</Suspense>;
}
