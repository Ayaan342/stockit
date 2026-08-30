import { useMemo, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import type { Holding, Stock } from '../types/api'
import { money, number, pnlClass } from '../utils/format'

type TradeSide = 'buy' | 'sell'

interface TradeRecordFormProps {
  side: TradeSide
  stock: Stock
  holding?: Holding
  quoteLoading: boolean
  onComplete: () => Promise<void> | void
}

const localDateTime = () => {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 16)
}

export function TradeRecordForm({ side, stock, holding, quoteLoading, onComplete }: TradeRecordFormProps) {
  const [quantity, setQuantity] = useState('')
  const [price, setPrice] = useState('')
  const [fees, setFees] = useState('0')
  const [executedAt, setExecutedAt] = useState(localDateTime)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const gross = useMemo(() => Number(quantity || 0) * Number(price || 0), [price, quantity])
  const total = side === 'buy' ? gross + Number(fees || 0) : gross - Number(fees || 0)
  const marketPrice = stock.last_price
  const isSell = side === 'sell'

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (!Number.isFinite(Number(quantity)) || Number(quantity) <= 0) return setError('Enter a quantity greater than zero.')
    if (!Number.isFinite(Number(price)) || Number(price) <= 0) return setError('Enter the actual transaction price.')
    if (!Number.isFinite(Number(fees)) || Number(fees) < 0) return setError('Brokerage / fees cannot be negative.')
    if (isSell && (!holding || Number(quantity) > Number(holding.quantity))) return setError('Quantity exceeds the shares you currently own.')
    if (isSell && total < 0) return setError('Fees cannot exceed the sale proceeds.')
    if (!executedAt) return setError('Choose the date and time of this transaction.')

    setSaving(true)
    try {
      await api.trade(side, {
        symbol: stock.symbol,
        exchange: stock.exchange,
        quantity,
        price,
        fees,
        notes: notes.trim() || undefined,
        executed_at: new Date(executedAt).toISOString(),
      })
      setQuantity('')
      setPrice('')
      setFees('0')
      setNotes('')
      setExecutedAt(localDateTime())
      await onComplete()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to record this transaction.')
    } finally {
      setSaving(false)
    }
  }

  return <form className="trade-record-form" onSubmit={(event) => void submit(event)}>
    <div className="trade-instrument">
      <div>
        <p className="eyebrow">Selected instrument</p>
        <h2>{stock.symbol}</h2>
        <p className="muted">{stock.name}</p>
        <p className="instrument-meta">{stock.exchange || 'Exchange unavailable'} · {stock.currency}</p>
      </div>
      <div className="market-reference">
        <span>Current market price</span>
        {quoteLoading ? <strong className="price-loading">Checking quote…</strong> : marketPrice ? <strong>{money(marketPrice, stock.currency)}</strong> : <><strong>—</strong><small>Market data unavailable</small></>}
        {marketPrice && <button type="button" className="text-button" onClick={() => setPrice(marketPrice)}>Use current price</button>}
      </div>
    </div>

    {isSell && holding && <div className="sale-context">
      <div><span>Owned</span><strong>{number(holding.quantity)} shares</strong></div>
      <div><span>Average cost</span><strong>{money(holding.average_buy_price, holding.currency)}</strong></div>
      <div><span>Unrealized P/L</span><strong className={pnlClass(holding.profit_loss)}>{holding.profit_loss === null ? '—' : money(holding.profit_loss, holding.currency)}</strong></div>
    </div>}

    <div className="trade-fields">
      <label>{isSell ? 'Quantity to sell' : 'Quantity'}
        <input required inputMode="decimal" placeholder="0" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
        {isSell && holding && Number(quantity || 0) > Number(holding.quantity) && <small className="field-error">You own {number(holding.quantity)} shares.</small>}
      </label>
      <label>{isSell ? 'Actual sell price' : 'Price per share'}
        <input required inputMode="decimal" placeholder="0.00" value={price} onChange={(event) => setPrice(event.target.value)} />
      </label>
      <label>Brokerage / Fees
        <input required inputMode="decimal" value={fees} onChange={(event) => setFees(event.target.value)} />
      </label>
      <label>Transaction date / time
        <input required type="datetime-local" value={executedAt} onChange={(event) => setExecutedAt(event.target.value)} />
      </label>
    </div>
    <label className="notes-field">Notes <span>(optional)</span>
      <textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Broker, account, or transaction note" />
    </label>
    <div className="transaction-summary">
      <div><span>{isSell ? 'Estimated proceeds' : 'Estimated total'}</span><strong>{money(total, stock.currency)}</strong></div>
      <p>{number(quantity || '0')} × {money(price || '0', stock.currency)} {Number(fees || 0) ? `${isSell ? '−' : '+'} ${money(fees, stock.currency)} fees` : ''}</p>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <button className={`primary trade-submit ${isSell ? 'sell-action' : ''}`} disabled={saving || (isSell && (!holding || Number(quantity || 0) > Number(holding.quantity)))}>{saving ? 'Recording…' : `Record ${isSell ? 'Sell' : 'Buy'}`}</button>
  </form>
}
