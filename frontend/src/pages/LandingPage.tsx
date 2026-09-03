import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

type IconName = 'portfolio' | 'trade' | 'history' | 'analytics' | 'watchlist' | 'holdings' | 'transactions' | 'shield'

const capabilities: Array<{ icon: IconName; title: string; body: string }> = [
  { icon: 'portfolio', title: 'Portfolio tracking', body: 'Track invested value, current value, allocation, and realized or unrealized P/L.' },
  { icon: 'trade', title: 'Buy / Sell recording', body: 'Record actual execution price, quantity, fees, date, and notes from your broker.' },
  { icon: 'history', title: 'Historical performance', body: 'Review transaction-aware portfolio value across 30-day and 12-month views.' },
  { icon: 'analytics', title: 'Analytics', body: 'Understand allocation, realized versus unrealized P/L, and gain or loss by holding.' },
  { icon: 'watchlist', title: 'Watchlists', body: 'Keep a focused list of equities you want to monitor before recording a trade.' },
  { icon: 'holdings', title: 'Holdings', body: 'See quantity, average cost, current value, allocation, and return in native currency.' },
  { icon: 'transactions', title: 'Transaction ledger', body: 'Keep an immutable record of recorded buys and sells in one place.' },
]

function Reveal({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === 'undefined')

  useEffect(() => {
    const element = ref.current
    if (!element) return
    if (typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) {
        setVisible(true)
        observer.disconnect()
      }
    }, { threshold: 0.12 })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return <div ref={ref} className={`landing-reveal ${visible ? 'landing-reveal-in' : ''} ${className}`}>{children}</div>
}

function LandingIcon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    portfolio: <><path d="M4 20V10m5 10V4m5 16v-7m5 7V7" /><path d="M3 20h18" /></>,
    trade: <><path d="M5 7h14m0 0-3-3m3 3-3 3M19 17H5m0 0 3 3m-3-3 3-3" /></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5M12 7v5l3 2" /></>,
    analytics: <><path d="M4 19V9m5 10V5m5 14v-6m5 6V3" /><path d="M3 20h18" /></>,
    watchlist: <path d="M6 3h12v18l-6-4-6 4V3Z" />,
    holdings: <><path d="M4 7h16v12H4z" /><path d="M8 7V5h8v2m-12 5h16" /></>,
    transactions: <><path d="M5 4h14v16H5z" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
    shield: <><path d="M12 3 4.5 6v5.4c0 4.7 3.1 8 7.5 9.6 4.4-1.6 7.5-4.9 7.5-9.6V6L12 3Z" /><path d="m8.8 12 2.1 2.1 4.4-4.4" /></>,
  }
  return <svg className="landing-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

function Brand() {
  return <Link className="landing-brand" to="/"><span className="landing-brand-mark">S</span><span>StockIt</span></Link>
}

function Ctas({ centered = false }: { centered?: boolean }) {
  return <div className={`landing-ctas ${centered ? 'landing-ctas-centered' : ''}`}>
    <Link className="landing-primary-cta" to="/register">Get started <span aria-hidden="true">→</span></Link>
    <Link className="landing-secondary-cta" to="/login">Sign in</Link>
  </div>
}

function PreviewChart() {
  return <svg className="landing-preview-chart" viewBox="0 0 450 160" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="landing-chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#42c9b6" stopOpacity=".22" /><stop offset="100%" stopColor="#42c9b6" stopOpacity="0" /></linearGradient></defs><path className="landing-chart-grid" d="M0 40H450M0 80H450M0 120H450" /><path d="M0 143 L35 133 L65 136 L101 116 L136 124 L170 101 L202 89 L237 96 L272 70 L308 55 L340 61 L381 38 L418 26 L450 11 L450 160 L0 160 Z" fill="url(#landing-chart-fill)" /><path d="M0 143 L35 133 L65 136 L101 116 L136 124 L170 101 L202 89 L237 96 L272 70 L308 55 L340 61 L381 38 L418 26 L450 11" className="landing-chart-line" /></svg>
}

function AllocationPreview() {
  return <div className="landing-allocation"><div className="landing-donut"><span>Allocation</span></div><div className="landing-preview-legend"><span><i className="dot-a" />NSE equities</span><span><i className="dot-b" />BSE equities</span><span><i className="dot-c" />US equities</span></div></div>
}

function GainLossPreview() {
  return <div className="landing-gain-loss"><div><span>Holding A</span><i className="gain gain-wide" /><b className="positive">+12.4%</b></div><div><span>Holding B</span><i className="gain gain-medium" /><b className="positive">+6.1%</b></div><div><span>Holding C</span><i className="loss loss-medium" /><b className="negative">−3.2%</b></div></div>
}

function DashboardPreview({ compact = false }: { compact?: boolean }) {
  return <div className={`landing-preview ${compact ? 'landing-preview-compact' : ''}`} aria-label="Illustrative StockIt dashboard preview">
    <div className="landing-browser-bar"><span><i /><i /><i /></span><code>app.stockit.io / portfolio</code></div>
    <div className="landing-preview-body">
      <div className="landing-preview-title"><div><strong>Portfolio</strong><small>Illustrative portfolio preview</small></div><div className="landing-preview-market"><b>India · INR</b><span>US · USD</span></div></div>
      <div className="landing-preview-metrics"><div><span>Portfolio value</span><b>₹8,36,420</b></div><div><span>Total invested</span><b>₹7,42,000</b></div><div><span>Total P/L</span><b className="positive">+₹94,420</b></div><div><span>Return</span><b className="positive">+12.72%</b></div></div>
      <div className="landing-preview-grid"><section><header>Portfolio value · 12 months <small>INR</small></header><PreviewChart /></section><section><header>Allocation</header><AllocationPreview /></section></div>
      <section className="landing-preview-gain"><header>Gain / loss by holding <small>unrealized</small></header><GainLossPreview /></section>
    </div>
  </div>
}

function PortfolioShowcase() {
  return <div className="landing-product-panel landing-product-panel-portfolio"><header><span>Portfolio tracking</span><b>Native currency views</b></header><div className="landing-product-stats"><div><small>Portfolio value</small><strong>₹8,36,420</strong></div><div><small>Invested value</small><strong>₹7,42,000</strong></div><div><small>Realized P/L</small><strong className="positive">+₹18,400</strong></div></div><div className="landing-mini-chart"><PreviewChart /></div></div>
}

function AnalyticsShowcase() {
  return <div className="landing-product-panel landing-product-panel-analytics"><header><span>Performance analysis</span><b>Illustrative</b></header><div className="landing-analytics-layout"><div><small>Gain / loss by holding</small><GainLossPreview /></div><AllocationPreview /></div><div className="landing-pnl-split"><span>Realized P/L <b className="positive">+₹18,400</b></span><span>Unrealized P/L <b className="positive">+₹76,020</b></span></div></div>
}

function TransactionsShowcase() {
  return <div className="landing-product-panel landing-product-panel-trade"><header><span>Record transaction</span><b>Buy</b></header><div className="landing-form-preview"><label>Instrument <strong>Selected listing</strong></label><div className="landing-form-row"><label>Exchange <strong>NSE</strong></label><label>Quantity <strong>100</strong></label></div><div className="landing-form-row"><label>Execution price <strong>Recorded by you</strong></label><label>Fees <strong>Optional</strong></label></div><span className="landing-form-preview-button">Record transaction</span></div></div>
}

export function LandingPage() {
  return <div className="landing-page">
    <header className="landing-nav"><div className="landing-shell"><Brand /><nav aria-label="Landing navigation"><a href="#capabilities">Capabilities</a><a href="#how-it-works">How it works</a><a href="#markets">Markets</a></nav><div className="landing-nav-actions"><Link to="/login">Sign in</Link><Link className="landing-nav-cta" to="/register">Get started</Link></div></div></header>
    <main>
      <section className="landing-hero"><div className="landing-shell landing-hero-grid"><Reveal className="landing-hero-copy"><p className="landing-kicker">Portfolio tracker · NSE · BSE · US</p><h1>Track your portfolio with clarity.</h1><p>Record real investment transactions, track NSE, BSE and US equities, and understand portfolio performance over time.</p><Ctas /><small className="landing-scope">Tracking only · StockIt does not execute trades</small></Reveal><Reveal className="landing-hero-preview"><DashboardPreview /></Reveal></div></section>
      <section className="landing-trust-strip"><div className="landing-shell"><span>NSE equities</span><span>BSE equities</span><span>US equities</span><span>Transaction-backed tracking</span><span>Native INR / USD views</span></div></section>
      <section id="capabilities" className="landing-section landing-capabilities"><div className="landing-shell"><Reveal className="landing-section-heading"><p className="landing-kicker">Capabilities</p><h2>Everything you need to understand your portfolio.</h2></Reveal><div className="landing-capability-grid">{capabilities.map((capability) => <Reveal key={capability.title}><article><span className="landing-capability-icon"><LandingIcon name={capability.icon} /></span><h3>{capability.title}</h3><p>{capability.body}</p></article></Reveal>)}</div></div></section>
      <section className="landing-section landing-showcase"><div className="landing-shell"><Reveal className="landing-showcase-intro"><p className="landing-kicker">The product</p><h2>A portfolio workspace built for real positions.</h2><p>StockIt tracks investments you have already made through your broker. It keeps recorded transactions, holdings, performance, and allocation in one focused workspace.</p></Reveal><Reveal className="landing-showcase-preview"><DashboardPreview compact /></Reveal></div></section>
      <section className="landing-section landing-product-sections"><div className="landing-shell"><Reveal className="landing-product-row"><div><p className="landing-kicker">Portfolio tracking</p><h2>See your positions in their native market context.</h2><p>Review holdings, invested value, current value, and realized or unrealized P/L without blending INR and USD portfolios.</p></div><PortfolioShowcase /></Reveal><Reveal className="landing-product-row landing-product-row-reverse"><div><p className="landing-kicker">Analytics</p><h2>Understand allocation and holding-level performance.</h2><p>Use current valuation, gain or loss by holding, and portfolio history to see what is contributing to performance.</p></div><AnalyticsShowcase /></Reveal><Reveal className="landing-product-row"><div><p className="landing-kicker">Record transactions</p><h2>Keep the trade you made, not a broker simulation.</h2><p>Record the actual execution details from your broker. StockIt uses those records to update your holdings and performance.</p></div><TransactionsShowcase /></Reveal></div></section>
      <section id="how-it-works" className="landing-section landing-steps"><div className="landing-shell"><Reveal className="landing-section-heading"><p className="landing-kicker">How it works</p><h2>Three steps from transactions to clarity.</h2></Reveal><ol><li><span>01</span><h3>Record your trades</h3><p>Enter the buys and sells you already completed through your broker.</p></li><li><span>02</span><h3>Track your holdings</h3><p>StockIt reconstructs positions, invested value, and portfolio performance.</p></li><li><span>03</span><h3>Understand performance</h3><p>Use allocation, P/L, history, analytics, and watchlists to monitor investments.</p></li></ol></div></section>
      <section id="markets" className="landing-section landing-markets"><div className="landing-shell landing-markets-grid"><Reveal><p className="landing-kicker">Market coverage</p><h2>Indian and US equities, tracked separately.</h2><p>StockIt supports listings across NSE, BSE, and US markets. INR and USD portfolios stay separate, with no forced base-currency conversion.</p></Reveal><Reveal className="landing-market-list"><div><b>NSE</b><span><strong>National Stock Exchange</strong><small>India · INR</small></span></div><div><b>BSE</b><span><strong>Bombay Stock Exchange</strong><small>India · INR</small></span></div><div><b>US</b><span><strong>US equities</strong><small>United States · USD</small></span></div></Reveal></div></section>
      <section className="landing-section landing-transparency"><div className="landing-shell"><Reveal><article><span><LandingIcon name="shield" /></span><div><p className="landing-kicker">Clear boundaries</p><h2>StockIt tracks investments. It does not execute trades or provide investment advice.</h2><p>Record transactions made through your existing broker, then use StockIt to monitor your holdings, performance, and portfolio analytics.</p></div></article></Reveal></div></section>
      <section className="landing-final"><div className="landing-shell"><Reveal><h2>Your portfolio, clearly understood.</h2><p>Bring recorded trades into one clear view of holdings, performance, and allocation.</p><Ctas centered /></Reveal></div></section>
    </main>
    <footer className="landing-footer"><div className="landing-shell"><div><Brand /><p>An equity portfolio tracker for NSE, BSE, and US listings.</p></div><span>Portfolio tracking · not a broker</span></div></footer>
  </div>
}
