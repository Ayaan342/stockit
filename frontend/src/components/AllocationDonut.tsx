import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { Holding } from '../types/api'
import { money, number } from '../utils/format'

const colors = ['#24c7d9', '#3b82f6', '#35c987', '#e7a63c', '#9671e8', '#ef7179', '#6da6c9', '#c789d6']

export function AllocationDonut({ holdings, currency = 'USD' }: { holdings: Holding[]; currency?: string }) {
  const valued = holdings
    .filter((holding) => holding.current_value !== null && Number.isFinite(Number(holding.current_value)) && Number(holding.current_value) > 0)
    .map((holding) => ({ ...holding, value: Number(holding.current_value) }))
  const total = valued.reduce((sum, holding) => sum + holding.value, 0)
  const data = valued.map((holding) => ({ ...holding, percentage: total > 0 ? holding.value / total * 100 : 0 }))
  if (!data.length) return <p className="muted compact-empty">{holdings.length ? 'Market data unavailable for allocation.' : 'No holdings yet. Record a buy transaction to see allocation.'}</p>
  return <div className="allocation-layout"><div className="allocation-chart"><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={data} dataKey="value" nameKey="symbol" innerRadius={57} outerRadius={82} paddingAngle={2} strokeWidth={0}>{data.map((holding, index) => <Cell key={`${holding.symbol}-${holding.exchange}`} fill={colors[index % colors.length]} />)}</Pie><Tooltip formatter={(value) => money(value as number, currency)} /></PieChart></ResponsiveContainer><div className="donut-center"><span>Valued holdings</span><strong>{money(total, currency)}</strong></div></div><div className="allocation-legend">{data.map((holding, index) => <div key={`${holding.symbol}-${holding.exchange}`}><i style={{ background: colors[index % colors.length] }} /><strong>{holding.symbol}</strong><span>{money(holding.value, currency)} · {number(holding.percentage)}%</span></div>)}</div></div>
}
