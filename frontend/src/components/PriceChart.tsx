import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { StockHistoryPoint } from '../types/api'

export function PriceChart({ history }: { history: StockHistoryPoint[] }) {
  const data = history.map((point) => ({ date: new Date(point.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), close: Number(point.close) }))
  return <div className="chart"><ResponsiveContainer width="100%" height={270}><LineChart data={data}><XAxis dataKey="date" minTickGap={28} /><YAxis dataKey="close" width={65} /><Tooltip /><Line type="monotone" dataKey="close" stroke="#2563eb" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div>
}
