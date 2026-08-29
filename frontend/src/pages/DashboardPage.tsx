import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { api, ApiError } from '../api/client'
import { ErrorState, Loading, MetricCard } from '../components/Ui'
import type { Holding, Portfolio, Transaction, Watchlist } from '../types/api'
import { dateTime, money, number, pnlClass } from '../utils/format'

const allocationColors = ['#17191e', '#24a687', '#5b6ee1', '#c9952d', '#bd5d66', '#78909c']

export function DashboardPage() {
  const [portfolio, setPortfolio] = useState<Portfolio>()
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [watchlists, setWatchlists] = useState<Watchlist[]>([])
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.portfolio(), api.holdings(), api.transactions(), api.watchlists()])
      .then(([summary, currentHoldings, activity, lists]) => {
        setPortfolio(summary as Portfolio)
        setHoldings(currentHoldings as Holding[])
        setTransactions(activity as Transaction[])
        setWatchlists(lists as Watchlist[])
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Unable to load analytics.'))
  }, [])

  if (error) return <ErrorState message={error} />
  if (!portfolio) return <Loading />

  const allocation = new Set(holdings.map((holding) => holding.currency)).size === 1 && holdings.every((holding) => holding.current_value !== null && holding.allocation_percentage !== null)
    ? holdings.map((holding) => ({ ...holding, value: Number(holding.current_value), percentage: Number(holding.allocation_percentage) })).filter((holding) => holding.value > 0)
    : []
  const rankedHoldings = [...holdings].filter((holding) => holding.profit_loss !== null).sort((left, right) => Number(right.profit_loss) - Number(left.profit_loss))
  const bestHolding = rankedHoldings[0]
  const worstHolding = rankedHoldings[rankedHoldings.length - 1]

  return <>
    <section className="page-heading">
      <div><p className="eyebrow">Analytics</p><h1>Portfolio insights</h1><p className="muted">A real-time summary based on your current portfolio and activity.</p></div>
      <Link className="primary" to="/portfolio">View portfolio</Link>
    </section>
    {portfolio.groups.map((group) => <section key={group.currency}><div className="panel-heading"><div><p className="eyebrow">{group.market_group}</p><h2>{group.currency} summary</h2></div></div><section className="metric-grid dashboard-metrics">
      <MetricCard featured label="Portfolio value" value={money(group.total_portfolio_value, group.currency)} detail={group.total_portfolio_value === null ? 'Market data unavailable' : 'Current holdings'} />
      <MetricCard label="Holdings value" value={money(group.current_holdings_value, group.currency)} />
      <MetricCard label="Total invested" value={money(group.total_invested, group.currency)} />
      <MetricCard label="Total P/L" tone={pnlClass(group.total_profit_loss)} value={money(group.total_profit_loss, group.currency)} detail={group.profit_loss_percentage === null ? 'Market data unavailable' : `${group.profit_loss_percentage}% overall`} />
    </section></section>)}
    <section className="dashboard-main">
      <article className="panel performance-panel">
        <div className="panel-heading"><div><h2>Profit & loss</h2><p className="muted">Current backend-calculated valuation</p></div><Link to="/portfolio">View portfolio</Link></div>
        <dl className="key-values">
          <div><dt>Holdings value</dt><dd>{portfolio.groups.length === 1 ? money(portfolio.groups[0].current_holdings_value, portfolio.groups[0].currency) : 'See currency summaries'}</dd></div>
          <div><dt>Realized P/L</dt><dd>{portfolio.groups.length === 1 ? money(portfolio.groups[0].realized_profit_loss, portfolio.groups[0].currency) : 'See currency summaries'}</dd></div>
          <div><dt>Unrealized P/L</dt><dd>{portfolio.groups.length === 1 ? money(portfolio.groups[0].unrealized_profit_loss, portfolio.groups[0].currency) : '—'}</dd></div>
          <div><dt>Overall return</dt><dd>{portfolio.groups.length === 1 && portfolio.groups[0].profit_loss_percentage !== null ? `${portfolio.groups[0].profit_loss_percentage}%` : '—'}</dd></div>
        </dl>
        {bestHolding && worstHolding && <div className="holding-extremes"><span>Best: <b className={pnlClass(bestHolding.profit_loss)}>{bestHolding.symbol} · {money(bestHolding.profit_loss)}</b></span><span>Lowest: <b className={pnlClass(worstHolding.profit_loss)}>{worstHolding.symbol} · {money(worstHolding.profit_loss)}</b></span></div>}
      </article>
      <article className="panel allocation-panel">
        <div className="panel-heading"><div><h2>Holdings allocation</h2><p className="muted">Based on current holding value</p></div></div>
        {allocation.length ? <>
          <div className="allocation-chart"><ResponsiveContainer width="100%" height={190}><PieChart><Pie data={allocation} dataKey="value" nameKey="symbol" innerRadius={52} outerRadius={76} paddingAngle={2} strokeWidth={0}>{allocation.map((holding, index) => <Cell key={holding.symbol} fill={allocationColors[index % allocationColors.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer><div className="donut-center"><span>Holdings</span><strong>{money(portfolio.current_holdings_value)}</strong></div></div>
          <div className="allocation-legend">{allocation.map((holding, index) => <div key={holding.symbol}><i style={{ background: allocationColors[index % allocationColors.length] }} /><strong>{holding.symbol}</strong><span>{money(holding.current_value)} · {number(holding.percentage)}%</span></div>)}</div>
        </> : <p className="muted compact-empty">{holdings.length ? 'Allocation is shown separately by currency when market data is available.' : 'No holdings yet. Buy stocks to build your allocation.'}</p>}
      </article>
    </section>
    <section className="dashboard-lower">
      <article className="panel"><div className="panel-heading"><h2>Watchlists</h2><Link to="/watchlists">Manage</Link></div>{watchlists.length ? <ul className="simple-list">{watchlists.slice(0, 4).map((list) => <li key={list.id}><span className="list-mark">{list.name.charAt(0).toUpperCase()}</span><strong>{list.name}</strong><span>{list.stocks.length} stocks</span></li>)}</ul> : <p className="muted">Create a watchlist to keep an eye on stocks.</p>}</article>
      <article className="panel"><div className="panel-heading"><h2>Recent transactions</h2><Link to="/transactions">View all</Link></div>{transactions.length ? <div className="compact-transactions">{transactions.slice(0, 4).map((transaction) => <div key={transaction.id}><span className={`badge ${transaction.transaction_type.toLowerCase()}`}>{transaction.transaction_type}</span><strong>{transaction.symbol} · {transaction.exchange}</strong><span>{number(transaction.quantity)} {Number(transaction.quantity) === 1 ? 'share' : 'shares'}</span><b>{money(transaction.total_amount, transaction.currency)}</b><small>{dateTime(transaction.created_at)}</small></div>)}</div> : <p className="muted">No transactions yet.</p>}</article>
    </section>
  </>
}
