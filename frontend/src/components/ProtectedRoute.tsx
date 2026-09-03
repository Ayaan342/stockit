import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export function ProtectedRoute() {
  const { user, loading } = useAuth()
  if (loading) return <div className="screen-message">Loading your workspace…</div>
  return user ? <Outlet /> : <Navigate to="/login" replace />
}
