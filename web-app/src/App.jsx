import { lazy, Suspense } from 'react';
import { AppHeader } from './components/AppHeader';
import { MotionPreloader } from './components/MotionFrame';
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

function AppShell({ children }) {
  return (
    <>
      <MotionPreloader />
      <div className="shell">
        <AppHeader />
        <main className="app-main overflow-x-hidden w-full max-w-full">
          {children}
        </main>
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
    page = <ProtectedRoute><SettingsPage /></ProtectedRoute>;
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
  if (!page) page = <Redirect to="/scan" />;
  return <Suspense fallback={<PageFallback />}>{page}</Suspense>;
}
