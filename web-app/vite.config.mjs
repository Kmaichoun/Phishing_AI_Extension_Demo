import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5505,
    strictPort: true,
    allowedHosts: ['app.phishradar.localhost']
  },
  preview: {
    host: '127.0.0.1',
    port: 5505,
    strictPort: true,
    allowedHosts: ['app.phishradar.localhost']
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      output: {
        assetFileNames(assetInfo) {
          return assetInfo.names?.includes('icon128.png')
            ? 'assets/icon128.png'
            : 'assets/[name]-[hash][extname]';
        },
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('gsap')) return 'motion';
          if (id.includes('jsqr')) return 'qr-reader';
          if (id.includes('react')) return 'react-vendor';
          return 'vendor';
        }
      }
    }
  }
});
