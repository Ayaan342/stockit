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
  exchange: string
  currency: string
  quantity: string
  average_buy_price: string
  current_market_price: string | null
  invested_value: string
  current_value: string | null
  profit_loss: string | null
  profit_loss_percentage: string | null
  allocation_percentage: string | null
}

export interface PortfolioCurrencyGroup {
  currency: string
  market_group: string
  total_invested: string
  current_holdings_value: string | null
  realized_profit_loss: string
  unrealized_profit_loss: string | null
  total_portfolio_value: string | null
  total_profit_loss: string | null
  profit_loss_percentage: string | null
  number_of_assets: number
}

export interface Portfolio {
  portfolio_id: number
  groups: PortfolioCurrencyGroup[]
  total_invested: string | null
  current_holdings_value: string | null
  realized_profit_loss: string | null
  unrealized_profit_loss: string | null
  total_portfolio_value: string | null
  total_profit_loss: string | null
  profit_loss_percentage: string | null
  day_change: string | null
}

export interface Transaction {
  id: number
  symbol: string
  exchange: string
  currency: string
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

export interface PortfolioHistoryPoint { date: string; value: string | null }
export interface PortfolioHistory { currency: string; period: '30d' | '1y'; complete: boolean; points: PortfolioHistoryPoint[] }
