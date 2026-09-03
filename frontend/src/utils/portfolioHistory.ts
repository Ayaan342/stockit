import type { PortfolioHistory } from '../types/api'

export interface ChartHistoryPoint {
  date: string
  value: number | null
}

export interface PreparedPortfolioHistory {
  points: ChartHistoryPoint[]
  hasMissingOwnedValue: boolean
}

/**
 * Derive a display range from the already transaction-aware portfolio series.
 * This deliberately keeps missing provider values as null; charts must never
 * turn unavailable valuation data into a zero-valued point.
 */
export function recentPortfolioHistory(history: PortfolioHistory, days: number): PortfolioHistory {
  const end = history.points.at(-1)?.date
  if (!end) return { ...history, points: [], complete: false }

  const endDate = new Date(`${end}T00:00:00Z`)
  const cutoff = new Date(endDate)
  cutoff.setUTCDate(cutoff.getUTCDate() - days + 1)
  const points = history.points.filter((point) => new Date(`${point.date}T00:00:00Z`) >= cutoff)

  return {
    ...history,
    period: days <= 30 ? '30d' : history.period,
    // A missing point outside the displayed range must not make a valid
    // shorter chart look incomplete.
    complete: points.length > 0 && points.every((point) => point.value !== null),
    points,
  }
}

/**
 * Keep the API series intact for Recharts. Portfolio ownership and valuation
 * completeness are established by the backend; the chart must not reinterpret
 * a recorded zero or fill a missing value.
 */
export function preparePortfolioHistoryForChart(history: PortfolioHistory): PreparedPortfolioHistory {
  const points = history.points.map((point) => {
    const numericValue = point.value === null ? null : Number(point.value)
    return {
      date: point.date,
      value: numericValue !== null && Number.isFinite(numericValue) ? numericValue : null,
    }
  })

  return {
    points,
    hasMissingOwnedValue: !history.complete && points.some((point) => point.value === null),
  }
}
