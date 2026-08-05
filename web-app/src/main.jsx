import { StrictMode, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { AppProvider } from './contexts/AppContext';
import { AuthProvider } from './contexts/AuthContext';
import { RouterProvider } from './contexts/RouterContext';
import { ThemeProvider } from './contexts/ThemeContext';
import '../fonts.css';
import '../styles.css';
import '../dockit-theme.css';
import '../auth.css';
import '../settings.css';
import '../professional-ui.css';
import './react.css';

function LegacyCacheCleanup() {
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations()
        .then(registrations => Promise.all(registrations.map(registration => registration.unregister())))
        .catch(() => {});
    }
    if ('caches' in window) {
      caches.keys()
        .then(keys => Promise.all(
          keys
            .filter(key => key.startsWith('phish-radar-web-'))
            .map(key => caches.delete(key))
        ))
        .catch(() => {});
    }
  }, []);
  return null;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <AppProvider>
          <RouterProvider>
            <LegacyCacheCleanup />
            <App />
          </RouterProvider>
        </AppProvider>
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>
);
