import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, HashRouter } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider } from './contexts/AuthContext';
import { App } from './App';
import './i18n/config';
import './index.scss';

// Relative Vite base (openKMS K8s proxy) needs HashRouter so /api and assets stay under the proxy path.
const Router = import.meta.env.BASE_URL === './' ? HashRouter : BrowserRouter;

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
