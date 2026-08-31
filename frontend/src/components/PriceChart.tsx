import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { StockHistoryPoint } from '../types/api'
import { money } from '../utils/format'

export function PriceChart({ history, currency }: { history: StockHistoryPoint[]; currency: string }) {
  const data = history
    .map((point) => ({ timestamp: point.timestamp, date: new Date(point.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), close: Number(point.close) }))
    .filter((point) => Number.isFinite(point.close))
  return <div className="chart"><ResponsiveContainer width="100%" height={270}><LineChart data={data}><XAxis dataKey="date" minTickGap={28} /><YAxis dataKey="close" width={82} tickFormatter={(value: number) => money(value, currency)} /><Tooltip labelFormatter={(_, payload) => payload[0]?.payload.timestamp ? new Date(payload[0].payload.timestamp).toLocaleDateString() : ''} formatter={(value) => money(value as number, currency)} /><Line type="monotone" dataKey="close" stroke="#28c7b1" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div>
}
