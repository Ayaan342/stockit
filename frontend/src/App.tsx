import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import { PortfolioPage, TransactionsPage } from './pages/PortfolioPages'
import { StockDetailPage, StocksPage } from './pages/StocksPages'
import { TradePage } from './pages/TradePage'
import { WatchlistsPage } from './pages/WatchlistsPage'
import { DashboardPage } from './pages/DashboardPage'
import { AnalyticsPage } from './pages/AnalyticsPage'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/overview" element={<DashboardPage />} />
          <Route path="/holdings" element={<PortfolioPage />} />
          <Route path="/portfolio" element={<Navigate to="/holdings" replace />} />
          <Route path="/trade" element={<TradePage />} />
          <Route path="/watchlists" element={<WatchlistsPage />} />
          <Route path="/stocks" element={<StocksPage />} />
          <Route path="/stocks/:symbol" element={<StockDetailPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/dashboard" element={<Navigate to="/overview" replace />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/overview" replace />} />
      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  )
}

export default App
