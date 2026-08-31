import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Holding } from '../types/api'
import { money } from '../utils/format'

interface HoldingPnlChartProps {
  holdings: Holding[]
  currency: string
}

interface HoldingPnlDatum {
  symbol: string
  value: number
  percentage: string | null
}

const axisMoney = (value: number, currency: string) => new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency,
  maximumFractionDigits: 0,
}).format(value)

const symmetricLimit = (values: number[]) => {
  const maximum = Math.max(...values.map((value) => Math.abs(value)), 1)
  const magnitude = 10 ** Math.floor(Math.log10(maximum))
  return Math.ceil(maximum / magnitude) * magnitude
}

function HoldingPnlTooltip({ active, payload, currency }: { active?: boolean; payload?: ReadonlyArray<{ payload?: HoldingPnlDatum }>; currency: string }) {
  const item = payload?.[0]?.payload
  if (!active || !item) return null
  const positive = item.value >= 0
  const absoluteValue = money(Math.abs(item.value), currency)
  return <div className="holding-pnl-tooltip">
    <strong>{item.symbol}</strong>
    <b className={positive ? 'positive' : 'negative'}>{positive ? '+' : '-'}{absoluteValue}</b>
    {item.percentage !== null && <span className={positive ? 'positive' : 'negative'}>{positive ? '+' : ''}{item.percentage}%</span>}
  </div>
}

export function HoldingPnlChart({ holdings, currency }: HoldingPnlChartProps) {
  const data: HoldingPnlDatum[] = holdings
    .filter((holding) => holding.profit_loss !== null)
    .map((holding) => ({ symbol: holding.symbol, value: Number(holding.profit_loss), percentage: holding.profit_loss_percentage }))
    .filter((holding) => Number.isFinite(holding.value))
    .sort((left, right) => right.value - left.value)

  if (!data.length) return <p className="muted compact-empty">Market data unavailable for holding-level analysis.</p>

  const limit = symmetricLimit(data.map((holding) => holding.value))
  return <div className="holding-pnl-chart" aria-label="Diverging unrealized profit and loss by holding">
    <ResponsiveContainer width="100%" height={Math.max(250, data.length * 46)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 18, bottom: 4, left: 4 }} barCategoryGap="27%">
        <XAxis
          type="number"
          domain={[-limit, limit]}
          ticks={[-limit, -limit / 2, 0, limit / 2, limit]}
          tickFormatter={(value: number) => axisMoney(value, currency)}
          tickLine={false}
          axisLine={false}
          tick={{ fill: '#8294a5', fontSize: 10 }}
        />
        <YAxis type="category" dataKey="symbol" width={106} tickLine={false} axisLine={false} tick={{ fill: '#bac7d1', fontSize: 11 }} />
        <ReferenceLine x={0} stroke="#657686" strokeWidth={1} />
        <Tooltip cursor={{ fill: 'rgba(130, 155, 171, 0.07)' }} content={({ active, payload }) => <HoldingPnlTooltip active={active} payload={payload as unknown as ReadonlyArray<{ payload?: HoldingPnlDatum }>} currency={currency} />} />
        <Bar dataKey="value" radius={[4, 4, 4, 4]} maxBarSize={20}>
          {data.map((holding) => <Cell key={holding.symbol} fill={holding.value >= 0 ? '#43c978' : '#ef626d'} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  </div>
}
