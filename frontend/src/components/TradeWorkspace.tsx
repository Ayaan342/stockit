import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Holding, Stock } from '../types/api'
import { TradeRecordForm } from './TradeRecordForm'
import { Empty, ErrorState, Loading } from './Ui'
import { money, number } from '../utils/format'

type TradeSide = 'buy' | 'sell'
const exchanges = ['NSE', 'BSE', 'NASDAQ', 'NYSE']

const fromHolding = (holding: Holding): Stock => ({
  symbol: holding.symbol,
  name: holding.name,
  exchange: holding.exchange,
  currency: holding.currency,
  last_price: holding.current_market_price,
  last_price_updated_at: null,
})

export function TradeWorkspace() {
  const [searchParams] = useSearchParams()
  const initialSide: TradeSide = searchParams.get('side') === 'sell' ? 'sell' : 'buy'
  const [side, setSide] = useState<TradeSide>(initialSide)
  const [exchange, setExchange] = useState(searchParams.get('exchange') ?? 'NSE')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Stock[]>([])
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [stock, setStock] = useState<Stock>()
  const [holding, setHolding] = useState<Holding>()
  const [loadingHoldings, setLoadingHoldings] = useState(true)
  const [searching, setSearching] = useState(false)
  const [quoteLoading, setQuoteLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const searchRequest = useRef(0)

  const refreshHoldings = async () => {
    const owned = await api.holdings() as Holding[]
    setHoldings(owned)
    return owned
  }

  useEffect(() => {
    let active = true
    void api.holdings().then((owned) => {
      if (!active) return
      const items = owned as Holding[]
      setHoldings(items)
      const requestedSymbol = searchParams.get('symbol')
      const requestedExchange = searchParams.get('exchange')
      if (requestedSymbol && side === 'sell') {
        const selectedHolding = items.find((item) => item.symbol === requestedSymbol && (!requestedExchange || item.exchange === requestedExchange))
        if (selectedHolding) {
          setHolding(selectedHolding)
          setStock(fromHolding(selectedHolding))
          setExchange(selectedHolding.exchange)
        }
      }
    }).catch((err) => active && setError(err instanceof ApiError ? err.message : 'Unable to load your holdings.')).finally(() => active && setLoadingHoldings(false))
    return () => { active = false }
  }, [searchParams, side])

  useEffect(() => {
    const term = query.trim()
    if (side !== 'buy' || term.length < 2) return
    const requestId = ++searchRequest.current
    const timer = window.setTimeout(() => {
      setSearching(true)
      setError('')
      void api.searchStocks(term).then((items) => {
        if (requestId !== searchRequest.current) return
        setResults((items as Stock[]).filter((item) => !exchange || item.exchange === exchange))
      }).catch((err) => {
        if (requestId === searchRequest.current) setError(err instanceof ApiError ? err.message : 'Unable to search stocks.')
      }).finally(() => requestId === searchRequest.current && setSearching(false))
    }, 350)
    return () => window.clearTimeout(timer)
  }, [exchange, query, side])

  const selectStock = async (candidate: Stock) => {
    setError('')
    setSuccess('')
    setResults([])
    setQuery('')
    setQuoteLoading(true)
    try {
      const details = await api.stock(candidate.symbol, candidate.exchange) as Stock
      setStock(details)
      setHolding(holdings.find((item) => item.symbol === details.symbol && item.exchange === details.exchange))
      if (details.exchange) setExchange(details.exchange)
    } catch (err) {
      // The listing still gives the user a valid form and manual price entry when a quote is unavailable.
      setStock(candidate)
      setHolding(holdings.find((item) => item.symbol === candidate.symbol && item.exchange === candidate.exchange))
      setError(err instanceof ApiError ? `${err.message} You can still record the actual execution price.` : 'Market price unavailable. You can still record the actual execution price.')
    } finally {
      setQuoteLoading(false)
    }
  }

  const selectHolding = (item: Holding) => {
    setError('')
    setSuccess('')
    setHolding(item)
    setStock(fromHolding(item))
    setExchange(item.exchange)
  }

  const chooseSide = (next: TradeSide) => {
    setSide(next)
    setError('')
    setSuccess('')
    setResults([])
    setQuery('')
    if (next === 'sell' && stock && !holdings.some((item) => item.symbol === stock.symbol && item.exchange === stock.exchange)) {
      setStock(undefined)
      setHolding(undefined)
    }
  }

  const complete = async () => {
    const owned = await refreshHoldings()
    const updatedHolding = stock && owned.find((item) => item.symbol === stock.symbol && item.exchange === stock.exchange)
    setHolding(updatedHolding)
    if (side === 'sell' && !updatedHolding) {
      setStock(undefined)
      setHolding(undefined)
    }
    setSuccess(`${side === 'buy' ? 'Buy' : 'Sell'} transaction recorded. Holdings, portfolio, transactions, and history have been refreshed.`)
  }

  const visibleHoldings = holdings.filter((item) => !exchange || item.exchange === exchange)
  const selectedForSide = stock && (side === 'buy' || holding) ? stock : undefined

  return <section className="trade-page">
    <header className="page-heading trade-heading">
      <div><p className="eyebrow">Portfolio records</p><h1>Buy / Sell</h1><p className="muted">Record transactions from your real brokerage account.</p></div>
    </header>
    <div className="trade-layout trade-layout-v2">
      <article className="panel trade-panel trade-panel-v2">
        <div className="trade-tabs" role="tablist" aria-label="Transaction type">
          <button type="button" role="tab" aria-selected={side === 'buy'} className={side === 'buy' ? 'active buy-tab' : ''} onClick={() => chooseSide('buy')}>Buy</button>
          <button type="button" role="tab" aria-selected={side === 'sell'} className={side === 'sell' ? 'active sell-tab' : ''} onClick={() => chooseSide('sell')}>Sell</button>
        </div>

        <label className="exchange-select">Exchange
          <select value={exchange} onChange={(event) => { setExchange(event.target.value); setResults([]); setError('') }}>
            {exchanges.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>

        {side === 'buy' ? <div className="stock-search">
          <label>Stock
            <input value={query} onChange={(event) => { setQuery(event.target.value); if (event.target.value.trim().length < 2) setResults([]) }} placeholder="Search symbol or company name" autoComplete="off" />
          </label>
          <p className="field-hint">Search {exchange} listings. Results do not request live prices.</p>
          {searching && <p className="search-status">Searching listings…</p>}
          {results.length > 0 && <div className="trade-results trade-results-v2">{results.map((item) => <button type="button" key={`${item.symbol}-${item.exchange}-${item.currency}`} onClick={() => void selectStock(item)}><span><strong>{item.symbol}</strong><small>{item.name}</small></span><span>{item.exchange || '—'} · {item.currency}</span></button>)}</div>}
        </div> : <div className="owned-assets owned-assets-v2">
          <div className="holding-picker-heading"><span>Stock</span><small>Only currently owned positions can be sold.</small></div>
          {loadingHoldings ? <Loading /> : visibleHoldings.length ? <div className="holding-picker">{visibleHoldings.map((item) => <button type="button" key={`${item.symbol}-${item.exchange}`} className={holding?.symbol === item.symbol && holding.exchange === item.exchange ? 'selected' : ''} onClick={() => selectHolding(item)}><span><strong>{item.symbol}</strong><small>{item.name} · {item.exchange}</small></span><span>{number(item.quantity)} owned</span></button>)}</div> : <Empty>No {exchange} shares available to sell.</Empty>}
        </div>}

        {error && <ErrorState message={error} />}
        {success && <p className="trade-success" role="status">{success}</p>}
        {selectedForSide ? <TradeRecordForm key={`${side}-${selectedForSide.symbol}-${selectedForSide.exchange}`} side={side} stock={selectedForSide} holding={holding} quoteLoading={quoteLoading} onComplete={complete} /> : !loadingHoldings && <div className="trade-empty"><Empty>{side === 'buy' ? 'Choose an exact listing to start recording a buy.' : 'Choose one of your owned positions to record a sale.'}</Empty></div>}
      </article>
      <aside className="panel trade-side-note trade-side-note-v2">
        <p className="eyebrow">{side === 'buy' ? 'About this transaction' : 'About this sale'}</p>
        <h2>{side === 'buy' ? 'Record what your broker executed' : 'Keep your portfolio history accurate'}</h2>
        {side === 'buy' ? <ul><li>Enter the actual execution price from your broker.</li><li>Current market price is reference data only.</li><li>Saving updates holdings and portfolio analytics.</li></ul> : <ul><li>Only owned positions can be sold.</li><li>Selling updates remaining quantity and realized P/L.</li><li>Enter the actual price and charges from your broker.</li></ul>}
        {stock && <div className="side-asset-summary"><span>Selected</span><strong>{stock.symbol}</strong><small>{stock.exchange || '—'} · {stock.currency}</small>{stock.last_price && <b>Reference: {money(stock.last_price, stock.currency)}</b>}</div>}
      </aside>
    </div>
  </section>
}
