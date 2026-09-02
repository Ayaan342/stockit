const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '')
const tokenKey = 'stockit_access_token'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

let unauthorizedHandler: (() => void) | undefined
const cache = new Map<string, { expiresAt: number; value?: Promise<unknown> }>()
const cached = <T>(key: string, loader: () => Promise<T>, ttl = 20_000): Promise<T> => {
  const current = cache.get(key)
  if (current && current.expiresAt > Date.now() && current.value) return current.value as Promise<T>
  const value = loader().catch((error) => { cache.delete(key); throw error })
  cache.set(key, { expiresAt: Date.now() + ttl, value })
  return value
}
const invalidate = (...keys: string[]) => keys.forEach((key) => cache.delete(key))

export function setUnauthorizedHandler(handler: (() => void) | undefined) {
  unauthorizedHandler = handler
}

export function getStoredToken() {
  return localStorage.getItem(tokenKey)
}

export function setStoredToken(token: string) {
  localStorage.setItem(tokenKey, token)
  // Every protected result is scoped to the current identity. A token change
  // must never reuse a prior user's short-lived portfolio/watchlist cache.
  cache.clear()
}

export function clearStoredToken() {
  localStorage.removeItem(tokenKey)
  cache.clear()
}

function errorMessage(payload: unknown): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = payload.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item) => item?.msg ?? 'Invalid input').join(', ')
  }
  return 'Something went wrong. Please try again.'
}

async function request<T>(path: string, options: RequestInit = {}, authenticated = false): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body) headers.set('Content-Type', 'application/json')
  const token = getStoredToken()
  if (authenticated && token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, { ...options, headers })
  } catch {
    throw new ApiError(0, 'Unable to reach the StockIt API. Is the backend running?')
  }

  if (response.status === 401 && authenticated) {
    clearStoredToken()
    unauthorizedHandler?.()
  }
  if (!response.ok) {
    let payload: unknown
    try { payload = await response.json() } catch { payload = undefined }
    throw new ApiError(response.status, errorMessage(payload))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  register: (name: string, email: string, password: string) => request('/auth/register', { method: 'POST', body: JSON.stringify({ name, email, password }) }),
  login: (email: string, password: string) => request<{ access_token: string; token_type: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  // React StrictMode intentionally remounts providers in development. Sharing
  // the in-flight current-user request avoids duplicate logical `/me` calls.
  me: () => cached('me', () => request('/auth/me', {}, true), 30_000),
  stocks: (limit = 50) => request(`/stocks?limit=${limit}`),
  searchStocks: (query: string) => request(`/stocks/search?q=${encodeURIComponent(query)}`),
  stock: (symbol: string, exchange?: string | null) => request(`/stocks/${encodeURIComponent(symbol)}${exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''}`),
  history: (symbol: string, exchange?: string | null) => {
    const listing = `${symbol.toUpperCase()}:${exchange?.toUpperCase() ?? ''}`
    return cached(`stock-history:${listing}`, () => request(`/stocks/${encodeURIComponent(symbol)}/history${exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''}`), 10 * 60_000)
  },
  watchlists: () => cached('watchlists', () => request('/watchlists', {}, true)),
  createWatchlist: async (name: string) => { const result = await request('/watchlists', { method: 'POST', body: JSON.stringify({ name }) }, true); invalidate('watchlists'); return result },
  deleteWatchlist: async (id: number) => { const result = await request(`/watchlists/${id}`, { method: 'DELETE' }, true); invalidate('watchlists'); return result },
  addWatchlistStock: async (id: number, symbol: string, exchange?: string | null) => { const result = await request(`/watchlists/${id}/stocks/${encodeURIComponent(symbol)}${exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''}`, { method: 'POST' }, true); invalidate('watchlists'); return result },
  removeWatchlistStock: async (id: number, symbol: string, exchange?: string | null) => { const result = await request(`/watchlists/${id}/stocks/${encodeURIComponent(symbol)}${exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''}`, { method: 'DELETE' }, true); invalidate('watchlists'); return result },
  portfolio: () => cached('portfolio', () => request('/portfolio', {}, true)),
  holdings: () => cached('holdings', () => request('/portfolio/holdings', {}, true)),
  transactions: () => cached('transactions', () => request('/portfolio/transactions', {}, true)),
  performance: () => request('/portfolio/performance', {}, true),
  portfolioHistory: (currency: string, period: '30d' | '1y') => cached(`portfolio-history:${currency}:${period}`, () => request(`/portfolio/history?currency=${encodeURIComponent(currency)}&period=${period}`, {}, true), 3_600_000),
  trade: async (side: 'buy' | 'sell', payload: { symbol: string; exchange?: string | null; quantity: string; price: string; fees: string; notes?: string; executed_at?: string }) => {
    const result = await request(`/portfolio/${side}`, { method: 'POST', body: JSON.stringify(payload) }, true)
    invalidate('portfolio', 'holdings', 'transactions', 'portfolio-history:INR:30d', 'portfolio-history:INR:1y', 'portfolio-history:USD:30d', 'portfolio-history:USD:1y')
    return result
  },
  invalidatePortfolioData: () => invalidate('portfolio', 'holdings', 'transactions', 'watchlists'),
}
