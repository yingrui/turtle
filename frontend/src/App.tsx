import { Navigate, Route, Routes } from 'react-router-dom';
import { MainLayout } from './components/Layout/MainLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { DataCollection } from './pages/DataCollection';
import { Portfolio } from './pages/Portfolio';
import { Screening } from './pages/Screening';
import { FactorList } from './pages/FactorList';
import { FactorDetail } from './pages/FactorDetail';
import { Simulation } from './pages/Simulation';
import { SimulationLayout } from './pages/SimulationLayout';
import { SimulationResults } from './pages/SimulationResults';
import { StockList } from './pages/StockList';
import { StockDetail } from './pages/StockDetail';
import { StockAnalysis } from './pages/StockAnalysis';
import { Forecast } from './pages/Forecast';
import { Jobs } from './pages/Jobs';
import { Settings } from './pages/Settings';

export function App() {
  return (
    <Routes>
      {/* Kept for STOCK_AUTH_MODE=local; unused when mode is none (openKMS iframe). */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Home />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/data" element={<DataCollection />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/screening" element={<Screening />} />
        <Route path="/factor" element={<FactorList />} />
        <Route path="/factor/:code" element={<FactorDetail />} />
        <Route path="/watchlist" element={<Navigate to="/portfolio?tab=holdings&status=watching" replace />} />
        <Route path="/simulation" element={<SimulationLayout />}>
          <Route index element={<Simulation />} />
          <Route path="results" element={<SimulationResults />} />
        </Route>
        <Route path="/market" element={<StockList />} />
        <Route path="/stocks/list" element={<Navigate to="/market" replace />} />
        <Route path="/stocks/:tsCode" element={<StockDetail />} />
        <Route path="/stocks" element={<StockAnalysis />} />
        <Route path="/forecast" element={<Forecast />} />
        <Route path="/jobs" element={<Jobs />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
