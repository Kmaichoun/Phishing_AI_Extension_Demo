'use strict';

const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = relativePath => fs.readFileSync(path.join(root, relativePath), 'utf8').replace(/^\uFEFF/, '');
const exists = relativePath => fs.existsSync(path.join(root, relativePath));
const packageJson = JSON.parse(read('web-app/package.json'));
const index = read('web-app/index.html');
const viteConfig = read('web-app/vite.config.mjs');
const main = read('web-app/src/main.jsx');
const app = read('web-app/src/App.jsx');
const authContext = read('web-app/src/contexts/AuthContext.jsx');
const appContext = read('web-app/src/contexts/AppContext.jsx');
const routerContext = read('web-app/src/contexts/RouterContext.jsx');
const api = read('web-app/src/services/api.js');
const login = read('web-app/src/pages/LoginPage.jsx');
const scanner = read('web-app/src/pages/ScannerPage.jsx');
const qr = read('web-app/src/pages/QrPage.jsx');
const dashboard = read('web-app/src/pages/DashboardPage.jsx');
const settings = read('web-app/src/pages/SettingsPage.jsx');
const theme = read('web-app/src/contexts/ThemeContext.jsx');
const themeToggle = read('web-app/src/components/ThemeToggle.jsx');
const motion = read('web-app/src/components/MotionFrame.jsx');
const fonts = read('web-app/fonts.css');
const styles = read('web-app/professional-ui.css');
const dockitStyles = read('web-app/dockit-theme.css');
const reactStyles = read('web-app/src/react.css');
const manifest = JSON.parse(read('web-app/manifest.webmanifest'));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const dependencies = packageJson.dependencies || {};
assert(dependencies.react, 'React dependency is missing.');
assert(dependencies['react-dom'], 'ReactDOM dependency is missing.');
assert(packageJson.devDependencies?.vite, 'Vite dependency is missing.');
assert(packageJson.scripts?.dev?.includes('vite'), 'Vite development command is missing.');
assert(packageJson.scripts?.build === 'vite build', 'Production build command is missing.');
assert(!dependencies['react-native'] && !dependencies.expo, 'Web App must not use React Native or Expo.');
assert(!dependencies['react-router-dom'], 'Vulnerable React Router package must not be installed.');

assert(index.includes('id="root"'), 'React mount element is missing.');
assert(index.includes('type="module"') && index.includes('./src/main.jsx'), 'React module entry is missing.');
assert(main.includes('createRoot('), 'React createRoot bootstrap is missing.');
assert(main.includes('<RouterProvider>'), 'React hash RouterProvider is missing.');
assert(main.includes('<AuthProvider>') && main.includes('<AppProvider>'), 'React Context providers are missing.');
assert(main.includes('getRegistrations()') && main.includes('phish-radar-web-'), 'Legacy service-worker cache cleanup is missing.');

for (const route of ['/login', '/scan', '/qr', '/dashboard', '/settings', '/methodology', '/status', '/security', '/admin']) {
  assert(app.includes(`path === '${route}'`), `React route ${route} is missing.`);
}
assert(app.includes('<ProtectedRoute>'), 'Protected routes must require an authenticated session.');
assert(app.includes('<AppHeader />'), 'Shared React header is missing.');
assert(routerContext.includes("addEventListener('hashchange'"), 'Hash route synchronization is missing.');
assert(routerContext.includes('function Link('), 'Accessible React Link component is missing.');

for (const pathName of [
  '/auth/health',
  '/auth/me',
  '/auth/login',
  '/auth/register',
  '/auth/profile',
  '/auth/change-password',
  '/auth/logout',
  '/predict',
  '/explain',
  '/feedback',
  '/history'
]) {
  assert(api.includes(pathName), `API client is missing ${pathName}.`);
}
assert(api.includes("credentials: options.credentials ?? 'include'"), 'Auth cookies are not enabled in the API client.');
assert(authContext.includes('createContext(') && authContext.includes('refreshUser'), 'Auth state was not migrated to React Context.');
assert(appContext.includes('createContext(') && appContext.includes('analyzeUrl'), 'Scanner state was not migrated to React Context.');
assert(appContext.includes('Privacy Mode') && appContext.includes('safeHistoryItem'), 'Privacy-safe history behavior is missing.');

assert(login.includes('เข้าสู่ระบบ') && login.includes('สมัครสมาชิก'), 'Login/Register React UI is incomplete.');
assert(scanner.includes('ตรวจสอบลิงก์') && !scanner.includes('hero-primary'), 'Scanner must open directly into the URL task.');
assert(scanner.includes('className="input-row scan-input-row"'), 'Scanner URL field must use the responsive input-row layout.');
assert(!scanner.includes('https://example.com/login'), 'Scanner URL field must not show the retired example URL.');
assert(scanner.includes('FuzzyScore') && scanner.includes('Random Forest'), 'Fuzzy and Random Forest score breakdown is missing.');
assert(scanner.includes('result.riskFormula') && !scanner.includes('FinalScore = 100 × LearnedFusion'), 'Formula must come from the result policy, not hardcoded copy.');
assert(scanner.includes('คำอธิบายจาก LLM'), 'LLM explanation panel is missing.');
assert(qr.includes("from 'jsqr'") && qr.includes('BarcodeDetector'), 'QR fallback and native reader support are missing.');
assert(dashboard.includes('Export CSV') && dashboard.includes('Export JSON'), 'Dashboard exports are missing.');
assert(settings.includes('updateProfile') && settings.includes('changePassword'), 'Account settings actions are missing.');

assert(theme.includes('phishRadarTheme'), 'Theme preference storage is missing.');
assert(themeToggle.includes('theme-icon-sun') && themeToggle.includes('theme-icon-moon'), 'Theme toggle must use sun and moon SVG icons.');
assert(motion.includes("from 'gsap'") && motion.includes('prefers-reduced-motion: reduce'), 'GSAP motion or reduced-motion fallback is missing.');
assert(styles.includes('grid-template-columns: repeat(12, minmax(0, 1fr))'), 'The 12-column layout contract is missing.');
assert(styles.includes('--display-font: "Outfit"'), 'Outfit display font token is missing.');
assert(styles.includes('--editorial-font: "Noto Serif Thai"'), 'Noto Serif Thai editorial token is missing.');
assert(fonts.includes('outfit-latin-400-700.woff2'), 'Local Outfit font is missing.');
assert(fonts.includes('ibm-plex-sans-thai-600.woff2'), 'Local Thai sans font is missing.');
assert(reactStyles.includes('@media (prefers-reduced-motion: reduce)'), 'React reduced-motion CSS is missing.');

assert(manifest.start_url === '/#/login', 'PWA start URL must point to the React login route.');
assert(viteConfig.includes("allowedHosts: ['app.phishradar.localhost']"), 'Local Phish Radar domain is not allowed by Vite.');
assert(viteConfig.includes("return 'react-vendor'"), 'Production bundle splitting is missing.');
assert(app.includes('lazy(() =>') && app.includes('<Suspense'), 'Route-level lazy loading is missing.');
assert(!dockitStyles.includes('.command-palette') && !dockitStyles.includes('.command-trigger'), 'Removed command palette CSS is still present.');

const retiredFiles = [
  'web-app/app.js',
  'web-app/auth.js',
  'web-app/login.html',
  'web-app/settings.html',
  'web-app/settings.js',
  'web-app/server.js',
  'web-app/sw.js',
  'web-app/theme.js',
  'web-app/runtime-config.js',
  'web-app/vendor/gsap.min.js',
  'web-app/vendor/ScrollTrigger.min.js'
];
for (const retiredFile of retiredFiles) {
  assert(!exists(retiredFile), `Retired vanilla file still exists: ${retiredFile}`);
}

const uiSource = [
  index,
  main,
  app,
  login,
  scanner,
  qr,
  dashboard,
  settings,
  themeToggle
].join('\n');
assert(!uiSource.includes('Ctrl K') && !uiSource.includes('Ctrl+K'), 'Removed Ctrl+K UI is still present.');
assert(!/\p{Extended_Pictographic}/u.test(uiSource), 'React Web App source contains an emoji character.');

console.log('React Web App architecture and UI contract tests passed.');
