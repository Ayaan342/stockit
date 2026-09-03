import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, clearStoredToken, getStoredToken, setStoredToken, setUnauthorizedHandler } from '../api/client'
import type { User } from '../types/api'
import { AuthContext, type AuthState } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => Boolean(getStoredToken()))

  const logout = useCallback(() => {
    clearStoredToken()
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!getStoredToken()) return () => setUnauthorizedHandler(undefined)
    api.me().then((current) => setUser(current as User)).catch(logout).finally(() => setLoading(false))
    return () => setUnauthorizedHandler(undefined)
  }, [logout])

  const value = useMemo<AuthState>(() => ({
    user,
    loading,
    logout,
    login: async (email, password) => {
      const token = await api.login(email, password)
      setStoredToken(token.access_token)
      setUser(await api.me() as User)
    },
    register: async (name, email, password) => {
      await api.register(name, email, password)
    },
  }), [loading, logout, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
