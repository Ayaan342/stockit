import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PortfolioHistory } from '../types/api'
import { money } from '../utils/format'
import { preparePortfolioHistoryForChart } from '../utils/portfolioHistory'

const chartDomain = (values: Array<number | null>): [number, number] | ['auto', 'auto'] => {
  const numeric = values.filter((value): value is number => value !== null)
  if (!numeric.length) return ['auto', 'auto']
  const minimum = Math.min(...numeric)
  const maximum = Math.max(...numeric)
  const padding = minimum === maximum
    ? Math.max(Math.abs(maximum) * 0.02, 1)
    : Math.max((maximum - minimum) * 0.02, Math.max(Math.abs(minimum), Math.abs(maximum)) * 0.001)
  return [minimum - padding, maximum + padding]
}

export function PortfolioHistoryChart({ history, monthly = false }: { history?: PortfolioHistory; monthly?: boolean }) {
  if (!history) return <div className="chart-skeleton" aria-label="Loading portfolio history" />
  const prepared = preparePortfolioHistoryForChart(history)
  const sampled = monthly ? prepared.points.filter((point, index, points) => index === points.length - 1 || point.date.slice(0, 7) !== points[index + 1]?.date.slice(0, 7)) : prepared.points
  const data = sampled.map((point) => ({ ...point, label: new Date(`${point.date}T00:00:00`).toLocaleDateString(undefined, monthly ? { month: 'short', year: 'numeric' } : { month: 'short', day: 'numeric' }) }))
  const warning = prepared.hasMissingOwnedValue && <p className="chart-note">Some dates are unavailable because market data could not be retrieved for an owned listing.</p>
  if (!data.some((point) => point.value !== null)) return <div className="portfolio-history-chart"><p className="muted compact-empty">Historical market data is unavailable for this period.</p>{warning}</div>
  return <div className="portfolio-history-chart"><ResponsiveContainer width="100%" height={monthly ? 270 : 245}><AreaChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}><defs><linearGradient id={`history-fill-${history.period}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#23c8b2" stopOpacity={.22} /><stop offset="100%" stopColor="#23c8b2" stopOpacity={0} /></linearGradient></defs><CartesianGrid vertical={false} stroke="#25313b" strokeDasharray="3 5" /><XAxis dataKey="label" minTickGap={monthly ? 24 : 34} tickLine={false} axisLine={false} /><YAxis hide domain={chartDomain(data.map((point) => point.value))} /><Tooltip labelFormatter={(_, payload) => payload[0]?.payload.date ? new Date(`${payload[0].payload.date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : ''} formatter={(value) => value === null ? 'Unavailable' : money(value as number, history.currency)} /><Area connectNulls={false} type="monotone" dataKey="value" stroke="#28c7b1" strokeWidth={2.2} fill={`url(#history-fill-${history.period})`} activeDot={{ r: 4, fill: '#e8fffb', stroke: '#28c7b1', strokeWidth: 2 }} /></AreaChart></ResponsiveContainer>{warning}</div>
}
