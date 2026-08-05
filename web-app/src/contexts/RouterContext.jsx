import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from 'react';

const RouterContext = createContext(null);

function readLocation() {
  const raw = window.location.hash.replace(/^#/, '') || '/scan';
  const [pathPart, ...searchParts] = raw.split('?');
  const path = pathPart.startsWith('/') ? pathPart : `/${pathPart}`;
  const search = searchParts.length ? `?${searchParts.join('?')}` : '';
  return { path, search };
}

export function RouterProvider({ children }) {
  const [location, setLocation] = useState(readLocation);

  useEffect(() => {
    const sync = () => setLocation(readLocation());
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);

  const navigate = useCallback((target, options = {}) => {
    const normalized = target.startsWith('/') ? target : `/${target}`;
    if (options.replace) {
      window.history.replaceState(
        window.history.state,
        '',
        `${window.location.pathname}${window.location.search}#${normalized}`
      );
      setLocation(readLocation());
      return;
    }
    window.location.hash = normalized;
  }, []);

  const value = useMemo(
    () => ({ ...location, navigate }),
    [location, navigate]
  );
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter() {
  const context = useContext(RouterContext);
  if (!context) throw new Error('useRouter must be used inside RouterProvider.');
  return context;
}

export function Link({ to, className = '', children, ...props }) {
  const { path, navigate } = useRouter();
  const targetPath = to.split('?')[0];
  const active = path === targetPath;
  return (
    <a
      href={`#${to}`}
      className={`${className}${active ? `${className ? ' ' : ''}active` : ''}`}
      aria-current={active ? 'page' : undefined}
      onClick={event => {
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) return;
        event.preventDefault();
        navigate(to);
      }}
      {...props}
    >
      {children}
    </a>
  );
}

export function Redirect({ to }) {
  const { navigate } = useRouter();
  useEffect(() => {
    navigate(to, { replace: true });
  }, [navigate, to]);
  return null;
}
