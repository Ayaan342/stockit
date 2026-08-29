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

export function setUnauthorizedHandler(handler: (() => void) | undefined) {
  unauthorizedHandler = handler
}

export function getStoredToken() {
  return localStorage.getItem(tokenKey)
}

export function setStoredToken(token: string) {
  localStorage.setItem(tokenKey, token)
}

export function clearStoredToken() {
  localStorage.removeItem(tokenKey)
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
  me: () => request('/auth/me', {}, true),
  stocks: (limit = 50) => request(`/stocks?limit=${limit}`),
  searchStocks: (query: string) => request(`/stocks/search?q=${encodeURIComponent(query)}`),
  stock: (symbol: string, exchange?: string | null) => request(`/stocks/${encodeURIComponent(symbol)}${exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''}`),
  history: (symbol: string, exchange?: string | null) => request(`/stocks/${encodeURIComponent(symbol)}/history${exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''}`),
  watchlists: () => request('/watchlists', {}, true),
  createWatchlist: (name: string) => request('/watchlists', { method: 'POST', body: JSON.stringify({ name }) }, true),
  deleteWatchlist: (id: number) => request(`/watchlists/${id}`, { method: 'DELETE' }, true),
  addWatchlistStock: (id: number, symbol: string, exchange?: string | null) => request(`/watchlists/${id}/stocks/${encodeURIComponent(symbol)}${exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''}`, { method: 'POST' }, true),
  removeWatchlistStock: (id: number, symbol: string, exchange?: string | null) => request(`/watchlists/${id}/stocks/${encodeURIComponent(symbol)}${exchange ? `?exchange=${encodeURIComponent(exchange)}` : ''}`, { method: 'DELETE' }, true),
  portfolio: () => request('/portfolio', {}, true),
  holdings: () => request('/portfolio/holdings', {}, true),
  transactions: () => request('/portfolio/transactions', {}, true),
  performance: () => request('/portfolio/performance', {}, true),
  trade: (side: 'buy' | 'sell', payload: { symbol: string; exchange?: string | null; quantity: string; price: string; fees: string; notes?: string; executed_at?: string }) => request(`/portfolio/${side}`, { method: 'POST', body: JSON.stringify(payload) }, true),
}
