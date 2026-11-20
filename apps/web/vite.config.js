
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8001';
  const proxy = {
    target: proxyTarget,
    changeOrigin: false
  };

  return {
    plugins: [react()],
    server: {
      // Listen on loopback and LAN interfaces. Browser requests remain
      // same-origin and are forwarded by the development proxy.
      host: env.VITE_DEV_HOST || '0.0.0.0',
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': proxy,
        '/health': proxy,
        '/live': proxy,
        '/ready': proxy,
        '/openapi.json': proxy
      }
    }
  };
});
