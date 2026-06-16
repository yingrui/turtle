import { Navigate, Route, Routes } from 'react-router-dom';
import { MainLayout } from './components/Layout/MainLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { DataCollection } from './pages/DataCollection';
import { Portfolio } from './pages/Portfolio';
import { Screening } from './pages/Screening';
import { Simulation } from './pages/Simulation';
import { SimulationResults } from './pages/SimulationResults';
import { StockList } from './pages/StockList';
import { StockDetail } from './pages/StockDetail';
import { StockAnalysis } from './pages/StockAnalysis';
import { Forecast } from './pages/Forecast';
import { Jobs } from './pages/Jobs';

export function App() {
  return (
    <Routes>
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
        <Route path="/data" element={<DataCollection />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/screening" element={<Screening />} />
        <Route path="/simulation" element={<Simulation />} />
        <Route path="/simulation/results" element={<SimulationResults />} />
        <Route path="/market" element={<StockList />} />
        <Route path="/stocks/list" element={<StockList />} />
        <Route path="/stocks/:tsCode" element={<StockDetail />} />
        <Route path="/stocks" element={<StockAnalysis />} />
        <Route path="/forecast" element={<Forecast />} />
        <Route path="/jobs" element={<Jobs />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
