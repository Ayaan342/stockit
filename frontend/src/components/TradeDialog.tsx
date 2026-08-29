import { useMemo, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api/client'
import { money, number } from '../utils/format'

export function TradeDialog({ side, symbol, marketPrice, owned, onClose, onComplete }: { side: 'buy' | 'sell'; symbol: string; marketPrice?: string; owned?: string; onClose: () => void; onComplete: () => void }) {
  const [quantity, setQuantity] = useState('1')
  const [price, setPrice] = useState('')
  const [fees, setFees] = useState('0')
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const gross = useMemo(() => Number(quantity || 0) * Number(price || 0), [price, quantity])
  const total = side === 'buy' ? gross + Number(fees || 0) : gross - Number(fees || 0)
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError('')
    if (!Number.isFinite(Number(quantity)) || Number(quantity) <= 0) return setError('Enter a quantity greater than zero.')
    if (!Number.isFinite(Number(price)) || Number(price) <= 0) return setError('Enter the actual transaction price.')
    if (!Number.isFinite(Number(fees)) || Number(fees) < 0) return setError('Fees cannot be negative.')
    if (side === 'sell' && Number(quantity) > Number(owned)) return setError('Quantity exceeds your current holding.')
    if (side === 'sell' && total < 0) return setError('Fees cannot exceed sale proceeds.')
    setLoading(true)
    try { await api.trade(side, { symbol, quantity, price, fees, notes: notes || undefined, executed_at: `${date}T00:00:00Z` }); onComplete() } catch (err) { setError(err instanceof ApiError ? err.message : 'Unable to record transaction.') } finally { setLoading(false) }
  }
  const label = side === 'buy' ? 'Buy' : 'Sell'
  return <div className="modal-backdrop" role="presentation"><form className="modal trade-record-modal" onSubmit={submit}><button type="button" className="close" onClick={onClose}>×</button><p className="eyebrow">Record {label.toLowerCase()}</p><h2>{symbol}</h2>{marketPrice && <p className="muted">Current market price: <strong>{money(marketPrice)}</strong> <span className="reference-label">reference only</span></p>}{owned && <p>Owned: <strong>{number(owned)} shares</strong></p>}<label>Quantity<input autoFocus inputMode="decimal" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label><label>Actual {label.toLowerCase()} price<input inputMode="decimal" placeholder="0.00" value={price} onChange={(event) => setPrice(event.target.value)} /></label><div className="trade-form-grid"><label>Fees (optional)<input inputMode="decimal" value={fees} onChange={(event) => setFees(event.target.value)} /></label><label>Transaction date<input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label></div><label>Notes (optional)<input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Broker, account, or trade note" /></label><p className="estimate">Recorded {side === 'buy' ? 'cost' : 'proceeds'}: <strong>{money(total)}</strong></p>{error && <p className="form-error">{error}</p>}<button className="primary" disabled={loading}>{loading ? 'Saving…' : `Record ${label}`}</button></form></div>
}
