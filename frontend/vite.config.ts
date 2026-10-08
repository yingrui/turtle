import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// VITE_BASE=./ for openKMS / reverse-proxy subpath hosting (see docs/operations/kubernetes.md).
const viteBase =
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env
    ?.VITE_BASE || '/';

export default defineConfig({
  base: viteBase,
  plugins: [react()],
  server: {
    port: 3200,
    proxy: {
      '/api': { target: 'http://localhost:8200', changeOrigin: true },
      '/health': { target: 'http://localhost:8200', changeOrigin: true },
    },
  },
});
