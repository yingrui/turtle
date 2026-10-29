import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, authMode } = useAuth();
  if (isLoading) {
    return <div className="loading-block">Loading…</div>;
  }
  // openKMS iframe / external host: no in-app login gate
  if (authMode === 'none') {
    return <>{children}</>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
