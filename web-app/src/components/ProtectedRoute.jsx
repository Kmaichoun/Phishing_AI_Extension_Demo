import { useAuth } from '../contexts/AuthContext';
import { Redirect, useRouter } from '../contexts/RouterContext';

export function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const { path, search } = useRouter();

  if (loading) {
    return (
      <main className="route-loading" aria-live="polite">
        <span className="route-loading-mark" aria-hidden="true" />
        <p>กำลังตรวจสอบ Session</p>
      </main>
    );
  }

  if (!user) {
    const next = `${path}${search}`;
    return <Redirect to={`/login?next=${encodeURIComponent(next)}`} />;
  }

  return children;
}
