import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { Holding } from '../types/api'
import { money, number } from '../utils/format'

const colors = ['#2fc19d', '#5b6ee1', '#c9952d', '#bd5d66', '#78909c', '#d5d9df']

export function AllocationDonut({ holdings }: { holdings: Holding[] }) {
  const total = holdings.reduce((sum, holding) => sum + Number(holding.current_value), 0)
  const data = total > 0 ? holdings.map((holding) => ({ ...holding, value: Number(holding.current_value), percentage: Number(holding.current_value) / total * 100 })).filter((holding) => holding.value > 0) : []
  if (!data.length) return <p className="muted compact-empty">No holdings yet. Record a buy transaction to see allocation.</p>
  return <div className="allocation-layout"><div className="allocation-chart"><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={data} dataKey="value" nameKey="symbol" innerRadius={57} outerRadius={82} paddingAngle={2} strokeWidth={0}>{data.map((holding, index) => <Cell key={holding.symbol} fill={colors[index % colors.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer><div className="donut-center"><span>Holdings</span><strong>{money(total)}</strong></div></div><div className="allocation-legend">{data.map((holding, index) => <div key={holding.symbol}><i style={{ background: colors[index % colors.length] }} /><strong>{holding.symbol}</strong><span>{money(holding.current_value)} · {number(holding.percentage)}%</span></div>)}</div></div>
}
