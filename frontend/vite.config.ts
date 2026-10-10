import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * VITE_BASE:
 *  - `/` local mid-dev
 *  - `./` prod nginx build (HashRouter)
 *  - `/api/app-builder/apps/<id>/proxy/` openKMS Apps (JS imports need this
 *    absolute prefix; HTML is forced to `./…` so the K8s API proxy rewriter
 *    does not double-prefix asset URLs)
 */
const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
const viteBase = env?.VITE_BASE || '/';
const proxyTarget = env?.VITE_PROXY_TARGET || 'http://localhost:8200';
const hmrOff = env?.VITE_HMR === '0' || env?.VITE_HMR === 'false';
const proxyBase =
  viteBase.startsWith('/') && viteBase.length > 1 ? (viteBase.endsWith('/') ? viteBase : `${viteBase}/`) : null;

/** openKMS: re-attach stripped proxy prefix for Vite + relative HTML + /-/reload. */
function openkmsDevPlugin(base: string | null): Plugin {
  const prefix = base?.replace(/\/$/, '') ?? '';

  return {
    name: 'openkms-dev',
    transformIndexHtml(html) {
      if (!base) return html;
      const esc = base.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      return html
        .replace(new RegExp(`([\\s](?:src|href)=["'])${esc}`, 'g'), '$1./')
        .replace(new RegExp(`(from\\s+["'])${esc}`, 'g'), '$1./');
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const r = req as { url?: string; method?: string };
        const raw = r.url || '/';
        const path = raw.split('?')[0] ?? '/';
        const search = raw.includes('?') ? raw.slice(raw.indexOf('?')) : '';

        // POST /-/reload — kubernetes dev-sync (WS HMR is not proxied by openKMS)
        if (path === '/-/reload' || path.endsWith('/-/reload')) {
          if (r.method !== 'POST' && r.method !== 'GET') {
            res.statusCode = 405;
            res.end('Method Not Allowed');
            return;
          }
          server.moduleGraph.invalidateAll();
          try {
            server.ws.send({ type: 'full-reload', path: '*' });
          } catch {
            /* hmr may be disabled */
          }
          res.statusCode = 200;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ ok: true }));
          return;
        }

        if (!base) {
          next();
          return;
        }
        if (path.startsWith(base) || path === prefix) {
          next();
          return;
        }
        // Backend API stays unprefixed after openKMS strip.
        if (path.startsWith('/api/') || path.startsWith('/health')) {
          next();
          return;
        }
        const suffix = path === '/' ? '/' : path.startsWith('/') ? path : `/${path}`;
        r.url = `${prefix}${suffix}${search}`;
        next();
      });
    },
  };
}

export default defineConfig({
  base: viteBase === './' ? '/' : viteBase,
  plugins: [react(), openkmsDevPlugin(proxyBase)],
  server: {
    host: true,
    port: 3200,
    allowedHosts: true,
    hmr: hmrOff ? false : undefined,
    proxy: {
      // Turtle API only — never `/api/app-builder/…`.
      '^/api/(auth|data|jobs|portfolios|screening|simulations|stocks|stock-pick)(/|$)': {
        target: proxyTarget,
        changeOrigin: true,
      },
      '/health': { target: proxyTarget, changeOrigin: true },
    },
  },
});
