import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { PriceChart } from '../components/PriceChart'
import { Empty, Loading } from '../components/Ui'
import type { Stock, StockHistoryPoint } from '../types/api'
import { dateTime, money } from '../utils/format'

function detailError(error: unknown) {
  if (!(error instanceof ApiError)) return 'Unable to load this stock right now.'
  if (error.status === 404) return 'Stock data unavailable'
  if (error.status === 429) return 'Market data limit reached. Please try again later.'
  if (error.status === 503) return 'Market data temporarily unavailable.'
  return error.message
}

function StockError({ message, retry }: { message: string; retry: () => void }) {
  return <section className="stock-error"><p className="eyebrow">Market data</p><h2>{message}</h2><div><button className="secondary" onClick={retry}>Retry</button><Link className="primary" to="/stocks">Back to stocks</Link></div></section>
}

function stockRoute(candidate: Stock) {
  const exchange = candidate.exchange ? `?exchange=${encodeURIComponent(candidate.exchange)}` : ''
  return `/stocks/${encodeURIComponent(candidate.symbol)}${exchange}`
}

export function StocksPage() {
  const [query, setQuery] = useState(''); const [results, setResults] = useState<Stock[]>([]); const [loading, setLoading] = useState(false); const [error, setError] = useState(''); const navigate = useNavigate()
  const search = async (event: FormEvent) => { event.preventDefault(); if (!query.trim()) return; setLoading(true); setError(''); try { setResults(await api.searchStocks(query.trim()) as Stock[]) } catch (err) { setError(detailError(err)) } finally { setLoading(false) } }
  return <><section className="page-heading"><div><p className="eyebrow">Market explorer</p><h1>Find a stock</h1><p className="muted">Search U.S. and supported international listings.</p></div></section><form className="search-form" onSubmit={search}><input aria-label="Search stocks" placeholder="Search AAPL, TCS:NSE, Reliance…" value={query} onChange={(event) => setQuery(event.target.value)} /><button className="primary" disabled={loading}>{loading ? 'Searching…' : 'Search'}</button></form>{error && <section className="stock-error inline"><h2>{error}</h2><button className="secondary" onClick={() => { setError(''); setResults([]) }}>Dismiss</button></section>}{results.length > 0 && <section className="panel search-results"><h2>Results</h2><div className="result-list">{results.map((stock) => <button key={`${stock.symbol}-${stock.exchange}-${stock.currency}`} className="stock-result" onClick={() => navigate(stockRoute(stock))}><span><strong>{stock.symbol}</strong><small>{stock.name}</small></span><span className="result-meta">{stock.exchange || '—'} · {stock.currency}</span></button>)}</div></section>}{!loading && !error && results.length === 0 && <Empty>Search for a stock to see available listings. Quotes are loaded only after you open a stock.</Empty>}</>
}

export function StockDetailPage() {
  const { symbol = '' } = useParams(); const [searchParams] = useSearchParams(); const exchange = searchParams.get('exchange'); const [stock, setStock] = useState<Stock>(); const [history, setHistory] = useState<StockHistoryPoint[]>([]); const [error, setError] = useState<{ listing: string; message: string }>(); const [reload, setReload] = useState(0); const listing = `${symbol.toUpperCase()}:${exchange ?? ''}`
  useEffect(() => { let active = true; Promise.all([api.stock(symbol, exchange), api.history(symbol, exchange)]).then(([s, h]) => { if (!active) return; setStock(s as Stock); setHistory(h as StockHistoryPoint[]); setError(undefined) }).catch((err) => active && setError({ listing, message: detailError(err) })); return () => { active = false } }, [symbol, exchange, listing, reload])
  const currentStock = stock && stock.symbol.toUpperCase() === symbol.toUpperCase() && (!exchange || stock.exchange === exchange) ? stock : undefined
  if (error?.listing === listing) return <StockError message={error.message} retry={() => setReload((value) => value + 1)} />; if (!currentStock) return <Loading />
  return <><Link className="back-link" to="/stocks">← Back to stocks</Link><section className="stock-hero"><div><p className="eyebrow">{currentStock.exchange || 'Exchange'} · {currentStock.currency}</p><h1>{currentStock.symbol}</h1><p className="muted">{currentStock.name}</p></div><div className="price-block"><strong>{currentStock.last_price ? money(currentStock.last_price, currentStock.currency) : 'Price unavailable'}</strong><small>{currentStock.last_price_updated_at ? `Updated ${dateTime(currentStock.last_price_updated_at)}` : 'No timestamp available'}</small></div></section><div className="action-row"><Link className="primary" to={`/trade?side=buy&symbol=${encodeURIComponent(currentStock.symbol)}${currentStock.exchange ? `&exchange=${encodeURIComponent(currentStock.exchange)}` : ''}`}>Add to portfolio</Link><Link className="secondary" to="/watchlists">Add to watchlist</Link></div><section className="panel"><div className="panel-heading"><div><h2>30-day price history</h2><p className="muted">Historical closing prices</p></div></div>{history.length ? <PriceChart history={history} currency={currentStock.currency} /> : <Empty>No historical prices were returned.</Empty>}</section></>
}
