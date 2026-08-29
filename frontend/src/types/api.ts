export interface User {
  id: number
  name: string | null
  email: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface Stock {
  symbol: string
  name: string
  exchange: string | null
  currency: string
  last_price: string | null
  last_price_updated_at: string | null
}

export interface StockHistoryPoint {
  timestamp: string
  close: string
}

export interface Watchlist {
  id: number
  name: string
  created_at: string
  stocks: Stock[]
}

export interface Holding {
  symbol: string
  name: string
  quantity: string
  average_buy_price: string
  current_market_price: string
  invested_value: string
  current_value: string
  profit_loss: string
  profit_loss_percentage: string | null
}

export interface Portfolio {
  portfolio_id: number
  total_invested: string
  current_holdings_value: string
  realized_profit_loss: string
  unrealized_profit_loss: string
  total_portfolio_value: string
  total_profit_loss: string
  profit_loss_percentage: string | null
  day_change: string | null
}

export interface Transaction {
  id: number
  symbol: string
  transaction_type: 'BUY' | 'SELL'
  quantity: string
  price: string
  total_amount: string
  fees: string
  notes: string | null
  executed_at: string
  created_at: string
}

export interface PortfolioPerformancePoint {
  timestamp: string
  portfolio_value: string
}
