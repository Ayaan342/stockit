import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { AllocationDonut } from '../components/AllocationDonut'
import { HoldingPnlChart } from '../components/HoldingPnlChart'
import { ErrorState, Loading, MetricCard } from '../components/Ui'
import { MarketSelector } from '../components/MarketSelector'
import { PortfolioHistoryChart } from '../components/PortfolioHistoryChart'
import type { Holding, Portfolio, PortfolioHistory, Transaction, Watchlist } from '../types/api'
import { dateTime, money, number, pnlClass } from '../utils/format'
import { recentPortfolioHistory } from '../utils/portfolioHistory'

export function DashboardPage() {
  const [portfolio, setPortfolio] = useState<Portfolio>()
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [watchlists, setWatchlists] = useState<Watchlist[]>([])
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [error, setError] = useState('')
  const [selectedCurrency, setSelectedCurrency] = useState('')
  const [growthHistory, setGrowthHistory] = useState<PortfolioHistory>()

  useEffect(() => {
    Promise.all([api.portfolio(), api.holdings(), api.transactions(), api.watchlists()])
      .then(([summary, currentHoldings, activity, lists]) => {
        const portfolioSummary = summary as Portfolio
        setPortfolio(portfolioSummary)
        setSelectedCurrency((current) => current || portfolioSummary.groups[0]?.currency || '')
        setHoldings(currentHoldings as Holding[])
        setTransactions(activity as Transaction[])
        setWatchlists(lists as Watchlist[])
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Unable to load analytics.'))
  }, [])

  useEffect(() => {
    if (!selectedCurrency) return
    let active = true
    // The 1-year ledger series already contains the last 30 calendar days.
    // Fetch it once, then derive the shorter display range locally instead of
    // doubling provider-backed portfolio-history work on dashboard startup.
    api.portfolioHistory(selectedCurrency, '1y')
      .then((growth) => { if (active) setGrowthHistory(growth as PortfolioHistory) })
      .catch(() => {
        if (!active) return
        // Preserve valid data for a refresh of the same market. A first load
        // for another market still receives the existing unavailable state.
        setGrowthHistory((current) => current?.currency === selectedCurrency
          ? current
          : { currency: selectedCurrency, period: '1y', complete: false, points: [] })
      })
    return () => { active = false }
  }, [selectedCurrency])

  const selectMarket = (currency: string) => { setSelectedCurrency(currency) }

  if (error) return <ErrorState message={error} />
  if (!portfolio) return <Loading />

  const activeGroup = portfolio.groups.find((group) => group.currency === selectedCurrency) ?? portfolio.groups[0]
  const activeHoldings = holdings.filter((holding) => holding.currency === activeGroup?.currency)
  const rankedHoldings = [...activeHoldings].filter((holding) => holding.profit_loss !== null).sort((left, right) => Number(right.profit_loss) - Number(left.profit_loss))
  const bestHolding = rankedHoldings[0]
  const worstHolding = rankedHoldings[rankedHoldings.length - 1]
  const chartCurrency = activeGroup?.currency
  const activeGrowthHistory = growthHistory?.currency === activeGroup?.currency ? growthHistory : undefined
  const shortHistory = activeGrowthHistory ? recentPortfolioHistory(activeGrowthHistory, 30) : undefined

  return <>
    <section className="page-heading">
      <div><p className="eyebrow">Portfolio</p><h1>Your portfolio</h1><p className="muted">Current value and transaction-aware market history in each native currency.</p></div>
    </section>
    <MarketSelector markets={portfolio.groups.map((group) => ({ currency: group.currency, market: group.market_group }))} selected={activeGroup?.currency ?? ''} onSelect={selectMarket} />
    {activeGroup && <section><div className="panel-heading"><div><p className="eyebrow">{activeGroup.market_group}</p><h2>{activeGroup.currency} summary</h2></div></div><section className="metric-grid dashboard-metrics">
      <MetricCard featured label="Portfolio value" value={money(activeGroup.total_portfolio_value, activeGroup.currency)} detail={activeGroup.total_portfolio_value === null ? 'Market data unavailable' : 'Current holdings'} />
      <MetricCard label="Holdings value" value={money(activeGroup.current_holdings_value, activeGroup.currency)} />
      <MetricCard label="Total invested" value={money(activeGroup.total_invested, activeGroup.currency)} />
      <MetricCard label="Total P/L" tone={pnlClass(activeGroup.total_profit_loss)} value={money(activeGroup.total_profit_loss, activeGroup.currency)} detail={activeGroup.profit_loss_percentage === null ? 'Market data unavailable' : `${activeGroup.profit_loss_percentage}% overall`} />
    </section></section>}
    <section className="portfolio-chart-grid"><article className="panel portfolio-growth-panel"><div className="panel-heading"><div><p className="eyebrow">Portfolio growth</p><h2>12 months</h2></div></div><PortfolioHistoryChart history={activeGrowthHistory} monthly /></article><article className="panel allocation-panel">
      <div className="panel-heading"><div><h2>Holdings allocation</h2><p className="muted">Current market value by position</p></div></div>
      <AllocationDonut holdings={activeHoldings} currency={activeGroup?.currency} />
    </article></section>
    <section className="dashboard-main">
      <article className="panel performance-panel">
        <div className="panel-heading"><div><h2>Profit & loss</h2><p className="muted">Current backend-calculated valuation</p></div><Link to="/overview">Portfolio</Link></div>
        <dl className="key-values">
          <div><dt>Holdings value</dt><dd>{money(activeGroup?.current_holdings_value, activeGroup?.currency)}</dd></div>
          <div><dt>Realized P/L</dt><dd>{money(activeGroup?.realized_profit_loss, activeGroup?.currency)}</dd></div>
          <div><dt>Unrealized P/L</dt><dd>{money(activeGroup?.unrealized_profit_loss, activeGroup?.currency)}</dd></div>
          <div><dt>Overall return</dt><dd>{activeGroup?.profit_loss_percentage === null ? '—' : `${activeGroup?.profit_loss_percentage}%`}</dd></div>
        </dl>
        {bestHolding && worstHolding && <div className="holding-extremes"><span>Best: <b className={pnlClass(bestHolding.profit_loss)}>{bestHolding.symbol} · {money(bestHolding.profit_loss)}</b></span><span>Lowest: <b className={pnlClass(worstHolding.profit_loss)}>{worstHolding.symbol} · {money(worstHolding.profit_loss)}</b></span></div>}
      </article>
      <article className="panel"><div className="panel-heading"><div><h2>Top holdings</h2><p className="muted">Current value, allocation, and P/L</p></div><Link to="/holdings">View all</Link></div>{activeHoldings.length ? <div className="top-holdings">{[...activeHoldings].sort((a,b) => Number(b.current_value ?? -1) - Number(a.current_value ?? -1)).slice(0,4).map((holding) => <div key={`${holding.symbol}-${holding.exchange}`}><span><strong>{holding.symbol}</strong><small>{holding.exchange}</small></span><b>{money(holding.current_value, holding.currency)}</b><em>{holding.allocation_percentage === null ? '—' : `${holding.allocation_percentage}%`}</em><i className={pnlClass(holding.profit_loss)}>{money(holding.profit_loss, holding.currency)}</i></div>)}</div> : <p className="muted compact-empty">No holdings in this market.</p>}</article>
    </section>
    <section className="panel history-wide-panel"><div className="panel-heading"><div><p className="eyebrow">Portfolio value</p><h2>Last 30 days</h2></div></div><PortfolioHistoryChart history={shortHistory} /></section>
    <section className="dashboard-lower">
      <article className="panel gain-loss-panel"><div className="panel-heading"><div><h2>Gain / loss by holding</h2><p className="muted">{chartCurrency || 'Selected'} holdings only</p></div></div><HoldingPnlChart holdings={activeHoldings} currency={chartCurrency ?? 'USD'} /></article>
      <article className="panel"><div className="panel-heading"><h2>Watchlists</h2><Link to="/watchlists">Manage</Link></div>{watchlists.length ? <ul className="simple-list">{watchlists.slice(0, 4).map((list) => <li key={list.id}><span className="list-mark">{list.name.charAt(0).toUpperCase()}</span><strong>{list.name}</strong><span>{list.stocks.length} stocks</span></li>)}</ul> : <p className="muted">Create a watchlist to keep an eye on stocks.</p>}</article>
      <article className="panel"><div className="panel-heading"><h2>Recent transactions</h2><Link to="/transactions">View all</Link></div>{transactions.length ? <div className="compact-transactions">{transactions.slice(0, 4).map((transaction) => <div key={transaction.id}><span className={`badge ${transaction.transaction_type.toLowerCase()}`}>{transaction.transaction_type}</span><strong>{transaction.symbol} · {transaction.exchange}</strong><span>{number(transaction.quantity)} {Number(transaction.quantity) === 1 ? 'share' : 'shares'}</span><b>{money(transaction.total_amount, transaction.currency)}</b><small>{dateTime(transaction.created_at)}</small></div>)}</div> : <p className="muted">No transactions yet.</p>}</article>
    </section>
  </>
}
