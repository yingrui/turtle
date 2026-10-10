import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, HashRouter } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider } from './contexts/AuthContext';
import { App } from './App';
import './i18n/config';
import './index.scss';

// Non-root Vite base (openKMS `…/proxy/` or `./`) → HashRouter so document
// path stays under the proxy prefix; relative `api/…` fetches resolve correctly.
const Router = import.meta.env.BASE_URL === '/' ? BrowserRouter : HashRouter;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Router>
      <AuthProvider>
        <App />
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </Router>
  </StrictMode>,
);
